"""
Tests for edge cases and robustness of current AI engine implementation.
"""
import json
import pytest
from datetime import datetime, timedelta
from app.services.injury_prevention import InjuryPreventionService
from app.models import (
    Athlete, Exercise, WorkoutSession, ExerciseSet
)
from app.utils.constants import Gender, TrainingExperience


class TestInjuryPreventionRobustness:
    """Test that injury prevention service handles edge cases correctly."""
    
    def test_injury_prevention_handles_missing_form_data(self, db_session):
        """Test that injury prevention works correctly when form quality data is missing."""
        # Create athlete
        athlete = Athlete(
            age=25,
            gender=Gender.MALE,
            training_experience=TrainingExperience.INTERMEDIATE,
            rpe_calibration_factor=1.0
        )
        db_session.add(athlete)
        db_session.flush()
        
        # Create exercise
        exercise = Exercise(
            name="Bench Press",
            primary_muscles=json.dumps(["chest"]),  # Serialize for SQLite
            exercise_type="compound"
        )
        db_session.add(exercise)
        db_session.flush()
        
        # Create workout session WITHOUT form quality data
        session = WorkoutSession(
            athlete_id=athlete.id,
            workout_day_id=1,
            session_date=datetime.utcnow()
        )
        db_session.add(session)
        db_session.flush()
        
        # Add sets without form quality
        for set_num in range(1, 4):
            ex_set = ExerciseSet(
                workout_session_id=session.id,
                exercise_id=exercise.id,
                set_number=set_num,
                weight=100.0,
                reps=5,
                rpe=8.0,
                form_quality=None  # No form data
            )
            db_session.add(ex_set)
        
        db_session.commit()
        
        # Test form degradation check - should handle missing form data gracefully
        service = InjuryPreventionService(db_session)
        result = service.check_form_degradation(athlete.id, sessions_to_check=1)
        
        # Should return valid result structure even without form data
        assert "warnings" in result
        assert "poor_form_percentage" in result
        assert "exercise_analysis" in result
        assert "chronic_issues" in result
        
        # Should not crash
        assert isinstance(result["warnings"], list)
        assert isinstance(result["poor_form_percentage"], (int, float))
    
    def test_injury_prevention_handles_no_sessions(self, db_session):
        """Test that injury prevention handles athletes with no workout sessions."""
        # Create athlete
        athlete = Athlete(
            age=25,
            gender=Gender.MALE,
            training_experience=TrainingExperience.INTERMEDIATE,
            rpe_calibration_factor=1.0
        )
        db_session.add(athlete)
        db_session.flush()
        
        # Test that check_form_degradation works correctly with no sessions
        service = InjuryPreventionService(db_session)
        
        # Should handle case with no sessions gracefully
        result = service.check_form_degradation(athlete.id, sessions_to_check=3)
        
        assert "warnings" in result
        assert "poor_form_percentage" in result
        assert result["poor_form_percentage"] == 0.0  # No sessions = 0%
        assert len(result["warnings"]) == 0  # No warnings if no data
    
class TestFormQualityServiceRobustness:
    """Test that form quality service handles edge cases correctly."""
    
    def test_form_quality_service_handles_missing_data(self, db_session):
        """Test that form quality service handles missing data gracefully."""
        from app.services.form_quality_service import FormQualityService
        
        # Create athlete
        athlete = Athlete(
            age=25,
            gender=Gender.MALE,
            training_experience=TrainingExperience.INTERMEDIATE,
            rpe_calibration_factor=1.0
        )
        db_session.add(athlete)
        db_session.flush()
        
        # Create exercise
        exercise = Exercise(
            name="Bench Press",
            primary_muscles=json.dumps(["chest"]),  # Serialize for SQLite
            exercise_type="compound"
        )
        db_session.add(exercise)
        db_session.flush()
        
        service = FormQualityService(db_session)
        
        # Test getting trend with no data
        trend = service.get_form_quality_trend(athlete.id, exercise.id, days_lookback=14)
        
        assert trend["has_data"] is False
        assert trend["average_score"] is None
        assert trend["session_count"] == 0
        
        # Test detecting chronic issues with no data
        issues = service.detect_chronic_form_issues(athlete.id, exercise.id, days_lookback=14)
        
        assert issues["has_issues"] is False
        assert len(issues["issues"]) == 0
        assert len(issues["affected_exercises"]) == 0
        
        # Test generating alerts with no data
        alerts = service.generate_form_alerts(athlete.id, exercise.id, days_lookback=14)
        
        assert isinstance(alerts, list)
        assert len(alerts) == 0
        
        # Test should_block_progression with no data
        should_block, reason = service.should_block_progression(athlete.id, exercise.id)
        
        assert should_block is False
        assert reason is None

