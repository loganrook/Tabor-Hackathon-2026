"""
config.py — Application configuration.

Purpose: Central configuration for the Flask app (secret key, database, session, etc.).
Who works here: Backend / deployment.
Responsibilities: Provide env-based or default settings; avoid hardcoding secrets.
"""

import os


class Config:
    """Flask application configuration. Load in app.py via app.config.from_object(Config)."""

    # Use a strong secret in production (e.g. set SECRET_KEY env var)
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")

    # SQLite database; file created in project root as app.db
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///app.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Enable debug mode only when FLASK_DEBUG=1 (do not use in production)
    DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1"

    # SESSION_COOKIE_SECURE = True  # Set True when using HTTPS
    # SESSION_COOKIE_HTTPONLY = True
