# Hackathon

A coach–athlete management web app built with Flask for a hackathon.

## Stack

- **Flask** — web framework
- **Flask-SQLAlchemy** — ORM and database (SQLite by default)
- **Flask-Login** — session and login handling

## Project structure

- **`app.py`** — main Flask app, route stubs (homepage, login, logout, coach/athlete dashboards, roster, add athlete)
- **`config.py`** — configuration (secret key, database URI, etc.)
- **`extensions.py`** — shared `db` and `login_manager` instances (used by `app.py` and `models.py`)
- **`models.py`** — SQLAlchemy models: `Coach`, `Athlete`, `Team`
- **`templates/`** — Jinja2 templates: `base.html`, `home.html`, `login.html`, `coach_dashboard.html`, `athlete_dashboard.html`, `roster.html`
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
