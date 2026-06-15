"""
Robustness tests for injury prevention + form quality (local algo tables).

Injury form-degradation now reads auto-regulation's own form_quality_trends; with
no local data the services degrade gracefully.
"""
import pytest

from app.modules.injury import InjuryPreventionService
from app.modules.form import FormQualityService
from tests.factories import AthleteFactory, ExerciseFactory


@pytest.mark.integration
@pytest.mark.slow
class TestInjuryPreventionRobustness:
    def test_form_degradation_with_no_local_data(self, db_session):
        athlete = AthleteFactory.create()
        ExerciseFactory.create_compound(name="Bench Press")

        service = InjuryPreventionService(db_session)
        result = service.check_form_degradation(athlete.id)

        # New shape: derived from local form_quality_trends (empty -> no warnings)
        assert "warnings" in result
        assert "alert_count" in result
        assert "chronic_issues" in result
        assert isinstance(result["warnings"], list)
        assert len(result["warnings"]) == 0

    def test_form_degradation_handles_unknown_athlete(self, db_session):
        service = InjuryPreventionService(db_session)
        result = service.check_form_degradation(999999)
        assert result["warnings"] == []
        assert result["chronic_issues"]["has_issues"] is False


@pytest.mark.integration
@pytest.mark.slow
class TestFormQualityServiceRobustness:
    def test_form_quality_service_handles_missing_data(self, db_session):
        athlete = AthleteFactory.create()
        exercise = ExerciseFactory.create_compound(name="Bench Press")
        service = FormQualityService(db_session)

        trend = service.get_form_quality_trend(athlete.id, exercise.id, days_lookback=14)
        assert trend["has_data"] is False
        assert trend["average_score"] is None
        assert trend["session_count"] == 0

        issues = service.detect_chronic_form_issues(athlete.id, exercise.id, days_lookback=14)
        assert issues["has_issues"] is False
        assert len(issues["issues"]) == 0
        assert len(issues["affected_exercises"]) == 0

        alerts = service.generate_form_alerts(athlete.id, exercise.id, days_lookback=14)
        assert isinstance(alerts, list)
        assert len(alerts) == 0

        should_block, reason = service.should_block_progression(athlete.id, exercise.id)
        assert should_block is False
        assert reason is None
