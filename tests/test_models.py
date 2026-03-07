"""
test_models.py — Unit tests for SQLAlchemy models (Coach, Athlete, Team).

Purpose: Test model creation, relationships, validation, and model methods.
Who works here: Backend / QA.
Responsibilities: Use app context and test DB; keep DB logic coverage in models.
"""

import pytest

# TODO: from app import create_app; from extensions import db; from models import Coach, Athlete, Team


def test_coach_creation():
    """Test that a Coach can be created with required fields (email, password_hash, name)."""
    # TODO: create app context, create Coach, assert id and attributes
    assert True


def test_athlete_belongs_to_team():
    """Test that an Athlete is linked to a Team via team_id and relationship."""
    # TODO: create Coach, Team, Athlete; assert athlete.team_id and athlete.team
    assert True


def test_team_has_athletes():
    """Test that a Team has an athletes relationship and can list roster."""
    # TODO: create Coach, Team, Athlete(s); assert team.athletes count or list
    assert True


def test_coach_has_teams():
    """Test that a Coach has a teams relationship."""
    # TODO: create Coach, Team; assert coach.teams
    assert True


def test_coach_email_unique():
    """Test that Coach email must be unique (constraint or validation)."""
    # TODO: create two coaches with same email; expect integrity error or validation
    assert True
