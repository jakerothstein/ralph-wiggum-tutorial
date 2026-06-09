"""Application configuration classes.

Configuration is loaded from environment variables with sensible defaults.
Each environment (development, testing, production) has its own class.
"""
import os
from dotenv import load_dotenv

# Load .env file if it exists
load_dotenv()


def _env_bool(name: str, default: bool = False) -> bool:
    """Read a boolean environment variable (``1/true/yes/on`` are truthy)."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {'1', 'true', 'yes', 'on'}


def _env_int(name: str, default: int) -> int:
    """Read an integer environment variable, falling back to ``default``."""
    raw = os.environ.get(name)
    if raw is None or raw.strip() == '':
        return default
    try:
        return int(raw)
    except ValueError:
        return default


class Config:
    """Base configuration with shared settings."""

    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key-change-me')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Vite dev server URL for template asset loading
    VITE_DEV_SERVER = os.environ.get('VITE_DEV_SERVER', 'http://localhost:5173')

    # --- Paper Comprehension Tutor: GitHub Models AI backend ---
    GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
    GITHUB_MODELS_ENDPOINT = os.environ.get(
        'GITHUB_MODELS_ENDPOINT', 'https://models.github.ai/inference'
    )
    GITHUB_MODELS_CHAT_MODEL = os.environ.get(
        'GITHUB_MODELS_CHAT_MODEL', 'openai/gpt-4o-mini'
    )
    GITHUB_MODELS_EMBEDDING_MODEL = os.environ.get(
        'GITHUB_MODELS_EMBEDDING_MODEL', 'openai/text-embedding-3-small'
    )
    EMBEDDING_DIMS = _env_int('EMBEDDING_DIMS', 1536)

    # Ingest / retrieval tuning
    MAX_UPLOAD_BYTES = _env_int('MAX_UPLOAD_BYTES', 10 * 1024 * 1024)
    CHUNK_SIZE_TOKENS = _env_int('CHUNK_SIZE_TOKENS', 400)
    CHUNK_OVERLAP_TOKENS = _env_int('CHUNK_OVERLAP_TOKENS', 80)
    RETRIEVAL_TOP_K = _env_int('RETRIEVAL_TOP_K', 5)

    # AI client behaviour. When USE_FAKE_AI is true (or no token is present),
    # a deterministic in-process fake client is used instead of real network calls.
    USE_FAKE_AI = _env_bool('USE_FAKE_AI', False)
    AI_REQUEST_TIMEOUT = _env_int('AI_REQUEST_TIMEOUT', 60)
    AI_MAX_RETRIES = _env_int('AI_MAX_RETRIES', 1)

    # Cookie used to scope anonymous sessions.
    SESSION_COOKIE_NAME_PAPER = 'paper_session'


class DevelopmentConfig(Config):
    """Development configuration with debug enabled."""

    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        'postgresql://postgres:postgres@localhost:5432/app'
    )
    # In development, load assets from Vite dev server
    VITE_DEV_MODE = True


class TestingConfig(Config):
    """Testing configuration with in-memory database."""

    TESTING = True
    DEBUG = True
    # Use SQLite in-memory for fast tests
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    VITE_DEV_MODE = False
    # Disable CSRF for testing
    WTF_CSRF_ENABLED = False

    # Tests never hit the network: always use the deterministic fake AI client.
    USE_FAKE_AI = True
    # Small embedding dimensionality keeps fake vectors cheap; SQLite stores them
    # as JSON text so the value only needs to be internally consistent.
    EMBEDDING_DIMS = 16


class ProductionConfig(Config):
    """Production configuration with strict security settings."""

    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    # In production, load assets from built manifest
    VITE_DEV_MODE = False

    # Ensure critical settings are configured
    @classmethod
    def init_app(cls, app):  # type: ignore[no-untyped-def]
        """Production-specific initialization."""
        if not os.environ.get('FLASK_SECRET_KEY'):
            raise ValueError("FLASK_SECRET_KEY must be set in production")
        if not os.environ.get('DATABASE_URL'):
            raise ValueError("DATABASE_URL must be set in production")


# Configuration dictionary for easy access
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
