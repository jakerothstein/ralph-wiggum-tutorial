"""Flask application factory and initialization."""
import os
from flask import Flask
from .config import config
from .models.base import db
from .logging_config import configure_logging


def create_app(config_name: str | None = None) -> Flask:
    """Create and configure the Flask application.

    Uses the application factory pattern for flexibility in testing
    and deployment scenarios.

    Args:
        config_name: Configuration to use ('development', 'testing', 'production').
                    Defaults to FLASK_ENV environment variable or 'development'.

    Returns:
        Configured Flask application instance.
    """
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Configure logging before other initialization
    configure_logging(app)

    # Initialize extensions
    db.init_app(app)

    # Ensure all models are imported so they register on db.metadata before
    # migrations / create_all run.
    from . import models  # noqa: F401

    # Initialize Flask-Migrate
    from flask_migrate import Migrate
    Migrate(app, db)

    # Build the AI client (real GitHub Models client, or the deterministic fake
    # when USE_FAKE_AI is set / no token is configured) and store it for services.
    from .services.ai_client import build_ai_client
    app.extensions['ai_client'] = build_ai_client(app.config)

    # Establish the anonymous session-id cookie lifecycle.
    from .services.session import init_session
    init_session(app)

    # Register error handlers
    from .errors import register_error_handlers
    register_error_handlers(app)

    # Register blueprints
    from .views import register_blueprints
    register_blueprints(app)

    return app
