"""Services package.

The service layer is intentionally decoupled from Flask views so the AI
provider, PDF parser, chunker, or retrieval strategy can change without touching
routes or the frontend. The single integration point for the AI provider is
:mod:`app.services.ai_client`.
"""
