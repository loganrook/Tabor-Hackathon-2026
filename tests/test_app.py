"""
test_app.py — Lightweight route tests for the Flask application.

These tests are intentionally minimal: they exercise a few core routes
to catch obvious regressions (homepage, login page, and a protected
dashboard route redirecting when unauthenticated).
"""

import pytest

from app import create_app


@pytest.fixture(scope="module")
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_homepage_returns_200(client):
    """GET / should return 200 and render the home page."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"RepRoom" in resp.data


def test_login_page_returns_200(client):
    """GET /login should return 200 and show the login form."""
    resp = client.get("/login")
    assert resp.status_code == 200
    assert b"Log in" in resp.data


def test_dashboard_requires_login_redirects(client):
    """
    GET /dashboard without being logged in should redirect to login.
    Flask-Login's @login_required handles this redirect.
    """
    resp = client.get("/dashboard", follow_redirects=False)
    assert resp.status_code in (302, 303)
    assert "/login" in resp.headers.get("Location", "")
