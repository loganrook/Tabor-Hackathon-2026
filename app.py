"""
app.py — Main Flask application and routing.

Purpose: Flask entry point; create app, register extensions, define routes.
Who works here: Backend / API.
Responsibilities: App creation, minimal request handling; keep business logic in models.
"""

from flask import Flask, render_template, redirect, url_for, flash, request
from config import Config
from extensions import db, login_manager

# Import models after extensions so db is available; registers models with Flask-SQLAlchemy
from models import Coach, Athlete, Team  # noqa: E402, F401


def create_app(config_class=Config):
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "login"
    login_manager.login_message = "Please log in to access this page."

    @login_manager.user_loader
    def load_user(user_id: str):
        # TODO: Load Coach by id; if athletes log in later, distinguish by type or separate loader
        return Coach.query.get(int(user_id)) if user_id else None

    # ---------- Routes ----------

    @app.route("/")
    def index():
        """Serve the homepage."""
        # TODO: implement — e.g. redirect to login or show landing
        return render_template("home.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        """Show login form (GET) or authenticate and redirect (POST)."""
        # TODO: implement — validate credentials, call login_user(current_user), redirect to coach/athlete dashboard
        if request.method == "POST":
            flash("Login not implemented yet.", "info")
            return redirect(url_for("login"))
        return render_template("login.html")

    @app.route("/logout")
    def logout():
        """Clear session and redirect to homepage or login."""
        # TODO: implement — logout_user(), then redirect
        return redirect(url_for("index"))

    @app.route("/coach/dashboard")
    def coach_dashboard():
        """Coach-only: roster overview and quick actions (e.g. add athlete)."""
        # TODO: implement — @login_required, ensure current_user is Coach, load roster summary
        return render_template("coach_dashboard.html")

    @app.route("/athlete/dashboard")
    def athlete_dashboard():
        """Athlete-only: view assignments and personal info."""
        # TODO: implement — @login_required if athletes log in, ensure current_user is Athlete
        return render_template("athlete_dashboard.html")

    @app.route("/roster")
    def roster():
        """List athletes for the current coach/context."""
        # TODO: implement — @login_required, filter by current_user (coach), pass athletes to template
        return render_template("roster.html")

    @app.route("/roster/add", methods=["GET", "POST"])
    def add_athlete():
        """Show form to add athlete (GET) or create athlete and persist (POST)."""
        # TODO: implement — @login_required, validate form, create Athlete, redirect to roster or coach_dashboard
        if request.method == "POST":
            flash("Add athlete not implemented yet.", "info")
            return redirect(url_for("roster"))
        return redirect(url_for("coach_dashboard"))

    with app.app_context():
        db.create_all()

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
