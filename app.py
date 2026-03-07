"""
app.py — Main Flask application and routing.

Purpose: Flask entry point; create app, register extensions, define routes.
Who works here: Backend / API.
Responsibilities: App creation, minimal request handling; keep business logic in models.
"""

from flask import Flask, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
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
        """Load Coach or Athlete by id; user_id is 'coach-{id}' or 'athlete-{id}'."""
        if not user_id or "-" not in user_id:
            return None
        prefix, _, id_str = user_id.partition("-")
        try:
            pk = int(id_str)
        except ValueError:
            return None
        if prefix == "coach":
            return Coach.query.get(pk)
        if prefix == "athlete":
            return Athlete.query.get(pk)
        return None

    # ---------- Routes ----------

    @app.route("/")
    def index():
        """Serve the homepage."""
        # TODO: implement — e.g. redirect to login or show landing
        return render_template("home.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        """Show login form (GET) or authenticate and redirect (POST)."""
        if request.method == "POST":
            email = request.form.get("email", "").strip()
            password = request.form.get("password", "")
            if not email or not password:
                flash("Email and password are required.", "error")
                return render_template("login.html")
            coach = Coach.query.filter_by(email=email).first()
            if coach and coach.check_password(password):
                login_user(coach)
                return redirect(url_for("coach_dashboard"))
            athlete = Athlete.query.filter_by(email=email).first()
            if athlete and athlete.check_password(password):
                login_user(athlete)
                return redirect(url_for("athlete_dashboard"))
            flash("Invalid email or password.", "error")
            return render_template("login.html")
        return render_template("login.html")

    @app.route("/logout")
    def logout():
        """Clear session and redirect to homepage or login."""
        logout_user()
        return redirect(url_for("index"))

    @app.route("/coach/dashboard")
    @login_required
    def coach_dashboard():
        """Coach-only: roster overview and quick actions (e.g. add athlete)."""
        # TODO: implement — ensure current_user is Coach, load roster summary
        return render_template("coach_dashboard.html")

    @app.route("/athlete/dashboard")
    @login_required
    def athlete_dashboard():
        """Athlete-only: view assignments and personal info."""
        # TODO: implement — ensure current_user is Athlete
        return render_template("athlete_dashboard.html")

    @app.route("/roster")
    @login_required
    def roster():
        """List athletes for the current coach/context."""
        # TODO: implement — filter by current_user (coach), pass athletes to template
        return render_template("roster.html")

    @app.route("/roster/add", methods=["GET", "POST"])
    @login_required
    def add_athlete():
        """Show form to add athlete (GET) or create athlete and persist (POST)."""
        # TODO: implement — validate form, create Athlete, redirect to roster or coach_dashboard
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
