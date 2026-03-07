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


def _local_now():
    """Return naive local datetime for created_at / completed_at (hackathon: no timezone)."""
    return datetime.now()


# Many-to-many: athletes can be on multiple teams
athlete_teams = db.Table(
    "athlete_teams",
    db.Column("athlete_id", db.Integer, db.ForeignKey("athletes.id"), primary_key=True),
    db.Column("team_id", db.Integer, db.ForeignKey("teams.id"), primary_key=True),
)

# Many-to-many: athletes can be in multiple groups (position groups)
group_members = db.Table(
    "group_members",
    db.Column("group_id", db.Integer, db.ForeignKey("groups.id"), primary_key=True),
    db.Column("athlete_id", db.Integer, db.ForeignKey("athletes.id"), primary_key=True),
)

# Many-to-many: additional coaches can join teams (assistant / staff coaches)
coach_teams = db.Table(
    "coach_teams",
    db.Column("coach_id", db.Integer, db.ForeignKey("coaches.id"), primary_key=True),
    db.Column("team_id", db.Integer, db.ForeignKey("teams.id"), primary_key=True),
)


class Coach(UserMixin, db.Model):
    """Coach user: can log in, own teams, and manage athletes."""

    __tablename__ = "coaches"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=_local_now)
    coach_type = db.Column(db.String(50), nullable=False, default="coach")

    # Relationship: one coach has many teams they own (head coach per team)
    teams = db.relationship("Team", backref="coach", lazy="dynamic", foreign_keys="Team.coach_id")

    # Relationship: coach's personal workout templates
    workout_templates = db.relationship(
        "WorkoutTemplate",
        backref="coach",
        lazy="dynamic",
        foreign_keys="WorkoutTemplate.coach_id",
    )

    __mapper_args__ = {
        "polymorphic_on": coach_type,
        "polymorphic_identity": "coach",
    }

    def set_password(self, password: str) -> None:
        """Hash the password and store it in self.password_hash."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Return True if the given password matches the hash."""
        return check_password_hash(self.password_hash, password)

    def get_id(self) -> str:
        """Return a unique id for Flask-Login; prefix so user_loader can distinguish Coach from Athlete."""
        return f"coach-{self.id}"


class HeadCoach(Coach):
    """Head coach type (shares coaches table via single-table inheritance)."""

    __mapper_args__ = {
        "polymorphic_identity": "head",
    }


class Team(db.Model):
    """Team: belongs to a coach; has many athletes via join table."""

    __tablename__ = "teams"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    coach_id = db.Column(db.Integer, db.ForeignKey("coaches.id"), nullable=False)
    invite_code = db.Column(db.String(8), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=_local_now)

    # Many-to-many with Athlete via athlete_teams
    athletes = db.relationship(
        "Athlete",
        secondary=athlete_teams,
        backref=db.backref("teams", lazy="dynamic"),
        lazy="dynamic",
    )

    # Many-to-many: additional coaches (staff) on this team, besides the owning coach
    coaches = db.relationship(
        "Coach",
        secondary=coach_teams,
        backref=db.backref("joined_teams", lazy="dynamic"),
        lazy="dynamic",
    )

    # One team has many workouts
    workouts = db.relationship(
        "Workout",
        backref="team",
        lazy="dynamic",
        foreign_keys="Workout.team_id",
    )

    # One team has many announcements
    announcements = db.relationship(
        "Announcement",
        backref="team",
        lazy="dynamic",
        foreign_keys="Announcement.team_id",
    )

    # One team has many groups (position groups)
    groups = db.relationship(
        "Group",
        backref="team",
        lazy="dynamic",
        foreign_keys="Group.team_id",
    )

    @classmethod
    def generate_invite_code(cls) -> str:
        """Generate a random 8-character invite code that is unique in the database."""
        for _ in range(100):
            code = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
            if not cls.query.filter_by(invite_code=code).first():
                return code
        raise RuntimeError("Could not generate unique invite code")


class Group(db.Model):
    """Position group within a team (e.g. Quarterbacks, O-Line)."""

    __tablename__ = "groups"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=_local_now)

    athletes = db.relationship(
        "Athlete",
        secondary=group_members,
        backref=db.backref("groups", lazy="dynamic"),
        lazy="dynamic",
    )


