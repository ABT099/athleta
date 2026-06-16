"""
Integration tests for intensity-technique recommendations through the analyze endpoint.

api persists the logged session (with the set types the athlete actually used) and
pushes it — together with the athlete, active plan and recovery — to
POST /api/analysis/sessions. Auto-regulation computes over that context and returns
the next workout, whose exercises carry the recommended ``set_type`` / ``rep_style``
(+ their params). These tests drive that endpoint end to end.

Set-data *validation* (rejecting an unknown set type) and set *storage* are api-owned
concerns now, so the former "invalid set type -> 422" and "technique stored in
ExerciseSet" cases live in the api test suite, not here. Plateau/struggling trigger
logic is covered directly in tests/integration/features/test_progressive_overload.py.
"""
import pytest

from app.modules.analysis import AnalysisRequest
from app.utils.constants import SetType
from tests.factories import (
    AthleteFactory, ExerciseFactory, WorkoutPlanFactory, WorkoutDayFactory,
    WorkoutDayExerciseFactory, WorkoutSessionFactory, ExerciseSetFactory,
    RecoveryMetricsFactory,
)


@pytest.fixture
def setup_athlete_with_plan():
    """Intermediate athlete + 3 exercises + an active push-day plan, all as DTOs."""
    athlete = AthleteFactory.create(age=28)
    bench_press = ExerciseFactory.create_compound(
        name="Bench Press",
        muscles=[("mid_chest", 90), ("anterior_delt", 70), ("triceps", 60)],
    )
    tricep_pushdown = ExerciseFactory.create_isolation(
        name="Tricep Pushdown", muscles=[("triceps", 95)]
    )
    bicep_curl = ExerciseFactory.create_isolation(
        name="Bicep Curl", muscles=[("biceps", 95)]
    )

    day_id, plan_id = 1001, 2001
    day = WorkoutDayFactory.create(
        id=day_id, workout_plan_id=plan_id, name="Push Day",
        exercises=[
            WorkoutDayExerciseFactory.create(
                exercise_id=bench_press.id, workout_day_id=day_id, order_in_workout=1,
                is_primary=True, target_sets_min=4, target_sets_max=4,
                target_reps_min=6, target_reps_max=8,
            ),
            WorkoutDayExerciseFactory.create(
                exercise_id=tricep_pushdown.id, workout_day_id=day_id, order_in_workout=2,
                is_primary=False, target_sets_min=3, target_sets_max=3,
                target_reps_min=10, target_reps_max=12,
            ),
            WorkoutDayExerciseFactory.create(
                exercise_id=bicep_curl.id, workout_day_id=day_id, order_in_workout=3,
                is_primary=False, target_sets_min=3, target_sets_max=3,
                target_reps_min=10, target_reps_max=12,
            ),
        ],
    )
    plan = WorkoutPlanFactory.create(id=plan_id, athlete_id=athlete.id, days=[day])
    return {
        "athlete": athlete,
        "plan": plan,
        "day_id": day_id,
        "exercises": {
            "bench_press": bench_press,
            "bicep_curl": bicep_curl,
            "tricep_pushdown": tricep_pushdown,
        },
    }


def _post_analysis(client, setup, sets_data, recovery_kwargs=None, overall_rpe=8.0):
    """Build the analyze request api would push (session + sets + recovery) and POST it."""
    sets = [
        ExerciseSetFactory.create(set_number=i, **sd)
        for i, sd in enumerate(sets_data, start=1)
    ]
    session = WorkoutSessionFactory.create(
        athlete_id=setup["athlete"].id, workout_day_id=setup["day_id"],
        overall_rpe=overall_rpe, duration_minutes=60, sets=sets,
    )
    # keep each set's session id consistent with the session
    session = session.model_copy(update={
        "sets": [s.model_copy(update={"workout_session_id": session.id}) for s in sets]
    })
    recovery = RecoveryMetricsFactory.create(
        athlete_id=setup["athlete"].id, date=session.session_date,
        **(recovery_kwargs or {"sleep_quality": "good", "sleep_hours": 7.5}),
    )
    request = AnalysisRequest(
        athlete=setup["athlete"], plan=setup["plan"], session=session,
        recovery=recovery, personal_records=[],
    )
    return client.post("/api/analysis/sessions", json=request.model_dump(mode="json"))


