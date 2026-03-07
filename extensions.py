"""
extensions.py — Flask extension instances (no app bound here).

Purpose: Hold db and login_manager so models.py can import db without circular imports.
Who works here: Backend.
Responsibilities: Instantiate SQLAlchemy and LoginManager; app binds them in app.py.
"""

from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

db = SQLAlchemy()
login_manager = LoginManager()
