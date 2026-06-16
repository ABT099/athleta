"""
Tests for extended workout break detection and detraining adjustments.

Break detection reads auto-regulation's local performance_trends (the latest
trend's date == the last session date), so these tests seed a PerformanceTrend
N days ago and compute over an in-memory AnalysisContext.
"""
import pytest
from datetime import datetime, timedelta, timezone

from app.modules.progression.progressive_overload_engine import ProgressiveOverloadEngine
from app.modules.analysis import AnalysisContext
from app.clients.api_client import AthleteDTO
from app.utils.constants import TrainingType, TrainingPhase, TrainingExperience
from tests.factories import WorkoutSessionFactory, PerformanceTrendFactory


def _ctx(athlete_id: int = 1, experience: TrainingExperience = TrainingExperience.INTERMEDIATE) -> AnalysisContext:
    athlete = AthleteDTO(
        id=athlete_id, age=25, gender="male", training_experience=experience,
        rpe_calibration_factor=1.0, body_weight_kg=80.0,
    )
    session = WorkoutSessionFactory.create(athlete_id=athlete_id, workout_day_id=1, sets=[])
    return AnalysisContext(
        athlete=athlete, plan=None, session=session, recovery=None, personal_records={},
        current_plan_entry=None, recent_performance_trends=[], exercise_progressions={},
        rpe_calibrations={}, form_trends={},
    )


def _seed_last_session(db, athlete_id, days_ago):
    PerformanceTrendFactory.create(
        db, athlete_id=athlete_id,
        session_date=datetime.now(timezone.utc) - timedelta(days=days_ago),
    )
    db.commit()


_PLAN_CONTEXT = {
    "has_plan": True, "plan_id": 1, "training_type": TrainingType.HYPERTROPHY,
    "current_phase": TrainingPhase.ACCUMULATION, "week_number": 1, "is_deload_week": False,
    "target_volume_multiplier": 1.0, "target_intensity_multiplier": 1.0,
}
_PERFORMANCE = {"performance_level": "on_target", "exercise_analyses": []}
_RECOVERY = {"readiness_score": 0.8, "fatigue_status": {"fatigue_level": "low"}, "needs_deload": False}
_INJURY_LOW = {"risk_level": "low", "warnings": []}


@pytest.mark.unit
class TestExtendedBreakDetection:
    def test_no_previous_workouts(self, db_session):
        engine = ProgressiveOverloadEngine(db_session)
        days_since, vol, intensity = engine._detect_extended_break(1)
        assert days_since is None and vol is None and intensity is None

    def test_break_less_than_7_days(self, db_session):
        _seed_last_session(db_session, athlete_id=1, days_ago=5)
        engine = ProgressiveOverloadEngine(db_session)
        days_since, vol, intensity = engine._detect_extended_break(1)
        assert days_since is None and vol is None and intensity is None

    @pytest.mark.parametrize("days_ago,expected_mult", [(10, 0.85), (17, 0.75), (30, 0.60)])
    def test_break_detection_reductions(self, db_session, days_ago, expected_mult):
        _seed_last_session(db_session, athlete_id=1, days_ago=days_ago)
        engine = ProgressiveOverloadEngine(db_session)
        days_since, vol, intensity = engine._detect_extended_break(1)
        assert days_since == days_ago
        assert vol == expected_mult
        assert intensity == expected_mult


@pytest.mark.unit
class TestBreakDetectionIntegration:
    def test_break_detection_applies_to_parameters(self, db_session):
        _seed_last_session(db_session, athlete_id=1, days_ago=10)
        engine = ProgressiveOverloadEngine(db_session)
        adjustments = engine.calculate_next_workout_parameters(
            ctx=_ctx(1), plan_context=_PLAN_CONTEXT, performance=_PERFORMANCE,
            recovery=_RECOVERY, injury_risk=_INJURY_LOW,
        )
        assert adjustments["volume_multiplier"] < 1.0
        assert adjustments["intensity_multiplier"] < 1.0
        assert "Extended break" in adjustments["reasoning"]
        assert "10" in adjustments["reasoning"]

    def test_break_detection_reasoning_includes_break_info(self, db_session):
        _seed_last_session(db_session, athlete_id=1, days_ago=17)
        engine = ProgressiveOverloadEngine(db_session)
        adjustments = engine.calculate_next_workout_parameters(
            ctx=_ctx(1), plan_context=_PLAN_CONTEXT, performance=_PERFORMANCE,
            recovery=_RECOVERY, injury_risk=_INJURY_LOW,
        )
        assert "Extended break" in adjustments["reasoning"]

    def test_deload_week_overrides_break_detection(self, db_session):
        _seed_last_session(db_session, athlete_id=1, days_ago=10)
        engine = ProgressiveOverloadEngine(db_session)
        plan_context = {**_PLAN_CONTEXT, "is_deload_week": True}
        adjustments = engine.calculate_next_workout_parameters(
            ctx=_ctx(1), plan_context=plan_context, performance=_PERFORMANCE,
            recovery=_RECOVERY, injury_risk=_INJURY_LOW,
        )
        assert adjustments["volume_multiplier"] == 0.5
        assert adjustments["intensity_multiplier"] == 0.9
        assert "deload week" in adjustments["reasoning"].lower()
        assert "Extended break" not in adjustments["reasoning"]

    def test_high_injury_risk_overrides_break_detection(self, db_session):
        _seed_last_session(db_session, athlete_id=1, days_ago=10)
        engine = ProgressiveOverloadEngine(db_session)
        injury_high = {"risk_level": "high", "warnings": ["Test warning"]}
        adjustments = engine.calculate_next_workout_parameters(
            ctx=_ctx(1), plan_context=_PLAN_CONTEXT, performance=_PERFORMANCE,
            recovery=_RECOVERY, injury_risk=injury_high,
        )
        assert adjustments["volume_multiplier"] == 0.5
        assert adjustments["intensity_multiplier"] == 0.85
        assert "injury risk" in adjustments["reasoning"].lower()
        assert "Extended break" not in adjustments["reasoning"]

    def test_break_detection_applies_after_moderate_injury_risk(self, db_session):
        _seed_last_session(db_session, athlete_id=1, days_ago=10)
        engine = ProgressiveOverloadEngine(db_session)
        injury_moderate = {"risk_level": "moderate", "warnings": ["Watch volume"]}
        adjustments = engine.calculate_next_workout_parameters(
            ctx=_ctx(1), plan_context=_PLAN_CONTEXT, performance=_PERFORMANCE,
            recovery=_RECOVERY, injury_risk=injury_moderate,
        )
        # Moderate injury does not early-return, so the break reduction still applies.
        assert adjustments["volume_multiplier"] < 1.0
        assert adjustments["intensity_multiplier"] < 1.0
        assert "Extended break" in adjustments["reasoning"]
