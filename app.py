"""
app.py — Main Flask application and routing.

Purpose: Flask entry point; create app, register extensions, define routes.
Who works here: Backend / API.
Responsibilities: App creation, minimal request handling; keep business logic in models.
"""

from flask import Flask, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from email_validator import validate_email, EmailNotValidError
from config import Config
from extensions import db, login_manager

# Import models after extensions so db is available; registers models with Flask-SQLAlchemy
import calendar as cal_module
import time
import json
from datetime import datetime, date

from validators import validate_password
from seed_demo import ensure_demo_data
from models import (  # noqa: E402, F401
    Coach,
    Athlete,
    Team,
    Announcement,
    Group,
    Workout,
    Exercise,
    ExerciseStatus,
    DirectMessage,
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

    @app.context_processor
    def inject_unread_dm_count():
        """Inject unread direct message count for coaches into all templates."""
        unread_dm_count = 0
        if current_user.is_authenticated and isinstance(current_user, Coach):
            unread_dm_count = (
                DirectMessage.query.filter_by(
                    coach_id=current_user.id,
                    sender_role="athlete",
                    read_by_coach=False,
                ).count()
            )
        return {"unread_dm_count": unread_dm_count}

    def _user_can_access_team(team):
        """Return True if current_user is a coach (head or joined) on this team or an athlete in it."""
        if not team or not current_user.is_authenticated:
            return False
        if isinstance(current_user, Coach):
            # Head coach for this team
            if team.coach_id == current_user.id:
                return True
            # Joined/staff coach on this team
            if team.coaches.filter(Coach.id == current_user.id).first() is not None:
                return True
        if isinstance(current_user, Athlete):
            return current_user.teams.filter(Team.id == team.id).first() is not None
        return False

    def _is_head_coach(team):
        """Return True if current_user is the owning (head) coach for this team."""
        return (
            current_user.is_authenticated
            and isinstance(current_user, Coach)
            and team is not None
            and team.coach_id == current_user.id
        )

    def _get_workout_completion_breakdown(team, workout):
        """Return (completed_athletes, not_completed_athletes) lists for a workout."""
        exercises = workout.exercises.all()
        exercise_ids = [ex.id for ex in exercises]
        if not exercise_ids:
            return [], []

        statuses = ExerciseStatus.query.filter(
            ExerciseStatus.exercise_id.in_(exercise_ids)
        ).all()

        per_athlete = {}
        for status in statuses:
            bucket = per_athlete.setdefault(
                status.athlete_id,
                {
                    "athlete": status.athlete,
                    "statuses": [],
                },
            )
            bucket["statuses"].append(status)

        completed_athletes = []
        not_completed_athletes = []

        for athlete_id, data in per_athlete.items():
            sts = data["statuses"]
            total = len(sts)
            completed_count = sum(1 for s in sts if s.completed)
            last_completed_at = max(
                (s.completed_at for s in sts if s.completed_at), default=None
            )
            athlete = data["athlete"]
            groups = (
                athlete.groups.filter(Group.team_id == team.id)
                .order_by(Group.name)
                .all()
            )
            if groups:
                group_label = ", ".join(g.name for g in groups)
            else:
                group_label = "Entire Team"

            record = {
                "athlete": athlete,
                "group_label": group_label,
                "completed_exercises": completed_count,
                "total_exercises": total,
                "completed": total > 0 and completed_count == total,
                "completed_at": last_completed_at,
            }
            if record["completed"]:
                completed_athletes.append(record)
            else:
                not_completed_athletes.append(record)

        completed_athletes.sort(
            key=lambda r: (
                r["completed_at"] or datetime.min,
                r["athlete"].name.lower(),
            ),
            reverse=True,
        )
        not_completed_athletes.sort(key=lambda r: r["athlete"].name.lower())

        return completed_athletes, not_completed_athletes

    # ---------- Routes ----------

    @app.route("/")
    def index():
        """Serve the homepage for guests; redirect logged-in users to dashboard."""
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        return render_template("home.html", role_param=request.args.get("role"))

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
        is_coach = isinstance(current_user, Coach)
        if is_coach:
            owned = current_user.teams.all()
            joined = current_user.joined_teams.all() if hasattr(current_user, "joined_teams") else []
            # Deduplicate by id while preserving insertion order (owned first, then joined)
            combined = []
            seen_ids = set()
            for t in owned + joined:
                if t.id not in seen_ids:
                    combined.append(t)
                    seen_ids.add(t.id)
            teams = combined
        else:
            teams = current_user.teams.all()
        return render_template(
            "dashboard.html",
            teams=teams,
            is_coach=is_coach,
        )

    @app.route("/profile", methods=["GET", "POST"])
    @login_required
    def profile():
        """Profile/settings for the current user (coach or athlete)."""
        user = current_user
        role = "Coach" if isinstance(user, Coach) else "Athlete"
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            if not name:
                flash("Name is required.", "error")
            else:
                user.name = name
                db.session.commit()
                flash("Profile updated.", "success")
                return redirect(url_for("profile"))
        return render_template("profile.html", user=user, role=role)

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
        """Show form to join team by invite code (GET) or add user to team (POST)."""
        if request.method == "POST":
            code = request.form.get("invite_code", "").strip().upper()
            if not code:
                flash("Please enter an invite code.", "error")
                return render_template("join_team.html", invite_code=request.form.get("invite_code", ""))
            team = Team.query.filter_by(invite_code=code).first()
            if not team:
                flash("Invalid or unknown invite code.", "error")
                return render_template("join_team.html", invite_code=request.form.get("invite_code", ""))
            # Athlete joins as player
            if isinstance(current_user, Athlete):
                if current_user.teams.filter(Team.id == team.id).first():
                    flash("You are already on this team.", "info")
                    return redirect(url_for("dashboard"))
                team.athletes.append(current_user)
                db.session.commit()
                flash("You have joined the team.", "success")
                return redirect(url_for("dashboard"))
            # Coach joins as staff coach
            if isinstance(current_user, Coach):
                if team.coach_id == current_user.id:
                    flash("You are already the head coach of this team.", "info")
                    return redirect(url_for("dashboard"))
                if team.coaches.filter(Coach.id == current_user.id).first() is not None:
                    flash("You are already a coach on this team.", "info")
                    return redirect(url_for("dashboard"))
                team.coaches.append(current_user)
                db.session.commit()
                flash("You have joined this team as a coach.", "success")
                return redirect(url_for("dashboard"))
            # Fallback: unsupported user type
            flash("You cannot join this team with this account type.", "error")
            return redirect(url_for("dashboard"))
        return render_template("join_team.html", invite_code="")

    @app.route("/team/<int:team_id>/settings", methods=["GET", "POST"])
    @login_required
    def team_settings(team_id):
        """Coach only: invite code, edit team name, delete team."""
        team = Team.query.get_or_404(team_id)
        if not _is_head_coach(team):
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
                # Delete in order: Workouts (cascade to exercises/statuses) -> Announcement -> Groups -> Team
                for workout in team.workouts.all():
                    db.session.delete(workout)
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
        return render_template("team_settings.html", team=team)

    @app.route("/team/<int:team_id>")
    @login_required
    def team_dashboard(team_id):
        """Team dashboard: announcements, workouts, and completion stats."""
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
        all_workouts = (
            Workout.query.filter_by(team_id=team_id)
            .order_by(Workout.created_at.desc())
            .all()
        )
        is_coach = isinstance(current_user, Coach) and team.coach_id == current_user.id

        # Athlete: only see team-wide workouts or group workouts (they're in)
        if is_coach:
            workouts = all_workouts
        else:
            athlete_group_ids = {
                g.id for g in current_user.groups.filter(Group.team_id == team_id).all()
            }
            workouts = [
                w
                for w in all_workouts
                if w.group_id is None or w.group_id in athlete_group_ids
            ]
            announcements = [
                ann
                for ann in all_announcements
                if ann.group_id is None or ann.group_id in athlete_group_ids
            ]
        if is_coach:
            announcements = all_announcements

        # Coach: completion counts per workout (completed, total exercise statuses)
        # Athlete: their exercise completion counts per workout
        workout_completion = {}
        workout_status_by_athlete = {}
        for w in workouts:
            if is_coach:
                total = (
                    ExerciseStatus.query.join(Exercise)
                    .filter(Exercise.workout_id == w.id)
                    .count()
                )
                completed = (
                    ExerciseStatus.query.join(Exercise)
                    .filter(
                        Exercise.workout_id == w.id,
                        ExerciseStatus.completed.is_(True),
                    )
                    .count()
                )
                workout_completion[w.id] = (completed, total)
            else:
                total_exercises = Exercise.query.filter_by(workout_id=w.id).count()
                completed_exercises = (
                    ExerciseStatus.query.join(Exercise)
                    .filter(
                        Exercise.workout_id == w.id,
                        ExerciseStatus.athlete_id == current_user.id,
                        ExerciseStatus.completed.is_(True),
                    )
                    .count()
                )
                workout_status_by_athlete[w.id] = (completed_exercises, total_exercises)

        # Sidebar groups: coach sees all, athlete sees only groups they belong to
        if is_coach:
            sidebar_groups = groups
        else:
            athlete_group_ids = {
                g.id for g in current_user.groups.filter(Group.team_id == team_id).all()
            }
            sidebar_groups = [g for g in groups if g.id in athlete_group_ids]

        # Calendar: current month, days with workout due dates
        today = date.today()
        cal_year = today.year
        cal_month = today.month
        first_day = date(cal_year, cal_month, 1)
        days_in_month = cal_module.monthrange(cal_year, cal_month)[1]
        first_weekday = first_day.weekday()
        workout_due_days = set()
        for w in workouts:
            if (
                w.due_date
                and w.due_date.year == cal_year
                and w.due_date.month == cal_month
            ):
                workout_due_days.add(w.due_date.day)

        # Calendar payload for JS (avoids Jinja inside <script>)
        calendar_payload = {
            "today": today.strftime("%Y-%m-%d"),
            "workouts": [
                {
                    "id": w.id,
                    "title": w.title,
                    "description": w.description or "",
                    "due_date": w.due_date.strftime("%Y-%m-%d")
                    if w.due_date
                    else None,
                    "due_display": fmt_datetime(w.due_date) if w.due_date else None,
                }
                for w in workouts
            ],
            "announcements": [
                {
                    "content": ann.content,
                    "created_at": ann.created_at.isoformat() if ann.created_at else None,
                    "is_auto": ann.is_auto,
                }
                for ann in announcements
            ],
        }

        return render_template(
            "team_dashboard.html",
            team=team,
            athletes=athletes,
            groups=groups,
            sidebar_groups=sidebar_groups,
            announcements=announcements,
            workouts=workouts,
            is_coach=is_coach,
            workout_completion=workout_completion,
            workout_status_by_athlete=workout_status_by_athlete,
            cal_year=cal_year,
            cal_month=cal_month,
            days_in_month=days_in_month,
            first_weekday=first_weekday,
            cal_today=today.day,
            workout_due_days=workout_due_days,
            cal_month_name=cal_module.month_name[cal_month],
            calendar_payload=calendar_payload,
        )

    @app.route("/team/<int:team_id>/announcement/create", methods=["GET", "POST"])
    @login_required
    def create_team_announcement(team_id):
        """Coach only: show form (GET) or create announcement (POST)."""
        team = Team.query.get_or_404(team_id)
        if not isinstance(current_user, Coach) or not _user_can_access_team(team):
            flash("You cannot post announcements for this team.", "error")
            return redirect(url_for("dashboard"))
        if request.method == "POST":
            content = request.form.get("content", "").strip()
            announce_to = request.form.get("announce_to", "").strip()
            group_id = None
            if not content:
                flash("Announcement cannot be empty.", "error")
                return render_template(
                    "create_announcement.html",
                    team=team,
                    groups=team.groups.order_by(Group.name).all(),
                )
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
        return render_template(
            "create_announcement.html",
            team=team,
            groups=team.groups.order_by(Group.name).all(),
        )

    @app.route("/team/<int:team_id>/group/create", methods=["GET", "POST"])
    @login_required
    def create_group(team_id):
        """Coach only: create a new group for the team."""
        team = Team.query.get_or_404(team_id)
        if not _is_head_coach(team):
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
        if not _is_head_coach(team):
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
        if not _is_head_coach(team):
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
        # Each athlete's groups for this team (for roster display)
        athlete_groups = {
            a.id: [g.name for g in a.groups.filter(Group.team_id == team_id).all()]
            for a in athletes
        }
        return render_template(
            "team_roster.html",
            team=team,
            athletes=athletes,
            athlete_groups=athlete_groups,
            is_coach=is_coach,
        )

    @app.route("/team/<int:team_id>/messages", methods=["GET", "POST"])
    @login_required
    def team_messages(team_id):
        """Athlete-only: direct messages with the team's coach."""
        team = Team.query.get_or_404(team_id)
        if not _user_can_access_team(team) or not isinstance(current_user, Athlete):
            flash("You cannot view messages for this team.", "error")
            return redirect(url_for("dashboard"))
        coach = team.coach
        if request.method == "POST":
            body = request.form.get("body", "").strip()
            reason = request.form.get("reason", "").strip() or None
            if not body:
                flash("Message cannot be empty.", "error")
                return redirect(url_for("team_messages", team_id=team_id))
            dm = DirectMessage(
                team_id=team.id,
                coach_id=coach.id,
                athlete_id=current_user.id,
                sender_role="athlete",
                reason=reason,
                body=body,
                read_by_coach=False,
                read_by_athlete=True,
                resolved=False,
            )
            db.session.add(dm)
            db.session.commit()
            flash("Message sent to your coach.", "success")
            return redirect(url_for("team_messages", team_id=team_id))

        # Thread: all messages between this athlete and the team's coach
        thread_messages = (
            DirectMessage.query.filter_by(
                team_id=team.id,
                coach_id=coach.id,
                athlete_id=current_user.id,
            )
            .order_by(DirectMessage.created_at.asc())
            .all()
        )
        # Mark coach-sent messages as read by athlete
        updated = False
        for msg in thread_messages:
            if msg.sender_role == "coach" and not msg.read_by_athlete:
                msg.read_by_athlete = True
                updated = True
        if updated:
            db.session.commit()
        return render_template(
            "team_messages.html",
            team=team,
            coach=coach,
            athlete=current_user,
            messages=thread_messages,
            is_coach=False,
        )

    @app.route("/coach/messages")
    @login_required
    def coach_inbox():
        """Coach inbox: grouped direct messages from athletes across teams."""
        if not isinstance(current_user, Coach):
            flash("Only coaches have an inbox.", "error")
            return redirect(url_for("dashboard"))
        # Fetch all messages for this coach
        all_messages = (
            DirectMessage.query.filter_by(coach_id=current_user.id)
            .order_by(DirectMessage.created_at.desc())
            .all()
        )
        threads = {}
        for dm in all_messages:
            key = (dm.team_id, dm.athlete_id)
            thread = threads.get(key)
            if thread is None:
                thread = {
                    "team": dm.team,
                    "athlete": dm.athlete,
                    "last_message": dm,
                    "unread_count": 0,
                    "resolved": dm.resolved,
                }
                threads[key] = thread
            if dm.created_at and (
                thread["last_message"] is None
                or dm.created_at > thread["last_message"].created_at
            ):
                thread["last_message"] = dm
                thread["resolved"] = dm.resolved
            if dm.sender_role == "athlete" and not dm.read_by_coach:
                thread["unread_count"] += 1
        thread_list = []
        for (team_id, athlete_id), data in threads.items():
            athlete = data["athlete"]
            team = data["team"]
            group_names = [
                g.name for g in athlete.groups.filter(Group.team_id == team_id).all()
            ]
            thread_list.append(
                {
                    "team": team,
                    "athlete": athlete,
                    "group_names": group_names,
                    "last_message": data["last_message"],
                    "unread_count": data["unread_count"],
                    "resolved": data["resolved"],
                }
            )
        # Apply filters
        status = request.args.get("status", "").lower()
        if status == "unread":
            thread_list = [t for t in thread_list if t["unread_count"] > 0]
        group_id = request.args.get("group", type=int)
        if group_id:
            thread_list = [
                t
                for t in thread_list
                if any(g.id == group_id for g in t["athlete"].groups.all())
            ]
        date_str = request.args.get("date", "").strip()
        if date_str:
            try:
                from datetime import datetime as _dt

                target_date = _dt.strptime(date_str, "%Y-%m-%d").date()
                thread_list = [
                    t
                    for t in thread_list
                    if t["last_message"].created_at
                    and t["last_message"].created_at.date() == target_date
                ]
            except ValueError:
                pass
        # Sort by latest activity
        thread_list.sort(
            key=lambda t: t["last_message"].created_at or datetime.min, reverse=True
        )
        # Pass first team so sidebar shows Team Hub, Workouts, Roster, Groups, Settings
        team = current_user.teams.first()
        return render_template(
            "coach_inbox.html",
            threads=thread_list,
            team=team,
            is_coach=True,
        )

    @app.route(
        "/team/<int:team_id>/messages/<int:athlete_id>", methods=["GET", "POST"]
    )
    @login_required
    def coach_thread(team_id, athlete_id):
        """Coach-only: conversation with a specific athlete for a team."""
        team = Team.query.get_or_404(team_id)
        if not _is_head_coach(team):
            flash("You cannot view messages for this team.", "error")
            return redirect(url_for("dashboard"))
        athlete = Athlete.query.get_or_404(athlete_id)
        if not team.athletes.filter(Athlete.id == athlete.id).first():
            flash("Athlete is not on this team.", "error")
            return redirect(url_for("dashboard"))
        if request.method == "POST":
            body = request.form.get("body", "").strip()
            reason = request.form.get("reason", "").strip() or None
            if not body:
                flash("Message cannot be empty.", "error")
                return redirect(
                    url_for("coach_thread", team_id=team_id, athlete_id=athlete_id)
                )
            dm = DirectMessage(
                team_id=team.id,
                coach_id=current_user.id,
                athlete_id=athlete.id,
                sender_role="coach",
                reason=reason,
                body=body,
                read_by_coach=True,
                read_by_athlete=False,
                resolved=False,
            )
            db.session.add(dm)
            db.session.commit()
            flash("Message sent.", "success")
            return redirect(
                url_for("coach_thread", team_id=team_id, athlete_id=athlete_id)
            )

        thread_messages = (
            DirectMessage.query.filter_by(
                team_id=team.id,
                coach_id=current_user.id,
                athlete_id=athlete.id,
            )
            .order_by(DirectMessage.created_at.asc())
            .all()
        )
        updated = False
        for msg in thread_messages:
            if msg.sender_role == "athlete" and not msg.read_by_coach:
                msg.read_by_coach = True
                updated = True
        if updated:
            db.session.commit()
        athlete_groups = [
            g.name for g in athlete.groups.filter(Group.team_id == team.id).all()
        ]
        return render_template(
            "team_messages.html",
            team=team,
            coach=current_user,
            athlete=athlete,
            athlete_groups=athlete_groups,
            messages=thread_messages,
            is_coach=True,
        )

    @app.route(
        "/team/<int:team_id>/messages/<int:athlete_id>/resolve", methods=["POST"]
    )
    @login_required
    def resolve_thread(team_id, athlete_id):
        """Coach-only: mark a conversation as resolved."""
        team = Team.query.get_or_404(team_id)
        if not _is_head_coach(team):
            flash("You cannot resolve messages for this team.", "error")
            return redirect(url_for("dashboard"))
        athlete = Athlete.query.get_or_404(athlete_id)
        if not team.athletes.filter(Athlete.id == athlete.id).first():
            flash("Athlete is not on this team.", "error")
            return redirect(url_for("dashboard"))
        thread_messages = DirectMessage.query.filter_by(
            team_id=team.id, coach_id=current_user.id, athlete_id=athlete.id
        ).all()
        for msg in thread_messages:
            msg.resolved = True
        if thread_messages:
            db.session.commit()
            flash("Conversation marked as resolved.", "success")
        return redirect(url_for("coach_thread", team_id=team_id, athlete_id=athlete_id))

    @app.route("/team/<int:team_id>/roster/remove", methods=["POST"])
    @login_required
    def roster_remove(team_id):
        """Coach only: remove an athlete from the team."""
        team = Team.query.get_or_404(team_id)
        if not _is_head_coach(team):
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
        # Remove exercise completion records for this athlete on this team.
        # (Cannot call .delete() on a query that uses .join(); select IDs first, then delete by ID.)
        ids_to_delete = [
            row[0]
            for row in db.session.query(ExerciseStatus.id)
            .join(Exercise, ExerciseStatus.exercise_id == Exercise.id)
            .join(Workout, Exercise.workout_id == Workout.id)
            .filter(Workout.team_id == team_id, ExerciseStatus.athlete_id == athlete_id)
            .all()
        ]
        if ids_to_delete:
            ExerciseStatus.query.filter(ExerciseStatus.id.in_(ids_to_delete)).delete(
                synchronize_session=False
            )
        db.session.commit()
        flash("Athlete removed from team.", "success")
        return redirect(url_for("team_roster", team_id=team_id))

    def _coach_owns_team(team):
        """Return True if current_user is the coach who owns the team (head coach)."""
        return _is_head_coach(team)

    # ----- Workouts -----

    @app.route("/team/<int:team_id>/workouts")
    @login_required
    def team_workouts(team_id):
        """List workouts for a team. Coach: all workouts with progress. Athlete: workouts assigned to them."""
        team = Team.query.get_or_404(team_id)
        if not _user_can_access_team(team):
            flash("You do not have access to this team.", "error")
            return redirect(url_for("dashboard"))

        all_workouts = (
            Workout.query.filter_by(team_id=team_id)
            .order_by(Workout.created_at.desc())
            .all()
        )
        is_coach = isinstance(current_user, Coach)

        if is_coach:
            workouts = all_workouts
        else:
            athlete_group_ids = {
                g.id for g in current_user.groups.filter(Group.team_id == team_id).all()
            }
            workouts = [
                w
                for w in all_workouts
                if w.group_id is None or w.group_id in athlete_group_ids
            ]

        coach_progress = {}
        athlete_progress = {}

        if is_coach:
            for w in workouts:
                total = (
                    ExerciseStatus.query.join(Exercise)
                    .filter(Exercise.workout_id == w.id)
                    .count()
                )
                completed = (
                    ExerciseStatus.query.join(Exercise)
                    .filter(
                        Exercise.workout_id == w.id,
                        ExerciseStatus.completed.is_(True),
                    )
                    .count()
                )
                coach_progress[w.id] = (completed, total)
        else:
            for w in workouts:
                total_exercises = Exercise.query.filter_by(workout_id=w.id).count()
                completed_exercises = (
                    ExerciseStatus.query.join(Exercise)
                    .filter(
                        Exercise.workout_id == w.id,
                        ExerciseStatus.athlete_id == current_user.id,
                        ExerciseStatus.completed.is_(True),
                    )
                    .count()
                )
                athlete_progress[w.id] = (completed_exercises, total_exercises)

        return render_template(
            "workouts_list.html",
            team=team,
            workouts=workouts,
            is_coach=is_coach,
            coach_progress=coach_progress,
            athlete_progress=athlete_progress,
        )

    @app.route("/team/<int:team_id>/workout/create", methods=["GET", "POST"])
    @login_required
    def create_team_workout(team_id):
        """Coach-only: create a workout with exercises for this team; generate ExerciseStatus for each athlete."""
        team = Team.query.get_or_404(team_id)
        if not isinstance(current_user, Coach) or not _user_can_access_team(team):
            flash("You cannot create workouts for this team.", "error")
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
                    due_date = None

            assign_to = request.form.get("assign_to", "").strip()
            group_id = None
            if assign_to.startswith("g"):
                try:
                    raw_id = int(assign_to[1:])
                    group = Group.query.filter_by(id=raw_id, team_id=team_id).first()
                    if group:
                        group_id = group.id
                except (TypeError, ValueError):
                    group_id = None

            if not title:
                flash("Title is required.", "error")
                return render_template(
                    "workout_create.html",
                    team=team,
                    groups=team.groups.order_by(Group.name).all(),
                )

            names = request.form.getlist("exercise_name")
            sets_list = request.form.getlist("exercise_sets")
            reps_list = request.form.getlist("exercise_reps")
            notes_list = request.form.getlist("exercise_notes")

            exercises_payload = []
            for idx, name in enumerate(names):
                name_clean = (name or "").strip()
                if not name_clean:
                    continue
                try:
                    sets_val = int(sets_list[idx]) if sets_list[idx] else None
                except (ValueError, IndexError):
                    sets_val = None
                # Reps can be a single number or a comma-separated per-set plan like "10,8"
                raw_reps = ""
                try:
                    raw_reps = (reps_list[idx] or "").strip()
                except IndexError:
                    raw_reps = ""
                reps_val = None
                set_plan = None
                if raw_reps:
                    if "," in raw_reps:
                        parts = [p.strip() for p in raw_reps.split(",") if p.strip()]
                        per_sets = []
                        for i, part in enumerate(parts, start=1):
                            try:
                                r = int(part)
                            except ValueError:
                                continue
                            per_sets.append({"set": i, "reps": r})
                        if per_sets:
                            set_plan = json.dumps(per_sets)
                            reps_val = per_sets[0]["reps"]
                            if sets_val is None:
                                sets_val = len(per_sets)
                    else:
                        try:
                            reps_val = int(raw_reps)
                        except ValueError:
                            reps_val = None
                notes_val = (notes_list[idx] if idx < len(notes_list) else "").strip() or None
                exercises_payload.append(
                    {
                        "name": name_clean,
                        "sets": sets_val,
                        "reps": reps_val,
                        "notes": notes_val,
                        "set_plan": set_plan,
                    }
                )

            if not exercises_payload:
                flash("Add at least one exercise.", "error")
                return render_template(
                    "workout_create.html",
                    team=team,
                    groups=team.groups.order_by(Group.name).all(),
                )

            workout = Workout(
                title=title,
                description=description,
                due_date=due_date,
                team_id=team_id,
                group_id=group_id,
                created_by=current_user.id,
            )
            db.session.add(workout)
            db.session.flush()

            for order_idx, row in enumerate(exercises_payload, start=1):
                ex = Exercise(
                    workout_id=workout.id,
                    name=row["name"],
                    sets=row["sets"],
                    reps=row["reps"],
                    notes=row["notes"],
                    set_plan=row["set_plan"],
                    order=order_idx,
                )
                db.session.add(ex)

            db.session.flush()

            # Create ExerciseStatus rows for all applicable athletes
            if group_id:
                target_group = Group.query.get(group_id)
                target_athletes = target_group.athletes.all() if target_group else []
            else:
                target_athletes = team.athletes.all()

            exercises = workout.exercises.all()
            for athlete in target_athletes:
                for ex in exercises:
                    status = ExerciseStatus(
                        exercise_id=ex.id,
                        athlete_id=athlete.id,
                        completed=False,
                    )
                    db.session.add(status)

            auto_ann = Announcement(
                content=f"{current_user.name} posted workout: {workout.title}",
                team_id=team_id,
                created_by=current_user.id,
                is_auto=True,
            )
            db.session.add(auto_ann)

            db.session.commit()
            flash("Workout created.", "success")
            return redirect(url_for("team_dashboard", team_id=team_id))

        return render_template(
            "workout_create.html",
            team=team,
            groups=team.groups.order_by(Group.name).all(),
        )

    @app.route("/team/<int:team_id>/workout/<int:workout_id>")
    @login_required
    def workout_detail(team_id, workout_id):
        """Workout detail view for coaches and athletes."""
        team = Team.query.get_or_404(team_id)
        workout = Workout.query.filter_by(id=workout_id, team_id=team_id).first_or_404()
        if not _user_can_access_team(team):
            flash("You do not have access to this team.", "error")
            return redirect(url_for("dashboard"))

        # Athlete-specific visibility: respect group targeting
        if isinstance(current_user, Athlete):
            if workout.group_id is not None:
                athlete_group_ids = {
                    g.id
                    for g in current_user.groups.filter(Group.team_id == team_id).all()
                }
                if workout.group_id not in athlete_group_ids:
                    flash("You do not have access to this workout.", "error")
                    return redirect(url_for("dashboard"))

        exercises = workout.exercises.order_by(Exercise.order).all()
        is_coach = isinstance(current_user, Coach)

        exercise_progress = {}
        overall_completed = 0
        overall_total = 0
        athlete_statuses = {}
        set_plans = {}

        if is_coach:
            for ex in exercises:
                total = ex.statuses.count()
                completed = ex.statuses.filter_by(completed=True).count()
                exercise_progress[ex.id] = (completed, total)
                overall_total += total
                overall_completed += completed
        else:
            for ex in exercises:
                status = ExerciseStatus.query.filter_by(
                    exercise_id=ex.id, athlete_id=current_user.id
                ).first()
                athlete_statuses[ex.id] = status

        # Parse any stored per-set rep plans for display
        for ex in exercises:
            if ex.set_plan:
                try:
                    plan = json.loads(ex.set_plan)
                except (TypeError, ValueError, json.JSONDecodeError):
                    plan = None
                if isinstance(plan, list):
                    set_plans[ex.id] = plan

        return render_template(
            "workout_detail.html",
            team=team,
            workout=workout,
            exercises=exercises,
            is_coach=is_coach,
            exercise_progress=exercise_progress,
            overall_completed=overall_completed,
            overall_total=overall_total,
            athlete_statuses=athlete_statuses,
            set_plans=set_plans,
        )

    @app.route("/team/<int:team_id>/workout/<int:workout_id>/completions")
    @login_required
    def workout_completions(team_id, workout_id):
        """Coach-only: per-athlete completion breakdown for a workout."""
        team = Team.query.get_or_404(team_id)
        workout = Workout.query.filter_by(id=workout_id, team_id=team_id).first_or_404()
        if not isinstance(current_user, Coach) or not _user_can_access_team(team):
            flash("You do not have access to this page.", "error")
            return redirect(url_for("dashboard"))

        completed_athletes, not_completed_athletes = _get_workout_completion_breakdown(
            team, workout
        )
        return render_template(
            "workout_completions.html",
            team=team,
            workout=workout,
            completed_athletes=completed_athletes,
            not_completed_athletes=not_completed_athletes,
        )

    @app.route("/team/<int:team_id>/workout/<int:workout_id>/completions.json")
    @login_required
    def workout_completions_json(team_id, workout_id):
        """Coach-only: JSON version of per-athlete completion breakdown."""
        team = Team.query.get_or_404(team_id)
        workout = Workout.query.filter_by(id=workout_id, team_id=team_id).first_or_404()
        if not isinstance(current_user, Coach) or not _user_can_access_team(team):
            return jsonify({"error": "Not authorized"}), 403

        completed_athletes, not_completed_athletes = _get_workout_completion_breakdown(
            team, workout
        )

        def _serialize(record):
            athlete = record["athlete"]
            completed_at = record["completed_at"]
            return {
                "name": athlete.name,
                "groupLabel": record["group_label"],
                "completed": record["completed"],
                "completedExercises": record["completed_exercises"],
                "totalExercises": record["total_exercises"],
                "completedAt": completed_at.isoformat() if completed_at else None,
                "completedAtDisplay": fmt_datetime(completed_at)
                if completed_at
                else "",
            }

        return jsonify(
            {
                "workoutTitle": workout.title,
                "completed": [_serialize(r) for r in completed_athletes],
                "notCompleted": [_serialize(r) for r in not_completed_athletes],
            }
        )

    @app.route("/exercise/<int:exercise_id>/complete", methods=["POST"])
    @login_required
    def exercise_toggle_complete(exercise_id):
        """Athlete only: toggle completion state for a single exercise."""
        if not isinstance(current_user, Athlete):
            flash("Only athletes can complete workouts.", "error")
            return redirect(url_for("dashboard"))

        exercise = Exercise.query.get_or_404(exercise_id)
        workout = exercise.workout
        team = workout.team
        if not _user_can_access_team(team):
            flash("You do not have access to this team.", "error")
            return redirect(url_for("dashboard"))

        # Ensure athlete is in the targeted cohort
        if workout.group_id is not None:
            group_ids = {
                g.id for g in current_user.groups.filter(Group.team_id == team.id).all()
            }
            if workout.group_id not in group_ids:
                flash("You do not have access to this workout.", "error")
                return redirect(url_for("dashboard"))

        status = ExerciseStatus.query.filter_by(
            exercise_id=exercise.id,
            athlete_id=current_user.id,
        ).first()
        now = datetime.now()
        if not status:
            status = ExerciseStatus(
                exercise_id=exercise.id,
                athlete_id=current_user.id,
                completed=True,
                completed_at=now,
            )
            db.session.add(status)
        else:
            status.completed = not status.completed
            status.completed_at = now if status.completed else None

        db.session.commit()
        return redirect(
            url_for(
                "workout_detail",
                team_id=team.id,
                workout_id=workout.id,
            )
        )

    @app.route("/team/<int:team_id>/workout/<int:workout_id>/edit", methods=["GET", "POST"])
    @login_required
    def workout_edit(team_id, workout_id):
        """Coach only: edit a workout and its exercises."""
        team = Team.query.get_or_404(team_id)
        workout = Workout.query.filter_by(id=workout_id, team_id=team_id).first_or_404()
        if not _coach_owns_team(team):
            flash("You cannot edit this workout.", "error")
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
                    due_date = None

            assign_to = request.form.get("assign_to", "").strip()
            group_id = None
            if assign_to.startswith("g"):
                try:
                    raw_id = int(assign_to[1:])
                    group = Group.query.filter_by(id=raw_id, team_id=team_id).first()
                    if group:
                        group_id = group.id
                except (TypeError, ValueError):
                    group_id = None

            if not title:
                flash("Title is required.", "error")
                return render_template(
                    "workout_edit.html",
                    team=team,
                    workout=workout,
                    groups=team.groups.order_by(Group.name).all(),
                    exercises=workout.exercises.order_by(Exercise.order).all(),
                )

            workout.title = title
            workout.description = description
            workout.due_date = due_date
            workout.group_id = group_id

            existing_exercises = {ex.id: ex for ex in workout.exercises.all()}

            ids = request.form.getlist("exercise_id")
            names = request.form.getlist("exercise_name")
            sets_list = request.form.getlist("exercise_sets")
            reps_list = request.form.getlist("exercise_reps")
            notes_list = request.form.getlist("exercise_notes")

            seen_ids = set()
            order_counter = 1

            for idx, name in enumerate(names):
                name_clean = (name or "").strip()
                if not name_clean:
                    continue

                raw_id = ids[idx] if idx < len(ids) else ""
                try:
                    sets_val = int(sets_list[idx]) if sets_list[idx] else None
                except (ValueError, IndexError):
                    sets_val = None
                # Reps can be a single number or a comma-separated per-set plan like "10,8"
                raw_reps = ""
                try:
                    raw_reps = (reps_list[idx] or "").strip()
                except IndexError:
                    raw_reps = ""
                reps_val = None
                set_plan = None
                if raw_reps:
                    if "," in raw_reps:
                        parts = [p.strip() for p in raw_reps.split(",") if p.strip()]
                        per_sets = []
                        for i, part in enumerate(parts, start=1):
                            try:
                                r = int(part)
                            except ValueError:
                                continue
                            per_sets.append({"set": i, "reps": r})
                        if per_sets:
                            set_plan = json.dumps(per_sets)
                            reps_val = per_sets[0]["reps"]
                            if sets_val is None:
                                sets_val = len(per_sets)
                    else:
                        try:
                            reps_val = int(raw_reps)
                        except ValueError:
                            reps_val = None
                notes_val = (notes_list[idx] if idx < len(notes_list) else "").strip() or None

                if raw_id:
                    ex_id = int(raw_id)
                    ex = existing_exercises.get(ex_id)
                    if not ex:
                        continue
                    ex.name = name_clean
                    ex.sets = sets_val
                    ex.reps = reps_val
                    ex.notes = notes_val
                    ex.set_plan = set_plan
                    ex.order = order_counter
                    seen_ids.add(ex_id)
                else:
                    ex = Exercise(
                        workout_id=workout.id,
                        name=name_clean,
                        sets=sets_val,
                        reps=reps_val,
                        notes=notes_val,
                        set_plan=set_plan,
                        order=order_counter,
                    )
                    db.session.add(ex)
                order_counter += 1

            # Delete exercises that were removed from the form
            for ex_id, ex in existing_exercises.items():
                if ex_id not in seen_ids:
                    db.session.delete(ex)

            auto_ann = Announcement(
                content=f"{current_user.name} updated workout: {workout.title}",
                team_id=team_id,
                created_by=current_user.id,
                is_auto=True,
            )
            db.session.add(auto_ann)

            db.session.commit()
            flash("Workout updated.", "success")
            return redirect(
                url_for("workout_detail", team_id=team_id, workout_id=workout.id)
            )

        ex_list = workout.exercises.order_by(Exercise.order).all()
        exercise_reps_display = {}
        for ex in ex_list:
            if ex.set_plan:
                try:
                    plan = json.loads(ex.set_plan)
                except (TypeError, ValueError, json.JSONDecodeError):
                    plan = None
                if isinstance(plan, list):
                    reps_str = ", ".join(
                        str(item.get("reps"))
                        for item in plan
                        if isinstance(item, dict) and item.get("reps") is not None
                    )
                    if reps_str:
                        exercise_reps_display[ex.id] = reps_str

        return render_template(
            "workout_edit.html",
            team=team,
            workout=workout,
            groups=team.groups.order_by(Group.name).all(),
            exercises=ex_list,
            exercise_reps_display=exercise_reps_display,
        )

    @app.route("/team/<int:team_id>/workout/<int:workout_id>/delete", methods=["POST"])
    @login_required
    def workout_delete(team_id, workout_id):
        """Coach only: delete a workout (and its exercises/statuses via cascade)."""
        team = Team.query.get_or_404(team_id)
        workout = Workout.query.filter_by(id=workout_id, team_id=team_id).first_or_404()
        if not _coach_owns_team(team):
            flash("You cannot delete this workout.", "error")
            return redirect(url_for("dashboard"))

        title = workout.title
        db.session.delete(workout)

        auto_ann = Announcement(
            content=f"{current_user.name} removed workout: {title}",
            team_id=team_id,
            created_by=current_user.id,
            is_auto=True,
        )
        db.session.add(auto_ann)
        db.session.commit()
        flash("Workout deleted.", "success")
        return redirect(url_for("team_dashboard", team_id=team_id))

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

    @app.errorhandler(404)
    def not_found(error):
        return (
            render_template(
                "error.html",
                code=404,
                message="That page could not be found.",
            ),
            404,
        )

    @app.errorhandler(500)
    def server_error(error):
        return (
            render_template(
                "error.html",
                code=500,
                message="Something went wrong on our side. Please try again.",
            ),
            500,
        )

    with app.app_context():
        db.create_all()
        # Automatically create a small demo dataset on first run (no-op if data exists).
        ensure_demo_data()

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
