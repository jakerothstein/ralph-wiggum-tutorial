/**
 * ChatIsland — the hybrid-Socratic tutor conversation UI.
 *
 * On mount it starts (or resumes) the conversation for the paper, then drives a
 * request/response loop: the user sends a message, the backend retrieves
 * grounding chunks and returns a tutor reply with an updated 0–100 comprehension
 * score, a rationale, and the chunk ids it cited. The component renders:
 *
 * - a scrollable message list (assistant text rendered as markdown),
 * - a live comprehension-score meter (with the latest rationale),
 * - per-assistant-message citations (the grounding chunk ids),
 * - an input that is disabled while a reply is pending.
 */
import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import ReactMarkdown from 'react-markdown'
import { ApiError, sendMessage, startConversation } from '@/lib/api'
import type { Message } from '@/types/paper'

interface Props {
  paperId: number
}

function ScoreMeter({
  score,
  rationale,
}: {
  score: number | null
  rationale: string | null
}) {
  const value = score ?? 0
  return (
    <div className="mb-3" title={rationale ?? undefined}>
      <div className="mb-1 flex items-center justify-between text-xs text-gray-500">
        <span>Comprehension</span>
        <span data-testid="score-value">{score === null ? '—' : `${value}/100`}</span>
      </div>
      <div
        className="h-2 w-full overflow-hidden rounded-full bg-gray-200"
        role="progressbar"
        aria-valuenow={value}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Comprehension score"
      >
        <div
          className="h-full rounded-full bg-blue-600 transition-all"
          style={{ width: `${value}%` }}
        />
      </div>
      {rationale && <p className="mt-1 text-xs text-gray-500">{rationale}</p>}
    </div>
  )
}

export function ChatIsland({ paperId }: Props) {
  const [conversationId, setConversationId] = useState<number | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const listRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let active = true
    startConversation(paperId)
      .then((conv) => {
        if (!active) return
        setConversationId(conv.id)
        setMessages(conv.messages)
      })
      .catch((e) => {
        if (!active) return
        setError(
          e instanceof ApiError ? e.message : 'Failed to start the conversation.',
        )
      })
    return () => {
      active = false
    }
  }, [paperId])

  useEffect(() => {
    const node = listRef.current
    if (node && typeof node.scrollTo === 'function') {
      node.scrollTo({ top: node.scrollHeight })
    }
  }, [messages])

  const latestScore = [...messages]
    .reverse()
    .find((m) => m.role === 'assistant' && m.comprehension_score !== null)

  async function handleSend(event: FormEvent) {
    event.preventDefault()
    const text = input.trim()
    if (!text || conversationId === null || pending) return
    setPending(true)
    setError(null)
    setInput('')
    try {
      const result = await sendMessage(conversationId, text)
      setMessages((prev) => [...prev, result.user, result.assistant])
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'The tutor could not reply.')
      setInput(text)
    } finally {
      setPending(false)
    }
  }

  return (
    <div className="flex h-full flex-col">
      <ScoreMeter
        score={latestScore?.comprehension_score ?? null}
        rationale={latestScore?.score_rationale ?? null}
      />

      <div
        ref={listRef}
        data-testid="message-list"
        className="flex-1 space-y-3 overflow-y-auto rounded-md bg-gray-50 p-3"
      >
        {messages.length === 0 && !error && (
          <p className="text-sm text-gray-500">
            Say what you understand so far, and the tutor will start probing your
            comprehension of the paper.
          </p>
        )}
        {messages.map((m) => (
          <div
            key={m.id}
            className={m.role === 'user' ? 'text-right' : 'text-left'}
          >
            <div
              className={[
                'inline-block max-w-[90%] rounded-lg px-3 py-2 text-sm',
                m.role === 'user'
                  ? 'bg-blue-600 text-white'
                  : 'bg-white text-gray-800 shadow',
              ].join(' ')}
            >
              {m.role === 'assistant' ? (
                <div className="prose prose-sm max-w-none">
                  <ReactMarkdown>{m.content}</ReactMarkdown>
                </div>
              ) : (
                m.content
              )}
              {m.role === 'assistant' && m.cited_chunk_ids.length > 0 && (
                <div className="mt-1 flex flex-wrap gap-1">
                  {m.cited_chunk_ids.map((cid) => (
                    <span
                      key={cid}
                      className="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-500"
                    >
                      source #{cid}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        {pending && (
          <p className="text-sm text-gray-400" aria-live="polite">
            Tutor is thinking…
          </p>
        )}
      </div>

      {error && (
        <p role="alert" className="mt-2 rounded-md bg-red-50 p-2 text-sm text-red-700">
          {error}
        </p>
      )}

      <form onSubmit={handleSend} className="mt-3 flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type your answer or question…"
          aria-label="Message the tutor"
          disabled={pending || conversationId === null}
          className="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none disabled:bg-gray-100"
        />
        <button
          type="submit"
          disabled={pending || conversationId === null || !input.trim()}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          Send
        </button>
      </form>
    </div>
  )
}
