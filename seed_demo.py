from datetime import datetime, timedelta

from extensions import db
from models import Coach, Athlete, Team, Group, Workout, Exercise, ExerciseStatus, Announcement


DEMO_COACH_EMAIL = "coach@example.com"


def _demo_exists() -> bool:
    """Return True if the demo coach already exists.

    This keeps demo seeding idempotent based on the specific demo data,
    instead of short-circuiting as soon as *any* data exists.
    """
    return Coach.query.filter_by(email=DEMO_COACH_EMAIL).first() is not None


def ensure_demo_data() -> None:
    """Create a small, realistic demo dataset if the DB is empty.

    This is meant for local development / demos. It does NOT drop or wipe data;
    it simply no-ops once the demo coach already exists.
    """
    if _demo_exists():
        return

    now = datetime.now()

    # --- Coaches ---
    coach = Coach(name="Coach Taylor", email= "coach@example.com")
    coach.set_password("Password123!")
    assistant = Coach(name="Assistant Kelly", email="assistant@example.com")
    assistant.set_password("Password123!")
    db.session.add_all([coach, assistant])
    db.session.flush()

    # --- Team ---
    team = Team(
        name="West Dillon Lions",
        coach_id=coach.id,
        invite_code=Team.generate_invite_code(),
    )
    db.session.add(team)
    db.session.flush()

    # Assistant as staff coach on same team
    team.coaches.append(assistant)

    # --- Athletes ---
    ath1 = Athlete(name="Jason Street", email="jason@example.com")
    ath1.set_password("Password123!")
    ath2 = Athlete(name="Tim Riggins", email="tim@example.com")
    ath2.set_password("Password123!")
    ath3 = Athlete(name="Matt Saracen", email="matt@example.com")
    ath3.set_password("Password123!")

    db.session.add_all([ath1, ath2, ath3])
    db.session.flush()

    # Add athletes to team
    team.athletes.extend([ath1, ath2, ath3])

    # --- Groups ---
    qbs = Group(name="Quarterbacks", team_id=team.id)
    offense = Group(name="Offense", team_id=team.id)
    db.session.add_all([qbs, offense])
    db.session.flush()

    # Group membership
    qbs.athletes.extend([ath1, ath3])
    offense.athletes.extend([ath1, ath2, ath3])

    # --- Announcements ---
    ann1 = Announcement(
        content="Welcome to RepRoom! Check your workouts for this week.",
        team_id=team.id,
        created_by=coach.id,
        created_at=now - timedelta(hours=2),
        is_auto=False,
    )
    ann2 = Announcement(
        content="QB meeting after practice in the film room.",
        team_id=team.id,
        group_id=qbs.id,
        created_by=coach.id,
        created_at=now - timedelta(days=1, hours=3),
        is_auto=False,
    )
    db.session.add_all([ann1, ann2])

    # --- Workouts ---
    # Team-wide workout
    team_workout = Workout(
        title="Monday Strength Session",
        description="Full-body strength and conditioning.",
        due_date=(now + timedelta(days=1)).replace(
            hour=23,
            minute=59,
            second=0,
            microsecond=0,
        ),
        team_id=team.id,
        group_id=None,
        created_by=coach.id,
        created_at=now - timedelta(hours=1),
    )
    db.session.add(team_workout)
    db.session.flush()

    ex1 = Exercise(
        workout_id=team_workout.id,
        name="Back Squat",
        sets=3,
        reps=10,
        notes="Focus on depth and control.",
        order=1,
    )
    ex2 = Exercise(
        workout_id=team_workout.id,
        name="Bench Press",
        sets=3,
        reps=8,
        notes="Spot each other.",
        order=2,
    )
    ex3 = Exercise(
        workout_id=team_workout.id,
        name="Conditioning Runs",
        sets=4,
        reps=None,
        notes="4 x 200m, steady pace.",
        order=3,
    )
    db.session.add_all([ex1, ex2, ex3])
    db.session.flush()

    team_athletes = team.athletes.all() if hasattr(team.athletes, "all") else [ath1, ath2, ath3]
    for athlete in team_athletes:
        for ex in (ex1, ex2, ex3):
            status = ExerciseStatus(
                exercise_id=ex.id,
                athlete_id=athlete.id,
                completed=False,
                completed_at=None,
            )
            db.session.add(status)

    # Mark some completions so progress looks interesting
    def _mark_completed(exercise: Exercise, athlete: Athlete, hours_ago: int = 0) -> None:
        status = ExerciseStatus.query.filter_by(
            exercise_id=exercise.id,
            athlete_id=athlete.id,
        ).first()
        if status:
            status.completed = True
            status.completed_at = now - timedelta(hours=hours_ago)

    _mark_completed(ex1, ath1, hours_ago=3)
    _mark_completed(ex2, ath1, hours_ago=2)
    _mark_completed(ex3, ath1, hours_ago=1)
    _mark_completed(ex1, ath2, hours_ago=1)

    # QB-only workout
    qb_workout = Workout(
        title="QB Film + Footwork",
        description="Film breakdown and on-field footwork drills.",
        due_date=(now + timedelta(days=2)).replace(
            hour=23,
            minute=59,
            second=0,
            microsecond=0,
        ),
        team_id=team.id,
        group_id=qbs.id,
        created_by=coach.id,
        created_at=now - timedelta(minutes=30),
    )
    db.session.add(qb_workout)
    db.session.flush()

    qb_ex1 = Exercise(
        workout_id=qb_workout.id,
        name="Dropback Footwork",
        sets=3,
        reps=10,
        notes="5-step and 7-step drops.",
        order=1,
    )
    qb_ex2 = Exercise(
        workout_id=qb_workout.id,
        name="Film Study: Cover-2",
        sets=1,
        reps=None,
        notes="Take notes on coverage rotations.",
        order=2,
    )
    db.session.add_all([qb_ex1, qb_ex2])
    db.session.flush()

    qb_athletes = qbs.athletes.all() if hasattr(qbs.athletes, "all") else [ath1, ath3]
    for athlete in qb_athletes:
        for ex in (qb_ex1, qb_ex2):
            status = ExerciseStatus(
                exercise_id=ex.id,
                athlete_id=athlete.id,
                completed=False,
                completed_at=None,
            )
            db.session.add(status)

    auto_ann_team = Announcement(
        content=f"{coach.name} posted workout: {team_workout.title}",
        team_id=team.id,
        created_by=coach.id,
        is_auto=True,
    )
    auto_ann_qb = Announcement(
        content=f"{coach.name} posted workout: {qb_workout.title}",
        team_id=team.id,
        created_by=coach.id,
        is_auto=True,
    )
    db.session.add_all([auto_ann_team, auto_ann_qb])

    db.session.commit()