@pytest.mark.integration
@pytest.mark.slow
class TestCompleteWorkoutWithTechniques:
    """The analyze endpoint accepts sessions logged with any set type."""

    def test_complete_workout_with_straight_sets(self, client, db_session, setup_athlete_with_plan):
        s = setup_athlete_with_plan
        resp = _post_analysis(
            client, s,
            sets_data=[
                {"exercise_id": s["exercises"]["bench_press"].id, "weight": 80.0, "reps": 8,
                 "rpe": 7.5, "set_type_used": "straight", "rep_style_used": "normal"},
                {"exercise_id": s["exercises"]["bench_press"].id, "weight": 80.0, "reps": 7,
                 "rpe": 8.0, "set_type_used": "straight", "rep_style_used": "normal"},
            ],
            recovery_kwargs={"sleep_quality": "good", "sleep_hours": 7.5,
                             "overall_soreness": 3, "stress_level": 4, "energy_level": 7},
            overall_rpe=7.5,
        )
        assert resp.status_code == 200, resp.text
        assert "next_workout" in resp.json()

    def test_complete_workout_with_drop_set(self, client, db_session, setup_athlete_with_plan):
        s = setup_athlete_with_plan
        resp = _post_analysis(
            client, s,
            sets_data=[
                {"exercise_id": s["exercises"]["bench_press"].id, "weight": 80.0, "reps": 8,
                 "rpe": 8.0, "set_type_used": "straight", "rep_style_used": "normal"},
                {"exercise_id": s["exercises"]["bicep_curl"].id, "weight": 15.0, "reps": 18,
                 "rpe": 9.0, "set_type_used": "drop_set", "rep_style_used": "normal",
                 "technique_details": {"drop_percentage": 0.20, "drops_count": 1,
                                       "total_reps_with_drops": 18}},
            ],
            recovery_kwargs={"sleep_quality": "good", "sleep_hours": 7.0},
            overall_rpe=8.0,
        )
        assert resp.status_code == 200, resp.text
        assert "next_workout" in resp.json()

    def test_complete_workout_with_myo_reps(self, client, db_session, setup_athlete_with_plan):
        s = setup_athlete_with_plan
        resp = _post_analysis(
            client, s,
            sets_data=[
                {"exercise_id": s["exercises"]["tricep_pushdown"].id, "weight": 25.0, "reps": 20,
                 "rpe": 8.5, "set_type_used": "myo_reps", "rep_style_used": "normal",
                 "technique_details": {"activation_reps": 12, "mini_sets": [5, 4, 3, 3],
                                       "rest_seconds": 5}},
            ],
            recovery_kwargs={"sleep_quality": "good", "sleep_hours": 8.0},
            overall_rpe=8.0,
        )
        assert resp.status_code == 200, resp.text

    def test_struggling_performance_completes(self, client, db_session, setup_athlete_with_plan):
        """A high-RPE struggling session still computes and returns a next workout."""
        s = setup_athlete_with_plan
        resp = _post_analysis(
            client, s,
            sets_data=[
                {"exercise_id": s["exercises"]["bicep_curl"].id, "weight": 15.0, "reps": 10,
                 "rpe": 9.0, "set_type_used": "straight", "rep_style_used": "normal"}
                for _ in range(3)
            ],
            recovery_kwargs={"sleep_quality": "good", "sleep_hours": 7.0},
            overall_rpe=8.5,
        )
        assert resp.status_code == 200, resp.text
        assert "next_workout" in resp.json()


