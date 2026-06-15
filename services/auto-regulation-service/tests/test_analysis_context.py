"""
Unit tests for the Analysis Context seam — the immutable, load-once input the
progressive-overload engine computes over. The context object is the engine's
test surface: construct one, no scattered DB/HTTP mocking.
"""
from app.modules.analysis import AnalysisContext, AnalysisRequest


def _request_payload() -> dict:
    return {
        "athlete": {
            "id": 7,
            "age": 28,
            "gender": "male",
            "training_experience": "intermediate",
            "rpe_calibration_factor": 1.0,
            "body_weight_kg": 82.0,
        },
        "session": {
            "id": 42,
            "athlete_id": 7,
            "workout_day_id": 3,
            "session_date": "2026-06-14T10:00:00",
            "overall_rpe": 8.0,
            "sets": [
                {"id": 1, "workout_session_id": 42, "exercise_id": 5, "set_number": 1, "weight": 100.0, "reps": 5, "rpe": 8.0},
                {"id": 2, "workout_session_id": 42, "exercise_id": 5, "set_number": 2, "weight": 100.0, "reps": 5, "rpe": 8.5},
                {"id": 3, "workout_session_id": 42, "exercise_id": 9, "set_number": 1, "weight": 40.0, "reps": 12, "rpe": 7.0},
            ],
        },
        "recovery": {
            "id": 1, "athlete_id": 7, "date": "2026-06-14T07:00:00", "sleep_quality": "good",
        },
        "personal_records": [
            {"exercise_id": 5, "one_rep_max": 120.0, "total_pr_count": 3},
        ],
    }


def test_analysis_request_parses_pushed_payload():
    req = AnalysisRequest.model_validate(_request_payload())
    assert req.athlete.id == 7
    assert len(req.session.sets) == 3
    assert req.recovery.sleep_quality == "good"
    assert req.personal_records[0].one_rep_max == 120.0


def test_analysis_context_accessors():
    req = AnalysisRequest.model_validate(_request_payload())
    ctx = AnalysisContext(
        athlete=req.athlete,
        plan=req.plan,
        session=req.session,
        recovery=req.recovery,
        personal_records={pr.exercise_id: pr for pr in req.personal_records},
        current_plan_entry=None,
        recent_performance_trends=[],
        exercise_progressions={},
        rpe_calibrations={},
        form_trends={},
    )

    assert ctx.athlete_id == 7
    assert len(ctx.sets) == 3
    assert sorted(ctx.exercise_ids) == [5, 9]
    assert ctx.pr_for(5).one_rep_max == 120.0
    assert ctx.pr_for(9) is None  # no PR pushed for this exercise yet


def test_analysis_context_is_immutable():
    req = AnalysisRequest.model_validate(_request_payload())
    ctx = AnalysisContext(
        athlete=req.athlete, plan=None, session=req.session, recovery=None,
        personal_records={}, current_plan_entry=None, recent_performance_trends=[],
        exercise_progressions={}, rpe_calibrations={}, form_trends={},
    )
    import dataclasses
    try:
        ctx.athlete = None  # type: ignore[misc]
        assert False, "AnalysisContext must be frozen"
    except dataclasses.FrozenInstanceError:
        pass
