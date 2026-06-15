"""
Integration test for plateau detection/intervention via /api/analysis/sessions.

Plateau detection reads auto-regulation's local per-exercise progression history;
these tests validate the analyze workflow (full plateau detection needs several
seeded sessions, covered by the unit tests).
"""
import pytest

from tests.factories import (
    AthleteFactory, ExerciseFactory, WorkoutPlanFactory, WorkoutDayFactory,
    WorkoutDayExerciseFactory, WorkoutSessionFactory, ExerciseSetFactory,
    RecoveryMetricsFactory,
)
from app.utils.constants import Gender, TrainingExperience, TrainingType


def _request(athlete, plan, day_id, exercise_id, sets_data, recovery_kwargs, overall_rpe=8.0):
    sets = [ExerciseSetFactory.create(exercise_id=exercise_id, set_number=i, **sd)
            for i, sd in enumerate(sets_data, start=1)]
    session = WorkoutSessionFactory.create(
        athlete_id=athlete.id, workout_day_id=day_id, overall_rpe=overall_rpe, sets=sets,
    )
    session = session.model_copy(update={
        "sets": [s.model_copy(update={"workout_session_id": session.id}) for s in sets]
    })
    recovery = RecoveryMetricsFactory.create(athlete_id=athlete.id, date=session.session_date, **recovery_kwargs)
    from app.modules.analysis import AnalysisRequest
    return AnalysisRequest(athlete=athlete, plan=plan, session=session, recovery=recovery, personal_records=[])


def _build_plan(athlete, exercise, plan_id, day_id, training_type=TrainingType.HYPERTROPHY,
                reps_min=8, reps_max=12):
    day_exercise = WorkoutDayExerciseFactory.create(
        exercise_id=exercise.id, workout_day_id=day_id, target_reps_min=reps_min, target_reps_max=reps_max,
    )
    day = WorkoutDayFactory.create(id=day_id, workout_plan_id=plan_id, exercises=[day_exercise])
    return WorkoutPlanFactory.create(id=plan_id, athlete_id=athlete.id, training_type=training_type, days=[day])


@pytest.mark.integration
class TestPlateauInterventionJourney:
    def test_stalled_session_workflow(self, client, db_session):
        athlete = AthleteFactory.create(age=28)
        exercise = ExerciseFactory.create_compound(name="Bench Press")
        plan = _build_plan(athlete, exercise, plan_id=5001, day_id=5101)
        request = _request(
            athlete, plan, 5101, exercise.id,
            sets_data=[
                {"weight": 100.0, "reps": 10, "rpe": 9.0, "form_quality": "good"},
                {"weight": 100.0, "reps": 9, "rpe": 9.5, "form_quality": "fair"},
            ],
            recovery_kwargs={"sleep_quality": "good", "sleep_hours": 7.5,
                             "overall_soreness": 4, "stress_level": 5, "energy_level": 6},
            overall_rpe=9.0,
        )
        response = client.post("/api/analysis/sessions", json=request.model_dump(mode="json"))
        assert response.status_code == 200, response.text
        data = response.json()
        assert "ai_insights" in data
        assert "next_workout" in data
        assert "adjustments" in data

    def test_progress_session_workflow(self, client, db_session):
        athlete = AthleteFactory.create(age=25, gender=Gender.FEMALE,
                                        training_experience=TrainingExperience.BEGINNER)
        exercise = ExerciseFactory.create_compound(
            name="Squat", muscles=[("quadriceps", 90), ("glutes", 80), ("hamstrings", 70)],
            movement_pattern="squat",
        )
        plan = _build_plan(athlete, exercise, plan_id=5002, day_id=5102,
                           training_type=TrainingType.STRENGTH, reps_min=3, reps_max=5)
        request = _request(
            athlete, plan, 5102, exercise.id,
            sets_data=[{"weight": 80.0, "reps": 5, "rpe": 8.0, "form_quality": "excellent"}],
            recovery_kwargs={"sleep_quality": "excellent", "sleep_hours": 8.0,
                             "overall_soreness": 2, "stress_level": 3, "energy_level": 8},
            overall_rpe=8.5,
        )
        response = client.post("/api/analysis/sessions", json=request.model_dump(mode="json"))
        assert response.status_code == 200, response.text
        data = response.json()
        assert "ai_insights" in data
        assert "next_workout" in data