@pytest.mark.integration
@pytest.mark.slow
class TestTechniqueRecommendationWorkflow:
    """The returned next workout carries per-exercise technique recommendations."""

    def test_next_workout_carries_technique_fields(self, client, db_session, setup_athlete_with_plan):
        s = setup_athlete_with_plan
        resp = _post_analysis(
            client, s,
            sets_data=[
                {"exercise_id": s["exercises"]["bench_press"].id, "weight": 80.0, "reps": 8,
                 "rpe": 7.0, "set_type_used": "straight", "rep_style_used": "normal"}
                for _ in range(3)
            ],
            recovery_kwargs={"sleep_quality": "good", "sleep_hours": 7.5},
            overall_rpe=7.0,
        )
        assert resp.status_code == 200, resp.text

        next_workout = resp.json()["next_workout"]
        exercises = next_workout["workout_day"]["exercises"]
        assert len(exercises) > 0
        valid_set_types = {st.value for st in SetType}
        for exercise in exercises:
            # set_type / rep_style always resolve to a concrete, valid value
            # (defaulting to straight / normal when no technique is recommended)
            assert exercise["set_type"] in valid_set_types
            assert exercise["rep_style"] is not None
            # params are a dict when a technique applies, else None — never some other
            # type (the empty-dict-preservation invariant from generate_next_workout)
            assert exercise["set_type_params"] is None or isinstance(exercise["set_type_params"], dict)
            assert exercise["rep_style_params"] is None or isinstance(exercise["rep_style_params"], dict)

    def test_technique_details_accepted(self, client, db_session, setup_athlete_with_plan):
        """A logged set may carry an arbitrary technique_details payload."""
        s = setup_athlete_with_plan
        resp = _post_analysis(
            client, s,
            sets_data=[
                {"exercise_id": s["exercises"]["bicep_curl"].id, "weight": 15.0, "reps": 18,
                 "rpe": 9.0, "set_type_used": "drop_set", "rep_style_used": "normal",
                 "technique_details": {"drop_percentage": 0.20, "drops_count": 2,
                                       "weight_sequence": [15.0, 12.0, 9.5],
                                       "reps_sequence": [10, 5, 3]}},
            ],
            recovery_kwargs={"sleep_quality": "good", "sleep_hours": 7.0},
        )
        assert resp.status_code == 200, resp.text


@pytest.mark.integration
@pytest.mark.slow
class TestBeginnerDoesNotGetAdvancedTechniques:
    """Beginners are never prescribed advanced, high-fatigue techniques."""

    def test_beginner_gets_straight_sets_only(self, client, db_session):
        athlete = AthleteFactory.create_beginner()
        exercise = ExerciseFactory.create_isolation(
            name="Lateral Raise", muscles=[("lateral_delt", 95)]
        )
        day_id, plan_id = 1101, 2101
        day = WorkoutDayFactory.create(
            id=day_id, workout_plan_id=plan_id, name="Shoulders",
            exercises=[WorkoutDayExerciseFactory.create(
                exercise_id=exercise.id, workout_day_id=day_id, order_in_workout=1,
                is_primary=False, target_sets_min=3, target_sets_max=3,
                target_reps_min=10, target_reps_max=12,
            )],
        )
        plan = WorkoutPlanFactory.create(id=plan_id, athlete_id=athlete.id, days=[day])
        setup = {"athlete": athlete, "plan": plan, "day_id": day_id}

        resp = _post_analysis(
            client, setup,
            sets_data=[
                {"exercise_id": exercise.id, "weight": 10.0, "reps": 10, "rpe": 9.0,
                 "set_type_used": "straight", "rep_style_used": "normal"}
                for _ in range(3)
            ],
            recovery_kwargs={"sleep_quality": "good", "sleep_hours": 7.0},
            overall_rpe=9.0,
        )
        assert resp.status_code == 200, resp.text

        exercises = resp.json()["next_workout"]["workout_day"]["exercises"]
        assert len(exercises) > 0
        for exercise_out in exercises:
            # even struggling, a beginner is not handed advanced techniques
            assert exercise_out["set_type"] not in (
                SetType.CLUSTER_SET.value, SetType.MYO_REPS.value,
                SetType.REST_PAUSE.value,
            )
