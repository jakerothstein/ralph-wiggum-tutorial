"""Views (routes) package.

Blueprint registration for all application routes.
Each view module defines a Blueprint with its routes.
"""
from flask import Flask


def register_blueprints(app: Flask) -> None:
    """Register all blueprints with the Flask application.

    Args:
        app: Flask application instance
    """
    from .paper import paper_bp
    from .chat import chat_bp

    app.register_blueprint(paper_bp)
    app.register_blueprint(chat_bp)
