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
from models import Coach, Athlete, Team, Assignment  # noqa: E402, F401


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

    def _user_can_access_team(team):
        """Return True if current_user is the coach of this team or an athlete in it."""
        if not team or not current_user.is_authenticated:
            return False
        if isinstance(current_user, Coach) and team.coach_id == current_user.id:
            return True
        if isinstance(current_user, Athlete):
            return current_user.teams.filter(Team.id == team.id).first() is not None
        return False

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

    @app.route("/register", methods=["GET", "POST"])
    def register():
        """Show registration form (GET) or create Coach/Athlete and log in (POST)."""
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip()
            password = request.form.get("password", "")
            role = request.form.get("role", "").strip().lower()
            if not name or not email or not password:
                flash("Name, email, and password are required.", "error")
                return render_template("register.html")
            if role == "coach":
                if Coach.query.filter_by(email=email).first():
                    flash("An account with that email already exists.", "error")
                    return render_template("register.html")
                coach = Coach(name=name, email=email)
                coach.set_password(password)
                db.session.add(coach)
                db.session.commit()
                login_user(coach)
                flash("Account created. Welcome!", "success")
                return redirect(url_for("coach_dashboard"))
            if role == "athlete":
                if Athlete.query.filter_by(email=email).first():
                    flash("An account with that email already exists.", "error")
                    return render_template("register.html")
                athlete = Athlete(name=name, email=email)
                athlete.set_password(password)
                db.session.add(athlete)
                db.session.commit()
                login_user(athlete)
                flash("Account created. Welcome! Join a team from your dashboard.", "success")
                return redirect(url_for("athlete_dashboard"))
            flash("Please select coach or athlete.", "error")
            return render_template("register.html")
        return render_template("register.html")

    @app.route("/logout")
    def logout():
        """Clear session and redirect to homepage or login."""
        logout_user()
        return redirect(url_for("index"))

    @app.route("/team/<int:team_id>")
    @login_required
    def team_dashboard(team_id):
        """Team dashboard: team name, roster, assignments. Coach sees edit links; athlete read-only."""
        team = Team.query.get_or_404(team_id)
        if not _user_can_access_team(team):
            flash("You do not have access to this team.", "error")
            if isinstance(current_user, Coach):
                return redirect(url_for("coach_dashboard"))
            return redirect(url_for("athlete_dashboard"))
        athletes = team.athletes.all()
        assignments = (
            Assignment.query.filter_by(team_id=team_id)
            .order_by(Assignment.created_at.desc())
            .all()
        )
        is_coach = isinstance(current_user, Coach) and team.coach_id == current_user.id
        return render_template(
            "team_dashboard.html",
            team=team,
            athletes=athletes,
            assignments=assignments,
            is_coach=is_coach,
        )

    @app.route("/coach/dashboard")
    @login_required
    def coach_dashboard():
        """Coach dashboard: list of teams as cards/links. Redirect to team if only one."""
        if not isinstance(current_user, Coach):
            return redirect(url_for("athlete_dashboard"))
        teams = current_user.teams.all()
        if len(teams) == 1:
            return redirect(url_for("team_dashboard", team_id=teams[0].id))
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
            team = Team(
                name=name,
                coach_id=current_user.id,
                invite_code=Team.generate_invite_code(),
            )
            db.session.add(team)
            db.session.commit()
            flash("Team created successfully.", "success")
            return redirect(url_for("coach_dashboard"))
        return render_template("team_create.html")

    @app.route("/athlete/dashboard")
    @login_required
    def athlete_dashboard():
        """Athlete dashboard: list of teams as cards/links. Redirect to team if only one."""
        if not isinstance(current_user, Athlete):
            return redirect(url_for("coach_dashboard"))
        teams = current_user.teams.all()
        if len(teams) == 1:
            return redirect(url_for("team_dashboard", team_id=teams[0].id))
        return render_template("athlete_dashboard.html", teams=teams)

    @app.route("/team/<int:team_id>/roster")
    @login_required
    def team_roster(team_id):
        """Roster for a specific team. Coach or athlete with access."""
        team = Team.query.get_or_404(team_id)
        if not _user_can_access_team(team):
            flash("You do not have access to this team.", "error")
            if isinstance(current_user, Coach):
                return redirect(url_for("coach_dashboard"))
            return redirect(url_for("athlete_dashboard"))
        athletes = team.athletes.all()
        is_coach = isinstance(current_user, Coach) and team.coach_id == current_user.id
        return render_template(
            "team_roster.html",
            team=team,
            athletes=athletes,
            is_coach=is_coach,
        )

    @app.route("/roster")
    @login_required
    def roster():
        """List athletes for the current coach/context (across all coach's teams)."""
        if not isinstance(current_user, Coach):
            return redirect(url_for("athlete_dashboard"))
        athletes = (
            Athlete.query.filter(Athlete.teams.any(Team.coach_id == current_user.id))
            .distinct()
            .all()
        )
        team_names_by_athlete = {
            a.id: [t.name for t in a.teams if t.coach_id == current_user.id]
            for a in athletes
        }
        return render_template(
            "roster.html",
            athletes=athletes,
            team_names_by_athlete=team_names_by_athlete,
        )

    @app.route("/team/join", methods=["GET", "POST"])
    @login_required
    def join_team():
        """Show form to join team by invite code (GET) or add athlete to team (POST)."""
        if not isinstance(current_user, Athlete):
            return redirect(url_for("coach_dashboard"))
        if request.method == "POST":
            code = request.form.get("invite_code", "").strip().upper()
            if not code:
                flash("Please enter an invite code.", "error")
                return render_template("join_team.html")
            team = Team.query.filter_by(invite_code=code).first()
            if not team:
                flash("Invalid or unknown invite code.", "error")
                return render_template("join_team.html")
            if current_user.teams.filter(Team.id == team.id).first():
                flash("You are already on this team.", "info")
                return redirect(url_for("athlete_dashboard"))
            team.athletes.append(current_user)
            db.session.commit()
            flash("You have joined the team.", "success")
            return redirect(url_for("athlete_dashboard"))
        return render_template("join_team.html")

    @app.route("/team/<int:team_id>/assignment/create", methods=["GET", "POST"])
    @login_required
    def create_team_assignment(team_id):
        """Coach-only: create an assignment for this team. Redirects to team dashboard."""
        team = Team.query.get_or_404(team_id)
        if not isinstance(current_user, Coach) or team.coach_id != current_user.id:
            flash("You cannot create assignments for this team.", "error")
            return redirect(url_for("coach_dashboard"))
        if request.method == "POST":
            title = request.form.get("title", "").strip()
            description = request.form.get("description", "").strip() or None
            if not title:
                flash("Title is required.", "error")
                return render_template("create_assignment.html", team=team)
            assignment = Assignment(
                title=title,
                description=description,
                team_id=team_id,
                created_by=current_user.id,
            )
            db.session.add(assignment)
            db.session.commit()
            flash("Assignment created.", "success")
            return redirect(url_for("team_dashboard", team_id=team_id))
        return render_template("create_assignment.html", team=team)

    @app.route("/assignments")
    @login_required
    def list_assignments():
        """Coach-only: list all assignments across the coach's teams."""
        if not isinstance(current_user, Coach):
            return redirect(url_for("athlete_dashboard"))
        team_ids = [t.id for t in current_user.teams.all()]
        assignments = (
            Assignment.query.filter(Assignment.team_id.in_(team_ids))
            .order_by(Assignment.created_at.desc())
            .all()
        )
        return render_template("assignments_list.html", assignments=assignments)

    with app.app_context():
        db.create_all()

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
