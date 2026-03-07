"""
models.py — SQLAlchemy models (Coach, Athlete, Team).

Purpose: Data layer: table definitions, relationships, and (later) query/helper methods.
Who works here: Backend.
Responsibilities: Define columns and relationships; keep DB logic here, not in routes.
"""

from datetime import datetime
from flask_login import UserMixin

from extensions import db


class Coach(UserMixin, db.Model):
    """Coach user: can log in, own teams, and manage athletes."""

    __tablename__ = "coaches"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship: one coach has many teams
    teams = db.relationship("Team", backref="coach", lazy="dynamic", foreign_keys="Team.coach_id")

    # TODO: set_password(password: str) -> None
    # TODO: check_password(password: str) -> bool
    # Flask-Login: get_id, is_authenticated, is_active provided by UserMixin


class Team(db.Model):
    """Team: belongs to a coach; has many athletes."""

    __tablename__ = "teams"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    coach_id = db.Column(db.Integer, db.ForeignKey("coaches.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    athletes = db.relationship("Athlete", backref="team", lazy="dynamic", foreign_keys="Athlete.team_id")

    # TODO: add_athlete(athlete: "Athlete") -> None
    # TODO: roster list / get_roster() -> list[Athlete]


class Athlete(db.Model):
    """Athlete: belongs to a team (and thus to that team's coach)."""

    __tablename__ = "athletes"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # TODO: If athletes log in: add UserMixin, password_hash, and Flask-Login loader for Athlete
    # TODO: Helper methods as needed (e.g. get_assignments, display_name)