class Announcement(db.Model):
    """Announcement: posted by a coach for a team (or auto-generated)."""

    __tablename__ = "announcements"

    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey("groups.id"), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("coaches.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=_local_now)
    is_auto = db.Column(db.Boolean, default=False)

    group = db.relationship(
        "Group",
        backref=db.backref("announcements", lazy="dynamic"),
        foreign_keys="Announcement.group_id",
    )


class DirectMessage(db.Model):
    """Direct message between a coach and an athlete for a specific team."""

    __tablename__ = "direct_messages"

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False)
    coach_id = db.Column(db.Integer, db.ForeignKey("coaches.id"), nullable=False)
    athlete_id = db.Column(db.Integer, db.ForeignKey("athletes.id"), nullable=False)
    sender_role = db.Column(db.String(16), nullable=False)  # 'coach' or 'athlete'
    reason = db.Column(db.String(50), nullable=True)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=_local_now)
    read_by_coach = db.Column(db.Boolean, default=False)
    read_by_athlete = db.Column(db.Boolean, default=False)
    resolved = db.Column(db.Boolean, default=False)

    team = db.relationship(
        "Team",
        backref=db.backref("direct_messages", lazy="dynamic"),
        foreign_keys="DirectMessage.team_id",
    )
    coach = db.relationship(
        "Coach",
        backref=db.backref("direct_messages", lazy="dynamic"),
        foreign_keys="DirectMessage.coach_id",
    )
    athlete = db.relationship(
        "Athlete",
        backref=db.backref("direct_messages", lazy="dynamic"),
        foreign_keys="DirectMessage.athlete_id",
    )


class WorkoutTemplate(db.Model):
    """Saved workout template in a coach's library (not tied to a team)."""

    __tablename__ = "workout_templates"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    coach_id = db.Column(db.Integer, db.ForeignKey("coaches.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=_local_now)

    exercises = db.relationship(
        "ExerciseTemplate",
        backref="workout_template",
        order_by="ExerciseTemplate.order",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )


class ExerciseTemplate(db.Model):
    """Exercise row inside a workout template."""

    __tablename__ = "exercise_templates"

    id = db.Column(db.Integer, primary_key=True)
    workout_template_id = db.Column(
        db.Integer,
        db.ForeignKey("workout_templates.id"),
        nullable=False,
    )
    name = db.Column(db.String(255), nullable=False)
    sets = db.Column(db.Integer, nullable=True)
    reps = db.Column(db.Integer, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    order = db.Column(db.Integer, nullable=True)


class Workout(db.Model):
    """Assigned workout for a team or group."""

    __tablename__ = "workouts"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    due_date = db.Column(db.DateTime, nullable=True)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey("groups.id"), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("coaches.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=_local_now)

    group = db.relationship("Group", backref="workouts", foreign_keys="Workout.group_id")

    exercises = db.relationship(
        "Exercise",
        backref="workout",
        order_by="Exercise.order",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )


class Exercise(db.Model):
    """Exercise row inside a workout."""

    __tablename__ = "exercises"

    id = db.Column(db.Integer, primary_key=True)
    workout_id = db.Column(db.Integer, db.ForeignKey("workouts.id"), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    sets = db.Column(db.Integer, nullable=True)
    reps = db.Column(db.Integer, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    # Optional per-set rep plan, stored as JSON text:
    # e.g. [{"set": 1, "reps": 12}, {"set": 2, "reps": 10}]
    set_plan = db.Column(db.Text, nullable=True)
    order = db.Column(db.Integer, nullable=True)

    statuses = db.relationship(
        "ExerciseStatus",
        backref="exercise",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )


class ExerciseStatus(db.Model):
    """Tracks completion of an exercise by an athlete."""

    __tablename__ = "exercise_statuses"

    id = db.Column(db.Integer, primary_key=True)
    exercise_id = db.Column(db.Integer, db.ForeignKey("exercises.id"), nullable=False)
    athlete_id = db.Column(db.Integer, db.ForeignKey("athletes.id"), nullable=False)
    completed = db.Column(db.Boolean, default=False)
    completed_at = db.Column(db.DateTime, nullable=True)

    athlete = db.relationship("Athlete", backref=db.backref("exercise_statuses", lazy="dynamic"))


class Athlete(UserMixin, db.Model):
    """Athlete: can be on multiple teams via athlete_teams join table."""

    __tablename__ = "athletes"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=_local_now)

    def set_password(self, password: str) -> None:
        """Hash the password and store it in self.password_hash."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Return True if the given password matches the hash."""
        return check_password_hash(self.password_hash, password)

    def get_id(self) -> str:
        """Return a unique id for Flask-Login; prefix so user_loader can distinguish Athlete from Coach."""
        return f"athlete-{self.id}"

    # TODO: Helper methods as needed (e.g. get_workouts, display_name)
