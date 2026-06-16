"""
Integration test for the progressive-overload workflow via /api/analysis/sessions.
"""
import pytest

from tests.factories import (
    AthleteFactory, ExerciseFactory, WorkoutPlanFactory, WorkoutDayFactory,
    WorkoutDayExerciseFactory, WorkoutSessionFactory, ExerciseSetFactory,
    RecoveryMetricsFactory,
)


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


@pytest.fixture
def setup_progressive_program():
    athlete = AthleteFactory.create(age=25)
    exercise = ExerciseFactory.create_compound(name="Back Squat", movement_pattern="squat")
    day_id, plan_id = 3001, 4001
    day_exercise = WorkoutDayExerciseFactory.create(
        exercise_id=exercise.id, workout_day_id=day_id, target_reps_min=8, target_reps_max=12,
    )
    day = WorkoutDayFactory.create(id=day_id, workout_plan_id=plan_id, exercises=[day_exercise])
    plan = WorkoutPlanFactory.create(id=plan_id, athlete_id=athlete.id, days=[day])
    return {"athlete": athlete, "exercise": exercise, "plan": plan, "day_id": day_id}


@pytest.mark.integration
class TestProgressiveOverloadWorkflow:
    def test_single_progression_workflow(self, client, db_session, setup_progressive_program):
        s = setup_progressive_program
        request = _request(
            s["athlete"], s["plan"], s["day_id"], s["exercise"].id,
            sets_data=[{"weight": 60.0, "reps": 10, "rpe": 7.0 + i, "form_quality": "good"} for i in range(1, 4)],
            recovery_kwargs={"sleep_quality": "good", "sleep_hours": 7.5,
                             "overall_soreness": 2, "stress_level": 3, "energy_level": 8},
            overall_rpe=7.5,
        )
        response = client.post("/api/analysis/sessions", json=request.model_dump(mode="json"))
        assert response.status_code == 200, response.text
        data = response.json()
        assert "ai_insights" in data
        assert "next_workout" in data
        assert "performance_analysis" in data
        assert "adjustments" in data

    def test_recovery_tracking_workflow(self, client, db_session, setup_progressive_program):
        s = setup_progressive_program
        request = _request(
            s["athlete"], s["plan"], s["day_id"], s["exercise"].id,
            sets_data=[{"weight": 70.0, "reps": 10, "rpe": 8.0, "form_quality": "good"}],
            recovery_kwargs={"sleep_quality": "good", "sleep_hours": 7.5,
                             "overall_soreness": 3, "stress_level": 4, "energy_level": 7},
        )
        response = client.post("/api/analysis/sessions", json=request.model_dump(mode="json"))
        assert response.status_code == 200, response.text
        data = response.json()
        assert "ai_insights" in data
        assert "next_workout" in data
