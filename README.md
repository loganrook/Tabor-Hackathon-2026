# GamePlan

GamePlan is a coach–athlete management web app built with Flask. Coaches create teams and share invite codes; athletes join teams and view assignments. UI uses Bootstrap 5, Bootstrap Icons, and custom GamePlan branding.

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
- **`templates/`** — Jinja2 templates: `base.html`, `home.html`, `login.html`, `register.html`, `dashboard.html`, `team_dashboard.html`, `team_settings.html`, `team_roster.html`, assignment/announcement/group forms
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

- **Calendar**: The team dashboard calendar now starts weeks on Sunday, stretches rows to fill the available height, and shows a tiny preview of the first assignment title inside each day cell so coaches can quickly scan what’s coming.
- **Sidebar & roster**: The team sidebar focuses on simple section labels (Team Hub, Roster, Groups, Team Settings), while the roster page itself shows a player count under the `Roster` heading (for example, `5 players`).
- **Top bar**: When viewing a team, the top bar shows a breadcrumb-style context like `GamePlan › Football`, with the team name slightly larger and bolder for orientation.
- **Right column**: The announcements/assignments column is slightly wider, announcement timestamps use friendly “time ago” text like `Just now` or `2 hours ago`, the plus icons have hover tooltips, and empty states include subtle icons so they feel intentional rather than broken.
