"""GitHub Models AI client (the single integration point for the AI provider).

GitHub Models exposes an **OpenAI-compatible** chat + embeddings API, so we use
the ``openai`` SDK pointed at ``GITHUB_MODELS_ENDPOINT`` with the ``GITHUB_TOKEN``
as the API key. Centralizing this here means every other service depends on an
*injectable* client, which makes faking trivial in tests and lets us swap
providers by touching only this file + config.

Two implementations share one duck-typed interface (``chat_json`` + ``embed``):

* :class:`GitHubModelsClient` — the real network client, with a small retry and
  JSON-mode parsing.
* :class:`FakeAiClient` — a deterministic, in-process fake used by the test suite
  and by the E2E run (``USE_FAKE_AI=1``). It never touches the network and
  returns schema-valid analysis + tutor payloads so the whole pipeline can run
  hermetically.

Why a fake instead of mocking the SDK everywhere: the fake is a single, stable
seam. Tests assert behaviour of *our* code (prompt assembly, parsing, clamping,
persistence) rather than the OpenAI SDK's internals.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import time
from typing import Any, Protocol, Sequence, runtime_checkable

logger = logging.getLogger(__name__)


class AiClientError(Exception):
    """Raised when the AI provider fails or returns an unparseable response."""


@runtime_checkable
class AiClient(Protocol):
    """Structural interface shared by the real and fake clients."""

    def chat_json(
        self, messages: Sequence[dict[str, str]], schema_hint: str | None = None
    ) -> dict[str, Any]:
        """Return a JSON object from a chat completion (JSON mode)."""

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one embedding vector per input text."""


class GitHubModelsClient:
    """Real OpenAI-compatible client for GitHub Models."""

    def __init__(
        self,
        token: str,
        endpoint: str,
        chat_model: str,
        embedding_model: str,
        timeout: int = 60,
        max_retries: int = 1,
    ) -> None:
        # Imported lazily so importing this module never requires the SDK in
        # environments that only ever use the fake client.
        from openai import OpenAI

        # Typed as Any so the OpenAI SDK's heavily-overloaded methods don't leak
        # call-site typing differences between environments that do/don't have
        # the SDK stubs installed.
        self._client: Any = OpenAI(base_url=endpoint, api_key=token, timeout=timeout)
        self._chat_model = chat_model
        self._embedding_model = embedding_model
        self._max_retries = max_retries

    def chat_json(
        self, messages: Sequence[dict[str, str]], schema_hint: str | None = None
    ) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                resp = self._client.chat.completions.create(
                    model=self._chat_model,
                    messages=list(messages),
                    response_format={'type': 'json_object'},
                    temperature=0.2,
                )
                content = resp.choices[0].message.content or '{}'
                return _parse_json_object(content)
            except AiClientError:
                raise
            except Exception as exc:  # noqa: BLE001 - normalize to a typed error
                last_error = exc
                logger.warning('chat_json attempt %d failed: %s', attempt + 1, exc)
                if attempt < self._max_retries:
                    time.sleep(0.5 * (attempt + 1))
        raise AiClientError(f'chat completion failed: {last_error}')

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                resp = self._client.embeddings.create(
                    model=self._embedding_model, input=list(texts)
                )
                return [list(item.embedding) for item in resp.data]
            except Exception as exc:  # noqa: BLE001 - normalize to a typed error
                last_error = exc
                logger.warning('embed attempt %d failed: %s', attempt + 1, exc)
                if attempt < self._max_retries:
                    time.sleep(0.5 * (attempt + 1))
        raise AiClientError(f'embedding request failed: {last_error}')


