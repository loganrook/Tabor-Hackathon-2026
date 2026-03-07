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
        if not isinstance(current_user, Coach):
            return redirect(url_for("athlete_dashboard"))
        teams = current_user.teams.all()
        return render_template("coach_dashboard.html", teams=teams)

    @app.route("/team/create", methods=["GET", "POST"])
    @login_required
    def create_team():
        """Show form to create team (GET) or create team and persist (POST)."""
        if not isinstance(current_user, Coach):
            return redirect(url_for("athlete_dashboard"))
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            if not name:
                flash("Team name is required.", "error")
                return render_template("team_create.html")
            team = Team(name=name, coach_id=current_user.id)
            db.session.add(team)
            db.session.commit()
            flash("Team created successfully.", "success")
            return redirect(url_for("coach_dashboard"))
        return render_template("team_create.html")

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
        if not isinstance(current_user, Coach):
            return redirect(url_for("athlete_dashboard"))
        team_ids = [t.id for t in current_user.teams.all()]
        athletes = Athlete.query.filter(Athlete.team_id.in_(team_ids)).all() if team_ids else []
        return render_template("roster.html", athletes=athletes)

    @app.route("/roster/add", methods=["GET", "POST"])
    @login_required
    def add_athlete():
        """Show form to add athlete (GET) or create athlete and persist (POST)."""
        if not isinstance(current_user, Coach):
            return redirect(url_for("athlete_dashboard"))
        teams = current_user.teams.all()
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip()
            password = request.form.get("password", "")
            team_id = request.form.get("team_id", type=int)
            if not name or not email or not password or not team_id:
                flash("Name, email, password, and team are required.", "error")
                return render_template("add_athlete.html", teams=teams)
            team = Team.query.get(team_id)
            if not team or team.coach_id != current_user.id:
                flash("Invalid team.", "error")
                return render_template("add_athlete.html", teams=teams)
            if Athlete.query.filter_by(email=email).first():
                flash("An athlete with that email already exists.", "error")
                return render_template("add_athlete.html", teams=teams)
            athlete = Athlete(name=name, email=email, team_id=team_id)
            athlete.set_password(password)
            db.session.add(athlete)
            db.session.commit()
            flash("Athlete added successfully.", "success")
            return redirect(url_for("roster"))
        return render_template("add_athlete.html", teams=teams)

    with app.app_context():
        db.create_all()

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
