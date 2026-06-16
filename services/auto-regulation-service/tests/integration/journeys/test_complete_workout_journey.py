"""
Integration test for the workout-analysis workflow.

api persists the logged session and pushes it (with the athlete, active plan and
recovery) to POST /api/analysis/sessions. Auto-regulation computes over that
context + its own local history, writes only its own algo tables, and returns the
adjustments + write-backs. These tests drive that endpoint end to end.
"""
import pytest

from app.models import PerformanceTrend
from tests.factories import (
    AthleteFactory, ExerciseFactory, WorkoutPlanFactory, WorkoutDayFactory,
    WorkoutDayExerciseFactory, WorkoutSessionFactory, ExerciseSetFactory,
    RecoveryMetricsFactory,
)


def _analysis_request(athlete, plan, day_id, exercise_id, sets_data, recovery_kwargs):
    sets = [
        ExerciseSetFactory.create(exercise_id=exercise_id, set_number=i, **sd)
        for i, sd in enumerate(sets_data, start=1)
    ]
    session = WorkoutSessionFactory.create(
        athlete_id=athlete.id, workout_day_id=day_id, overall_rpe=8.0,
        duration_minutes=60, sets=sets,
    )
    # keep the sets' session id consistent
    session = session.model_copy(update={"sets": [s.model_copy(update={"workout_session_id": session.id}) for s in sets]})
    recovery = RecoveryMetricsFactory.create(
        athlete_id=athlete.id, date=session.session_date, **recovery_kwargs
    )
    from app.modules.analysis import AnalysisRequest
    return AnalysisRequest(athlete=athlete, plan=plan, session=session, recovery=recovery, personal_records=[])


@pytest.fixture
def workout_setup():
    """Athlete + exercise (fake) + active plan (day + day-exercise), all as DTOs."""
    athlete = AthleteFactory.create(age=25)
    exercise = ExerciseFactory.create_compound(name="Bench Press")
    day_id, plan_id = 1001, 2001
    day_exercise = WorkoutDayExerciseFactory.create(
        exercise_id=exercise.id, workout_day_id=day_id,
        target_reps_min=8, target_reps_max=12, target_rpe=8.0,
    )
    day = WorkoutDayFactory.create(id=day_id, workout_plan_id=plan_id, exercises=[day_exercise])
    plan = WorkoutPlanFactory.create(id=plan_id, athlete_id=athlete.id, days=[day])
    return {"athlete": athlete, "exercise": exercise, "plan": plan, "day_id": day_id}


@pytest.mark.integration
@pytest.mark.smoke
class TestAnalysisWorkflow:
    def test_analysis_full_workflow(self, client, db_session, workout_setup):
        s = workout_setup
        request = _analysis_request(
            s["athlete"], s["plan"], s["day_id"], s["exercise"].id,
            sets_data=[
                {"weight": 100.0, "reps": 10, "rpe": 8.0, "form_quality": "good"},
                {"weight": 100.0, "reps": 10, "rpe": 8.5, "form_quality": "good"},
                {"weight": 100.0, "reps": 9, "rpe": 9.0, "form_quality": "fair"},
            ],
            recovery_kwargs={"sleep_quality": "good", "sleep_hours": 7.5,
                             "overall_soreness": 3, "stress_level": 4, "energy_level": 7},
        )

        response = client.post("/api/analysis/sessions", json=request.model_dump(mode="json"))
        assert response.status_code == 200, response.text
        data = response.json()

        # New response shape (write-backs for api + adjustments)
        for key in ("adjustments", "next_workout", "performance_analysis", "ai_insights",
                    "pr_updates", "calibration_factor"):
            assert key in data, f"missing {key}"

        performance = data["performance_analysis"]
        assert performance["total_volume"] > 0
        assert len(performance["exercise_analyses"]) > 0

        assert isinstance(data["ai_insights"], list)
        assert isinstance(data["calibration_factor"], (int, float))

        next_workout = data["next_workout"]
        assert "workout_day" in next_workout
        assert "adjustments_summary" in next_workout
        assert "injury_warnings" in next_workout
        assert "recovery_recommendations" in next_workout

        # PR detection ran and produced write-backs (first-ever sets are all PRs)
        assert isinstance(data["pr_updates"]["updates"], list)
        assert len(data["pr_updates"]["updates"]) > 0

    def test_analysis_creates_performance_trend(self, client, db_session, workout_setup):
        s = workout_setup
        initial = db_session.query(PerformanceTrend).filter(
            PerformanceTrend.athlete_id == s["athlete"].id
        ).count()

        request = _analysis_request(
            s["athlete"], s["plan"], s["day_id"], s["exercise"].id,
            sets_data=[{"weight": 100.0, "reps": 10, "rpe": 8.0}],
            recovery_kwargs={"sleep_quality": "good", "sleep_hours": 7.5},
        )
        response = client.post("/api/analysis/sessions", json=request.model_dump(mode="json"))
        assert response.status_code == 200, response.text

        db_session.commit()
        trend = db_session.query(PerformanceTrend).filter(
            PerformanceTrend.athlete_id == s["athlete"].id
        ).order_by(PerformanceTrend.session_date.desc()).first()

        assert db_session.query(PerformanceTrend).filter(
            PerformanceTrend.athlete_id == s["athlete"].id
        ).count() == initial + 1
        assert trend is not None
        assert trend.total_volume is not None
        assert trend.average_rpe is not None
        assert trend.readiness_score is not None
        assert trend.performance_score is not None

    def test_poor_recovery_surfaces_recovery_guidance(self, client, db_session, workout_setup):
        s = workout_setup
        request = _analysis_request(
            s["athlete"], s["plan"], s["day_id"], s["exercise"].id,
            sets_data=[{"weight": 100.0, "reps": 10, "rpe": 8.0}],
            recovery_kwargs={"sleep_quality": "poor", "sleep_hours": 5.0,
                             "overall_soreness": 8, "stress_level": 9, "energy_level": 2},
        )
        response = client.post("/api/analysis/sessions", json=request.model_dump(mode="json"))
        assert response.status_code == 200, response.text
        data = response.json()

        next_workout = data["next_workout"]
        recovery_recs = next_workout.get("recovery_recommendations", [])
        insights = data["ai_insights"]
        volume_mult = data["adjustments"].get("volume_multiplier")

        text = (" ".join(insights) + " " + str(recovery_recs)).lower()
        recovery_mentioned = any(k in text for k in ["recovery", "rest", "sleep", "deload", "reduce"])
        assert (volume_mult is not None and volume_mult < 1.0) or recovery_mentioned