class FakeAiClient:
    """Deterministic, in-process AI client for tests and the E2E suite.

    ``chat_json`` branches on ``schema_hint`` to return a schema-valid analysis or
    tutor turn. ``embed`` produces stable pseudo-random unit-ish vectors derived
    from a hash of the text, so identical text always embeds identically and
    cosine similarity is meaningful (same text -> similarity 1.0).
    """

    def __init__(self, embedding_dims: int = 1536) -> None:
        self.embedding_dims = embedding_dims

    def chat_json(
        self, messages: Sequence[dict[str, str]], schema_hint: str | None = None
    ) -> dict[str, Any]:
        if schema_hint == 'paper_analysis':
            return self._fake_analysis(messages)
        if schema_hint == 'tutor_turn':
            return self._fake_tutor_turn(messages)
        return {}

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._fake_vector(t) for t in texts]

    # -- internals -------------------------------------------------------
    def _fake_vector(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode('utf-8')).digest()
        # Expand the 32-byte digest deterministically to the desired length.
        raw: list[float] = []
        counter = 0
        while len(raw) < self.embedding_dims:
            block = hashlib.sha256(digest + counter.to_bytes(4, 'big')).digest()
            raw.extend(b / 255.0 for b in block)
            counter += 1
        vec = raw[: self.embedding_dims]
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def _fake_analysis(self, messages: Sequence[dict[str, str]]) -> dict[str, Any]:
        title = _guess_title(messages)
        return {
            'summary': (
                f'This paper, "{title}", introduces an approach and evaluates it. '
                'It frames a problem, proposes a method, and reports results.'
            ),
            'contributions': [
                'A clearly framed problem statement.',
                'A proposed method to address the problem.',
                'An empirical evaluation of the method.',
            ],
            'methodology': (
                'The authors describe their method and validate it through '
                'experiments, comparing against baselines.'
            ),
            'key_claims': [
                {
                    'claim': 'The proposed method improves on prior work.',
                    'evidence': 'Reported experimental results in the paper.',
                }
            ],
            'limitations': [
                'Evaluation scope may be limited.',
                'Generalization beyond the tested setting is unverified.',
            ],
            'glossary': [
                {'term': 'Method', 'definition': 'The approach proposed by the paper.'},
                {'term': 'Baseline', 'definition': 'A reference approach for comparison.'},
            ],
            'questions': [
                {
                    'question': 'What problem does the paper address?',
                    'difficulty': 'easy',
                    'ideal_answer': 'The core problem framed in the introduction.',
                },
                {
                    'question': 'How does the proposed method work?',
                    'difficulty': 'medium',
                    'ideal_answer': 'A description of the methodology.',
                },
                {
                    'question': 'What are the main limitations?',
                    'difficulty': 'hard',
                    'ideal_answer': 'The limitations discussed by the authors.',
                },
            ],
        }

    def _fake_tutor_turn(self, messages: Sequence[dict[str, str]]) -> dict[str, Any]:
        user_text = ''
        for msg in reversed(messages):
            if msg.get('role') == 'user':
                user_text = msg.get('content', '')
                break
        reply = (
            "Good — let's dig in. Based on the passages you read, can you explain in "
            'your own words what core problem the paper is trying to solve, and why '
            'existing approaches fall short?'
        )
        if user_text:
            reply = (
                f'You said: "{user_text[:80]}". {reply}'
            )
        return {
            'reply': reply,
            'comprehension_score': 50,
            'score_rationale': 'Baseline estimate; refine as the conversation continues.',
            'cited_chunk_ids': [],
        }


def _parse_json_object(content: str) -> dict[str, Any]:
    """Parse a JSON object from model output, tolerating ```json fences."""
    text = content.strip()
    if text.startswith('```'):
        text = text.strip('`')
        if text.lower().startswith('json'):
            text = text[4:]
        text = text.strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AiClientError(f'model did not return valid JSON: {exc}') from exc
    if not isinstance(data, dict):
        raise AiClientError('model JSON was not an object')
    return data


def _guess_title(messages: Sequence[dict[str, str]]) -> str:
    """Best-effort title extraction from the prompt for nicer fake output."""
    for msg in messages:
        content = msg.get('content', '')
        if 'Title:' in content:
            line = content.split('Title:', 1)[1].splitlines()[0].strip()
            if line:
                return line[:120]
    return 'Untitled Paper'


def build_ai_client(config: Any) -> AiClient:
    """Construct the appropriate AI client from app config.

    Uses the deterministic fake when ``USE_FAKE_AI`` is set or when no
    ``GITHUB_TOKEN`` is configured, so the app never makes accidental network
    calls in tests or unconfigured environments.
    """
    use_fake = bool(config.get('USE_FAKE_AI'))
    token = config.get('GITHUB_TOKEN') or ''
    dims = int(config.get('EMBEDDING_DIMS', 1536))
    if use_fake or not token:
        if not use_fake:
            logger.warning('No GITHUB_TOKEN configured; using FakeAiClient.')
        return FakeAiClient(embedding_dims=dims)
    return GitHubModelsClient(
        token=token,
        endpoint=config.get('GITHUB_MODELS_ENDPOINT'),
        chat_model=config.get('GITHUB_MODELS_CHAT_MODEL'),
        embedding_model=config.get('GITHUB_MODELS_EMBEDDING_MODEL'),
        timeout=int(config.get('AI_REQUEST_TIMEOUT', 60)),
        max_retries=int(config.get('AI_MAX_RETRIES', 1)),
    )
