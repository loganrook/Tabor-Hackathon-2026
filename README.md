# RepRoom

RepRoom is a coach–athlete management web app built with Flask. Coaches create teams and share invite codes; athletes join teams and view workouts. UI uses Bootstrap 5, Bootstrap Icons, and custom RepRoom branding.

## Stack

- **Flask** — web framework
- **Flask-SQLAlchemy** — ORM and database (SQLite by default)
- **Flask-Login** — session and login handling
- **Bootstrap 5** — layout and components; **Bootstrap Icons** — icons

## Project structure

- **`app.py`** — main Flask app, route stubs (homepage, login, logout, coach/athlete dashboards, roster, add athlete)
- **`config.py`** — configuration (secret key, database URI, etc.)
- **`extensions.py`** — shared `db` and `login_manager` instances (used by `app.py` and `models.py`)
- **`models.py`** — SQLAlchemy models: `Coach`, `Athlete`, `Team`
- **`templates/`** — Jinja2 templates: `base.html`, `home.html`, `login.html`, `register.html`, `dashboard.html`, `team_dashboard.html`, `team_settings.html`, `team_roster.html`, workout/announcement/group forms
- **`static/`** — static assets (e.g. `style.css`)
- **`tests/`** — tests: `test_models.py`, `test_app.py`

## Setup and run

1. Create a virtual environment and install dependencies:

   ```bash
   python -m venv venv
   venv\Scripts\activate   # Windows
   pip install -r requirements.txt
   ```

2. Run the app (set `FLASK_APP=app` if needed):

   ```bash
   set FLASK_APP=app
   flask run
   ```

   Or:

   ```bash
   python app.py
   ```

   The app will be available at `http://127.0.0.1:5000/`. The SQLite database file is created as `app.db` in the project root on first run.

## Demo data

On first launch against an empty database, RepRoom automatically seeds a small demo environment so the UI looks “alive” without any manual setup:

- **Coach accounts**
  - `coach@example.com` / `Password123!` (head coach)
  - `assistant@example.com` / `Password123!` (staff coach on the same team)
- **Athlete accounts**
  - `jason@example.com` / `Password123!`
  - `tim@example.com` / `Password123!`
  - `matt@example.com` / `Password123!`
- **Team**
  - One team named `West Dillon Lions` with a generated invite code
- **Extras**
  - Position groups (e.g. Quarterbacks, Offense) with athletes assigned
  - Announcements (manual + auto-generated)
  - Team-wide and group-only workouts with exercises and completion statuses so dashboards, progress bars, and the calendar all show realistic data

Seeding is **idempotent**: the demo data is only created when the database has no coaches or teams. If you already have data (for example, in a shared dev DB), `seed_demo` will not modify or reset it.

## Tests

From the project root:

```bash
python -m pytest tests/ -v
```

Tests are stubs for now; implement them as you add features (e.g. login, DB operations).

## Configuration

- **SECRET_KEY**: Set the `SECRET_KEY` environment variable in any non-local environment so sessions and cookies are properly secured. The dev default is only for local use.
- **DATABASE_URL**: Override the default SQLite database by setting `DATABASE_URL` (e.g. to a Postgres URI) if you deploy beyond a single-machine demo.
- **FLASK_DEBUG**: Debug mode is enabled only when `FLASK_DEBUG=1`. Do not set this in production; leave it unset (or `0`) so detailed stack traces are not exposed and the custom 404/500 pages are used instead.

## Team dashboard UI

- **Calendar**: The team dashboard calendar starts weeks on Sunday, stretches rows to fill the available height, and shows a tiny preview of the first workout title inside each day cell so coaches can quickly scan what’s coming. Dots under each day indicate workout due dates and announcements.
- **Sidebar & roster**: The team sidebar focuses on simple section labels (Team Hub, Workouts, Roster, Groups, Team Settings), while the roster page itself shows a player count under the `Roster` heading (for example, `5 players`).
- **Top bar**: When viewing a team, the top bar shows a breadcrumb-style context like `RepRoom › Football`, with the team name slightly larger and bolder for orientation.
- **Right column**: The right column is split into Announcements and Workouts. Cards in this column use the same clean white card style as the rest of the app so workouts, announcements, and their progress states all feel consistent. Announcement timestamps use friendly “time ago” text like `Just now` or `2 hours ago`, the plus icons have hover tooltips, and empty states include subtle icons so they feel intentional rather than broken. Coaches see per-workout completion progress; athletes see their own exercise completion status.

## Workouts: sets and reps

- **Simple case**: Each exercise row lets you enter a number of sets and a single reps value (for example, `3` sets and `10` reps).
- **Different reps per set**: If a coach wants different reps on each set, they can type a comma-separated list into the Reps box (for example, `12,10` for 2 sets, or `12,10,8` for 3 sets). The app stores this plan with the workout, and the workout detail screen shows the breakdown as “Set 1: 12 reps · Set 2: 10 reps · Set 3: 8 reps”.

## Workout detail UI

- **Exercise cards**: On the workout detail page, each exercise is rendered as its own white card with a bold, dark exercise name, darker gray sets/reps text, and generous padding/spacing so both coaches and athletes can quickly scan the workout.
- **Completion & progress**: Athlete checkboxes use high-contrast styling, and per-exercise completion/progress text is shown in dark, readable text inside each card so it remains legible even on dim displays.
