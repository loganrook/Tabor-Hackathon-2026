"""
models.py — SQLAlchemy models (Coach, Athlete, Team).

Purpose: Data layer: table definitions, relationships, and (later) query/helper methods.
Who works here: Backend.
Responsibilities: Define columns and relationships; keep DB logic here, not in routes.
"""

import random
import string
from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from extensions import db


# Many-to-many: athletes can be on multiple teams
athlete_teams = db.Table(
    "athlete_teams",
    db.Column("athlete_id", db.Integer, db.ForeignKey("athletes.id"), primary_key=True),
    db.Column("team_id", db.Integer, db.ForeignKey("teams.id"), primary_key=True),
)


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

    def set_password(self, password: str) -> None:
        """Hash the password and store it in self.password_hash."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Return True if the given password matches the hash."""
        return check_password_hash(self.password_hash, password)

    def get_id(self) -> str:
        """Return a unique id for Flask-Login; prefix so user_loader can distinguish Coach from Athlete."""
        return f"coach-{self.id}"


class Team(db.Model):
    """Team: belongs to a coach; has many athletes via join table."""

    __tablename__ = "teams"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    coach_id = db.Column(db.Integer, db.ForeignKey("coaches.id"), nullable=False)
    invite_code = db.Column(db.String(8), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Many-to-many with Athlete via athlete_teams
    athletes = db.relationship(
        "Athlete",
        secondary=athlete_teams,
        backref=db.backref("teams", lazy="dynamic"),
        lazy="dynamic",
    )

    # One team has many assignments
    assignments = db.relationship(
        "Assignment",
        backref="team",
        lazy="dynamic",
        foreign_keys="Assignment.team_id",
    )

    # One team has many announcements
    announcements = db.relationship(
        "Announcement",
        backref="team",
        lazy="dynamic",
        foreign_keys="Announcement.team_id",
    )

    @classmethod
    def generate_invite_code(cls) -> str:
        """Generate a random 8-character invite code that is unique in the database."""
        for _ in range(100):
            code = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
            if not cls.query.filter_by(invite_code=code).first():
                return code
        raise RuntimeError("Could not generate unique invite code")


class Announcement(db.Model):
    """Announcement: posted by a coach for a team."""

    __tablename__ = "announcements"

    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("coaches.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Assignment(db.Model):
    """Assignment: created by a coach for a team."""

    __tablename__ = "assignments"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    due_date = db.Column(db.DateTime, nullable=True)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("coaches.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    statuses = db.relationship(
        "AssignmentStatus",
        backref="assignment",
        lazy="dynamic",
        foreign_keys="AssignmentStatus.assignment_id",
    )


class AssignmentStatus(db.Model):
    """Tracks completion of an assignment by an athlete."""

    __tablename__ = "assignment_statuses"

    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey("assignments.id"), nullable=False)
    athlete_id = db.Column(db.Integer, db.ForeignKey("athletes.id"), nullable=False)
    completed = db.Column(db.Boolean, default=False)
    completed_at = db.Column(db.DateTime, nullable=True)

    athlete = db.relationship("Athlete", backref=db.backref("assignment_statuses", lazy="dynamic"))


class Athlete(UserMixin, db.Model):
    """Athlete: can be on multiple teams via athlete_teams join table."""

    __tablename__ = "athletes"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password: str) -> None:
        """Hash the password and store it in self.password_hash."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Return True if the given password matches the hash."""
        return check_password_hash(self.password_hash, password)

    def get_id(self) -> str:
        """Return a unique id for Flask-Login; prefix so user_loader can distinguish Athlete from Coach."""
        return f"athlete-{self.id}"

    # TODO: Helper methods as needed (e.g. get_assignments, display_name)
