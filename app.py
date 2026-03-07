"""
app.py — Main Flask application and routing.

Purpose: Flask entry point; create app, register extensions, define routes.
Who works here: Backend / API.
Responsibilities: App creation, minimal request handling; keep business logic in models.
"""

from flask import Flask, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from email_validator import validate_email, EmailNotValidError
from config import Config
from extensions import db, login_manager

# Import models after extensions so db is available; registers models with Flask-SQLAlchemy
import calendar as cal_module
import time
from datetime import datetime, date

from validators import validate_password
from models import (  # noqa: E402, F401
    Coach,
    Athlete,
    Team,
    Assignment,
    Announcement,
    AssignmentStatus,
    Group,
)

# In-memory rate limit for failed logins: ip -> (attempt_count, block_until_timestamp)
_login_failures = {}


def create_app(config_class=Config):
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "login"
    login_manager.login_message = "Please log in to access this page."

    @app.template_filter("fmt_datetime")
    def fmt_datetime(dt):
        """Format datetime as 'March 7, 2026 at 11:59 PM' (12-hour, no leading zero on hour)."""
        if dt is None:
            return ""
        h = dt.hour % 12 or 12
        ampm = "AM" if dt.hour < 12 else "PM"
        return dt.strftime("%B %d, %Y at ") + f"{h}:{dt.minute:02d} {ampm}"

    @app.after_request
    def add_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        return response

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
        """Serve the homepage for guests; redirect logged-in users to dashboard."""
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        return render_template("home.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        """Show login form (GET) or authenticate and redirect (POST). Rate-limited by IP."""
        if request.method == "POST":
            ip = request.remote_addr or "0.0.0.0"
            now = time.time()
            count, block_until = _login_failures.get(ip, (0, 0))
            if block_until and now < block_until:
                flash("Too many failed attempts. Try again in a few minutes.", "error")
                return render_template("login.html")
            if block_until and now >= block_until:
                count, block_until = 0, 0
            email = request.form.get("email", "").strip()
            password = request.form.get("password", "")
            if not email or not password:
                flash("Email and password are required.", "error")
                return render_template("login.html")
            try:
                validate_email(email, check_deliverability=False)
            except EmailNotValidError:
                flash("Invalid email or password.", "error")
                return render_template("login.html")
            coach = Coach.query.filter_by(email=email).first()
            if coach and coach.check_password(password):
                _login_failures.pop(ip, None)
                login_user(coach)
                return redirect(url_for("dashboard"))
            athlete = Athlete.query.filter_by(email=email).first()
            if athlete and athlete.check_password(password):
                _login_failures.pop(ip, None)
                login_user(athlete)
                return redirect(url_for("dashboard"))
            count += 1
            block_until = (now + 300) if count >= 5 else 0
            _login_failures[ip] = (count, block_until)
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
                return render_template("register.html", role_param=request.form.get("role"))
            pw_errors = validate_password(password)
            if pw_errors:
                for msg in pw_errors:
                    flash(msg, "error")
                return render_template("register.html", role_param=request.form.get("role"))
            try:
                validate_email(email, check_deliverability=False)
            except EmailNotValidError:
                flash("Please enter a valid email address.", "error")
                return render_template("register.html", role_param=request.form.get("role"))
            if role == "coach":
                if Coach.query.filter_by(email=email).first():
                    flash("An account with that email already exists.", "error")
                    return render_template("register.html", role_param=request.form.get("role"))
                coach = Coach(name=name, email=email)
                coach.set_password(password)
                db.session.add(coach)
                db.session.commit()
                login_user(coach)
                flash("Account created. Welcome!", "success")
                return redirect(url_for("dashboard"))
            if role == "athlete":
                if Athlete.query.filter_by(email=email).first():
                    flash("An account with that email already exists.", "error")
                    return render_template("register.html", role_param=request.form.get("role"))
                athlete = Athlete(name=name, email=email)
                athlete.set_password(password)
                db.session.add(athlete)
                db.session.commit()
                login_user(athlete)
                flash("Account created. Welcome! Join a team from your dashboard.", "success")
                return redirect(url_for("dashboard"))
            flash("Please select coach or athlete.", "error")
            return render_template("register.html", role_param=request.form.get("role"))
        return render_template("register.html", role_param=request.args.get("role"))

    @app.route("/logout")
    def logout():
        """Clear session and redirect to homepage or login."""
        logout_user()
        return redirect(url_for("index"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        """Single dashboard for coaches and athletes: list of teams as cards."""
        teams = current_user.teams.all()
        is_coach = isinstance(current_user, Coach)
        return render_template(
            "dashboard.html",
            teams=teams,
            is_coach=is_coach,
        )

    @app.route("/team/create", methods=["GET", "POST"])
    @login_required
    def create_team():
        """Show form to create team (GET) or create team and persist (POST)."""
        if not isinstance(current_user, Coach):
            return redirect(url_for("dashboard"))
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
            return redirect(url_for("dashboard"))
        return render_template("team_create.html")

    @app.route("/team/join", methods=["GET", "POST"])
    @login_required
    def join_team():
        """Show form to join team by invite code (GET) or add athlete to team (POST)."""
        if not isinstance(current_user, Athlete):
            return redirect(url_for("dashboard"))
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
                return redirect(url_for("dashboard"))
            team.athletes.append(current_user)
            db.session.commit()
            flash("You have joined the team.", "success")
            return redirect(url_for("dashboard"))
        return render_template("join_team.html")

    @app.route("/team/<int:team_id>/settings", methods=["GET", "POST"])
    @login_required
    def team_settings(team_id):
        """Coach only: invite code, edit team name, manage groups, delete team."""
        team = Team.query.get_or_404(team_id)
        if not isinstance(current_user, Coach) or team.coach_id != current_user.id:
            flash("You do not have access to team settings.", "error")
            return redirect(url_for("dashboard"))
        if request.method == "POST":
            action = request.form.get("action")
            if action == "update_name":
                name = request.form.get("name", "").strip()
                if name:
                    team.name = name
                    db.session.commit()
                    flash("Team name updated.", "success")
                return redirect(url_for("team_settings", team_id=team_id))
            if action == "delete_team":
                # Delete in order: AssignmentStatus -> Assignment -> Announcement -> Groups -> Team
                for assignment in team.assignments.all():
                    for status in assignment.statuses.all():
                        db.session.delete(status)
                    db.session.delete(assignment)
                for ann in team.announcements.all():
                    db.session.delete(ann)
                for group in list(team.groups.all()):
                    group.athletes = []
                    db.session.delete(group)
                team.athletes = []
                db.session.delete(team)
                db.session.commit()
                flash("Team deleted.", "success")
                return redirect(url_for("dashboard"))
        groups = team.groups.order_by(Group.name).all()
        return render_template(
            "team_settings.html",
            team=team,
            groups=groups,
        )

    @app.route("/team/<int:team_id>")
    @login_required
    def team_dashboard(team_id):
        """Team dashboard: announcements, assignments, completion stats (coach) or statuses (athlete)."""
        team = Team.query.get_or_404(team_id)
        if not _user_can_access_team(team):
            flash("You do not have access to this team.", "error")
            if isinstance(current_user, Coach):
                return redirect(url_for("dashboard"))
            return redirect(url_for("dashboard"))
        athletes = team.athletes.all()
        groups = team.groups.order_by(Group.name).all()
        all_announcements = (
            team.announcements.order_by(Announcement.created_at.desc()).limit(50).all()
        )
        all_assignments = (
            Assignment.query.filter_by(team_id=team_id)
            .order_by(Assignment.created_at.desc())
            .all()
        )
        is_coach = isinstance(current_user, Coach) and team.coach_id == current_user.id

        # Athlete: only see team-wide, group (they're in), or individual (assigned to them)
        if is_coach:
            assignments = all_assignments
        else:
            athlete_group_ids = {
                g.id for g in current_user.groups.filter(Group.team_id == team_id).all()
            }
            assignments = [
                a
                for a in all_assignments
                if a.athlete_id == current_user.id
                or a.group_id is None
                or a.group_id in athlete_group_ids
            ]
            announcements = [
                ann
                for ann in all_announcements
                if ann.group_id is None or ann.group_id in athlete_group_ids
            ]
        if is_coach:
            announcements = all_announcements

        # Coach: completion counts per assignment (completed, total)
        # Athlete: their AssignmentStatus per assignment
        assignment_completion = {}
        assignment_status_by_athlete = {}
        for a in assignments:
            if is_coach:
                total = a.statuses.count()
                completed = a.statuses.filter_by(completed=True).count()
                assignment_completion[a.id] = (completed, total)
            else:
                status = (
                    AssignmentStatus.query.filter_by(
                        assignment_id=a.id, athlete_id=current_user.id
                    ).first()
                )
                assignment_status_by_athlete[a.id] = status

        # Sidebar groups: coach sees all, athlete sees only groups they belong to
        if is_coach:
            sidebar_groups = groups
        else:
            athlete_group_ids = {
                g.id for g in current_user.groups.filter(Group.team_id == team_id).all()
            }
            sidebar_groups = [g for g in groups if g.id in athlete_group_ids]

        # Calendar: current month, days with due dates
        today = date.today()
        cal_year = today.year
        cal_month = today.month
        first_day = date(cal_year, cal_month, 1)
        days_in_month = cal_module.monthrange(cal_year, cal_month)[1]
        first_weekday = first_day.weekday()
        assignment_due_days = set()
        for a in assignments:
            if (
                a.due_date
                and a.due_date.year == cal_year
                and a.due_date.month == cal_month
            ):
                assignment_due_days.add(a.due_date.day)

        return render_template(
            "team_dashboard.html",
            team=team,
            athletes=athletes,
            groups=groups,
            sidebar_groups=sidebar_groups,
            announcements=announcements,
            assignments=assignments,
            is_coach=is_coach,
            assignment_completion=assignment_completion,
            assignment_status_by_athlete=assignment_status_by_athlete,
            cal_year=cal_year,
            cal_month=cal_month,
            days_in_month=days_in_month,
            first_weekday=first_weekday,
            cal_today=today.day,
            assignment_due_days=assignment_due_days,
            cal_month_name=cal_module.month_name[cal_month],
        )

    @app.route("/team/<int:team_id>/announce", methods=["POST"])
    @login_required
    def team_announce(team_id):
        """Coach only: create an announcement for the team. Redirect to team dashboard."""
        team = Team.query.get_or_404(team_id)
        if not isinstance(current_user, Coach) or team.coach_id != current_user.id:
            flash("You cannot post announcements for this team.", "error")
            return redirect(url_for("dashboard"))
        content = request.form.get("content", "").strip()
        announce_to = request.form.get("announce_to", "").strip()
        group_id = None
        if not content:
            flash("Announcement cannot be empty.", "error")
            return redirect(url_for("team_dashboard", team_id=team_id))
        if announce_to.startswith("g"):
            try:
                raw_id = int(announce_to[1:])
                group = Group.query.filter_by(id=raw_id, team_id=team_id).first()
                if group:
                    group_id = group.id
            except (TypeError, ValueError):
                group_id = None
        ann = Announcement(
            content=content,
            team_id=team_id,
            group_id=group_id,
            created_by=current_user.id,
        )
        db.session.add(ann)
        db.session.commit()
        flash("Announcement posted.", "success")
        return redirect(url_for("team_dashboard", team_id=team_id))

    @app.route("/team/<int:team_id>/group/create", methods=["GET", "POST"])
    @login_required
    def create_group(team_id):
        """Coach only: create a new group for the team."""
        team = Team.query.get_or_404(team_id)
        if not isinstance(current_user, Coach) or team.coach_id != current_user.id:
            flash("You cannot create groups for this team.", "error")
            return redirect(url_for("dashboard"))
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            if not name:
                flash("Group name is required.", "error")
                return render_template("group_create.html", team=team)
            group = Group(name=name, team_id=team_id)
            db.session.add(group)
            db.session.commit()
            flash("Group created.", "success")
            return redirect(url_for("team_groups", team_id=team_id))
        return render_template("group_create.html", team=team)

    @app.route("/team/<int:team_id>/groups")
    @login_required
    def team_groups(team_id):
        """List all groups for the team. Same layout as dashboard/roster."""
        team = Team.query.get_or_404(team_id)
        if not _user_can_access_team(team):
            flash("You do not have access to this team.", "error")
            return redirect(url_for("dashboard"))
        groups = team.groups.order_by(Group.name).all()
        is_coach = isinstance(current_user, Coach) and team.coach_id == current_user.id
        return render_template(
            "team_groups.html",
            team=team,
            groups=groups,
            is_coach=is_coach,
        )

    @app.route("/team/<int:team_id>/group/<int:group_id>/delete", methods=["POST"])
    @login_required
    def delete_group(team_id, group_id):
        """Coach only: delete a group."""
        team = Team.query.get_or_404(team_id)
        group = Group.query.filter_by(id=group_id, team_id=team_id).first_or_404()
        if not isinstance(current_user, Coach) or team.coach_id != current_user.id:
            flash("You cannot delete this group.", "error")
            return redirect(url_for("dashboard"))
        group.athletes = []
        db.session.delete(group)
        db.session.commit()
        flash("Group deleted.", "success")
        return redirect(url_for("team_groups", team_id=team_id))

    @app.route("/team/<int:team_id>/group/<int:group_id>/manage", methods=["GET", "POST"])
    @login_required
    def manage_group(team_id, group_id):
        """Coach only: update which athletes are in the group."""
        team = Team.query.get_or_404(team_id)
        group = Group.query.filter_by(id=group_id, team_id=team_id).first_or_404()
        if not isinstance(current_user, Coach) or team.coach_id != current_user.id:
            flash("You cannot manage this group.", "error")
            return redirect(url_for("dashboard"))
        athletes = team.athletes.all()
        if request.method == "POST":
            selected_ids = set(request.form.getlist("athlete_id"))
            group.athletes = [a for a in athletes if str(a.id) in selected_ids]
            db.session.commit()
            flash("Group updated.", "success")
            return redirect(url_for("team_groups", team_id=team_id))
        group_member_ids = {a.id for a in group.athletes.all()}
        return render_template(
            "group_manage.html",
            team=team,
            group=group,
            athletes=athletes,
            group_member_ids=group_member_ids,
        )

    @app.route("/team/<int:team_id>/roster")
    @login_required
    def team_roster(team_id):
        """Roster for a specific team. Coach or athlete with access."""
        team = Team.query.get_or_404(team_id)
        if not _user_can_access_team(team):
            flash("You do not have access to this team.", "error")
            return redirect(url_for("dashboard"))
        athletes = team.athletes.all()
        is_coach = isinstance(current_user, Coach) and team.coach_id == current_user.id
        return render_template(
            "team_roster.html",
            team=team,
            athletes=athletes,
            is_coach=is_coach,
        )

    @app.route("/team/<int:team_id>/roster/remove", methods=["POST"])
    @login_required
    def roster_remove(team_id):
        """Coach only: remove an athlete from the team."""
        team = Team.query.get_or_404(team_id)
        if not isinstance(current_user, Coach) or team.coach_id != current_user.id:
            flash("You cannot remove athletes from this team.", "error")
            return redirect(url_for("dashboard"))
        athlete_id = request.form.get("athlete_id", type=int)
        if not athlete_id:
            flash("Invalid request.", "error")
            return redirect(url_for("team_roster", team_id=team_id))
        athlete = Athlete.query.get(athlete_id)
        if not athlete or athlete not in team.athletes.all():
            flash("Athlete not on this team.", "error")
            return redirect(url_for("team_roster", team_id=team_id))
        team.athletes.remove(athlete)
        for group in team.groups.all():
            if athlete in group.athletes.all():
                group.athletes.remove(athlete)
        for assignment in team.assignments.all():
            AssignmentStatus.query.filter_by(
                assignment_id=assignment.id, athlete_id=athlete_id
            ).delete()
        db.session.commit()
        flash("Athlete removed from team.", "success")
        return redirect(url_for("team_roster", team_id=team_id))

    @app.route("/team/<int:team_id>/assignment/create", methods=["GET", "POST"])
    @login_required
    def create_team_assignment(team_id):
        """Coach-only: create an assignment for this team; create AssignmentStatus for each athlete."""
        team = Team.query.get_or_404(team_id)
        if not isinstance(current_user, Coach) or team.coach_id != current_user.id:
            flash("You cannot create assignments for this team.", "error")
            return redirect(url_for("dashboard"))
        if request.method == "POST":
            title = request.form.get("title", "").strip()
            description = request.form.get("description", "").strip() or None
            due_date = None
            due_str = request.form.get("due_date", "").strip()
            if due_str:
                try:
                    due_date = datetime.strptime(due_str, "%Y-%m-%d").replace(
                        hour=23, minute=59, second=0, microsecond=0
                    )
                except ValueError:
                    pass
            assign_to = request.form.get("assign_to", "").strip()
            group_id = None
            athlete_id = None
            if assign_to.startswith("g"):
                try:
                    group_id = int(assign_to[1:])
                    g = Group.query.filter_by(id=group_id, team_id=team_id).first()
                    if not g:
                        group_id = None
                except (ValueError, TypeError):
                    group_id = None
            elif assign_to.startswith("a"):
                try:
                    athlete_id = int(assign_to[1:])
                    ath = Athlete.query.get(athlete_id)
                    if not ath or not ath.teams.filter(Team.id == team_id).first():
                        athlete_id = None
                except (ValueError, TypeError):
                    athlete_id = None
            if not title:
                flash("Title is required.", "error")
                return render_template(
                    "create_assignment.html",
                    team=team,
                    groups=team.groups.order_by(Group.name).all(),
                    athletes=team.athletes.order_by(Athlete.name).all(),
                )
            assignment = Assignment(
                title=title,
                description=description,
                due_date=due_date,
                team_id=team_id,
                group_id=group_id if not athlete_id else None,
                athlete_id=athlete_id,
                created_by=current_user.id,
            )
            db.session.add(assignment)
            db.session.flush()
            if athlete_id:
                target_athletes = [Athlete.query.get(athlete_id)]
            elif group_id:
                group = Group.query.get(group_id)
                target_athletes = group.athletes.all()
            else:
                target_athletes = team.athletes.all()
            for athlete in target_athletes:
                status = AssignmentStatus(
                    assignment_id=assignment.id,
                    athlete_id=athlete.id,
                    completed=False,
                )
                db.session.add(status)
            db.session.commit()
            flash("Assignment created.", "success")
            return redirect(url_for("team_dashboard", team_id=team_id))
        return render_template(
            "create_assignment.html",
            team=team,
            groups=team.groups.order_by(Group.name).all(),
            athletes=team.athletes.order_by(Athlete.name).all(),
        )

    @app.route("/assignment/<int:assignment_id>/complete", methods=["POST"])
    @login_required
    def assignment_complete(assignment_id):
        """Athlete only: mark their AssignmentStatus as completed. Create status if missing (joined later)."""
        if not isinstance(current_user, Athlete):
            flash("Only athletes can complete assignments.", "error")
            return redirect(url_for("dashboard"))
        assignment = Assignment.query.get_or_404(assignment_id)
        if not _user_can_access_team(assignment.team):
            flash("You do not have access to this team.", "error")
            return redirect(url_for("dashboard"))
        status = AssignmentStatus.query.filter_by(
            assignment_id=assignment_id,
            athlete_id=current_user.id,
        ).first()
        if not status:
            status = AssignmentStatus(
                assignment_id=assignment_id,
                athlete_id=current_user.id,
                completed=True,
                completed_at=datetime.now(),
            )
            db.session.add(status)
        else:
            status.completed = True
            status.completed_at = datetime.now()
        db.session.commit()
        flash("Assignment marked complete.", "success")
        return redirect(url_for("team_dashboard", team_id=assignment.team_id))

    @app.route("/assignment/<int:assignment_id>/uncomplete", methods=["POST"])
    @login_required
    def assignment_uncomplete(assignment_id):
        """Athlete only: undo their own completion of an assignment."""
        if not isinstance(current_user, Athlete):
            flash("Only athletes can undo assignment completion.", "error")
            return redirect(url_for("dashboard"))
        assignment = Assignment.query.get_or_404(assignment_id)
        if not _user_can_access_team(assignment.team):
            flash("You do not have access to this team.", "error")
            return redirect(url_for("dashboard"))
        status = AssignmentStatus.query.filter_by(
            assignment_id=assignment_id,
            athlete_id=current_user.id,
        ).first()
        if status and status.completed:
            status.completed = False
            status.completed_at = None
            db.session.commit()
            flash("Assignment completion undone.", "success")
        else:
            flash("Nothing to undo.", "info")
        return redirect(url_for("team_dashboard", team_id=assignment.team_id))

    def _coach_owns_team(team):
        """Return True if current_user is the coach who owns the team."""
        return (
            current_user.is_authenticated
            and isinstance(current_user, Coach)
            and team
            and team.coach_id == current_user.id
        )

    @app.route("/assignment/<int:assignment_id>/edit", methods=["GET", "POST"])
    @login_required
    def edit_assignment(assignment_id):
        """Coach only: edit assignment; on POST update and auto-announce."""
        assignment = Assignment.query.get_or_404(assignment_id)
        team = assignment.team
        if not _coach_owns_team(team):
            flash("You cannot edit this assignment.", "error")
            return redirect(url_for("dashboard"))
        if request.method == "POST":
            title = request.form.get("title", "").strip()
            description = request.form.get("description", "").strip() or None
            due_date = None
            due_str = request.form.get("due_date", "").strip()
            if due_str:
                try:
                    due_date = datetime.strptime(due_str, "%Y-%m-%d").replace(
                        hour=23, minute=59, second=0, microsecond=0
                    )
                except ValueError:
                    pass
            assign_to = request.form.get("assign_to", "").strip()
            group_id = None
            athlete_id = None
            if assign_to.startswith("g"):
                try:
                    group_id = int(assign_to[1:])
                    g = Group.query.filter_by(id=group_id, team_id=team.id).first()
                    if not g:
                        group_id = None
                except (ValueError, TypeError):
                    group_id = None
            elif assign_to.startswith("a"):
                try:
                    athlete_id = int(assign_to[1:])
                    ath = Athlete.query.get(athlete_id)
                    if not ath or not ath.teams.filter(Team.id == team.id).first():
                        athlete_id = None
                except (ValueError, TypeError):
                    athlete_id = None
            if not title:
                flash("Title is required.", "error")
                return render_template(
                    "edit_assignment.html",
                    assignment=assignment,
                    team=team,
                    groups=team.groups.order_by(Group.name).all(),
                    athletes=team.athletes.order_by(Athlete.name).all(),
                )
            assignment.title = title
            assignment.description = description
            assignment.due_date = due_date
            assignment.group_id = group_id if not athlete_id else None
            assignment.athlete_id = athlete_id
            db.session.commit()
            auto_ann = Announcement(
                content=f"{current_user.name} updated assignment: {assignment.title}",
                team_id=team.id,
                created_by=current_user.id,
                is_auto=True,
            )
            db.session.add(auto_ann)
            db.session.commit()
            flash("Assignment updated.", "success")
            return redirect(url_for("team_dashboard", team_id=team.id))
        return render_template(
            "edit_assignment.html",
            assignment=assignment,
            team=team,
            groups=team.groups.order_by(Group.name).all(),
            athletes=team.athletes.order_by(Athlete.name).all(),
        )

    @app.route("/assignment/<int:assignment_id>/delete", methods=["POST"])
    @login_required
    def delete_assignment(assignment_id):
        """Coach only: delete assignment and its statuses; auto-announce removal."""
        assignment = Assignment.query.get_or_404(assignment_id)
        team = assignment.team
        if not _coach_owns_team(team):
            flash("You cannot delete this assignment.", "error")
            return redirect(url_for("dashboard"))
        title = assignment.title
        AssignmentStatus.query.filter_by(assignment_id=assignment_id).delete()
        db.session.delete(assignment)
        auto_ann = Announcement(
            content=f"{current_user.name} removed assignment: {title}",
            team_id=team.id,
            created_by=current_user.id,
            is_auto=True,
        )
        db.session.add(auto_ann)
        db.session.commit()
        flash("Assignment deleted.", "success")
        return redirect(url_for("team_dashboard", team_id=team.id))

    @app.route("/announcement/<int:announcement_id>/edit", methods=["GET", "POST"])
    @login_required
    def edit_announcement(announcement_id):
        """Coach only: edit announcement content; on POST update and auto-announce."""
        ann = Announcement.query.get_or_404(announcement_id)
        team = ann.team
        if not _coach_owns_team(team):
            flash("You cannot edit this announcement.", "error")
            return redirect(url_for("dashboard"))
        if request.method == "POST":
            content = request.form.get("content", "").strip()
            if not content:
                flash("Announcement cannot be empty.", "error")
                return render_template("edit_announcement.html", announcement=ann, team=team)
            ann.content = content
            db.session.commit()
            auto_ann = Announcement(
                content=f"{current_user.name} edited an announcement",
                team_id=team.id,
                created_by=current_user.id,
                is_auto=True,
            )
            db.session.add(auto_ann)
            db.session.commit()
            flash("Announcement updated.", "success")
            return redirect(url_for("team_dashboard", team_id=team.id))
        return render_template("edit_announcement.html", announcement=ann, team=team)

    @app.route("/announcement/<int:announcement_id>/delete", methods=["POST"])
    @login_required
    def delete_announcement(announcement_id):
        """Coach only: delete announcement. No auto-announcement for delete."""
        ann = Announcement.query.get_or_404(announcement_id)
        team = ann.team
        if not _coach_owns_team(team):
            flash("You cannot delete this announcement.", "error")
            return redirect(url_for("dashboard"))
        db.session.delete(ann)
        db.session.commit()
        flash("Announcement deleted.", "success")
        return redirect(url_for("team_dashboard", team_id=team.id))

    with app.app_context():
        db.create_all()

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
