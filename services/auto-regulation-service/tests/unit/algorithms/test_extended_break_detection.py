"""
Tests for extended workout break detection and detraining adjustments.

Tests that the system correctly detects extended breaks (7+ days) and
applies appropriate volume/intensity reductions to account for detraining.
"""
import pytest
from datetime import datetime, timedelta, timezone
from autoregulation.services.progressive_overload_engine import ProgressiveOverloadEngine
from autoregulation.models import (
    Athlete, WorkoutPlan, WorkoutDay, WorkoutSession, ExerciseSet
)
from autoregulation.utils.constants import (
    Gender, TrainingExperience, TrainingType, PeriodizationModel, TrainingPhase
)
from tests.factories import (
    AthleteFactory, WorkoutPlanFactory, WorkoutDayFactory, WorkoutSessionFactory
)


@pytest.mark.unit
class TestExtendedBreakDetection:
    """Test extended break detection method."""
    
    def test_no_previous_workouts(self, db_session):
        """Test that no adjustment is applied for first workout ever."""
        # Create athlete
        athlete = Athlete(
            age=25,
            gender=Gender.MALE,
            training_experience=TrainingExperience.INTERMEDIATE,
            rpe_calibration_factor=1.0
        )
        db_session.add(athlete)
        db_session.flush()
        
        engine = ProgressiveOverloadEngine(db_session)
        days_since, volume_mult, intensity_mult = engine._detect_extended_break(athlete.id)
        
        # Should return None for all values (no previous workouts)
        assert days_since is None
        assert volume_mult is None
        assert intensity_mult is None
    
    def test_break_less_than_7_days(self, db_session):
        """Test that no adjustment is applied for breaks < 7 days."""
        # Create athlete
        athlete = Athlete(
            age=25,
            gender=Gender.MALE,
            training_experience=TrainingExperience.INTERMEDIATE,
            rpe_calibration_factor=1.0
        )
        db_session.add(athlete)
        db_session.flush()
        
        # Create workout plan and day
        plan = WorkoutPlan(
            athlete_id=athlete.id,
            name="Test Plan",
            training_type=TrainingType.HYPERTROPHY,
            periodization_model=PeriodizationModel.LINEAR,
            frequency=3,
            duration_weeks=12,
            start_date=datetime.now(timezone.utc) - timedelta(days=30)
        )
        db_session.add(plan)
        db_session.flush()
        
        workout_day = WorkoutDay(
            workout_plan_id=plan.id,
            name="Test Day",
            day_of_week=0,
            order_in_week=1,
        )
        db_session.add(workout_day)
        db_session.flush()
        
        # Create workout session 5 days ago
        session = WorkoutSession(
            athlete_id=athlete.id,
            workout_day_id=workout_day.id,
            session_date=datetime.now(timezone.utc) - timedelta(days=5)
        )
        db_session.add(session)
        db_session.commit()
        
        engine = ProgressiveOverloadEngine(db_session)
        days_since, volume_mult, intensity_mult = engine._detect_extended_break(athlete.id)
        
        # Should return None (break < 7 days)
        assert days_since is None
        assert volume_mult is None
        assert intensity_mult is None
    
    @pytest.mark.parametrize("days_ago,expected_mult", [
        (10, 0.85),  # 7-13 days: 15% reduction
        (17, 0.75),  # 14-20 days: 25% reduction
        (30, 0.60),  # 21+ days: 40% reduction
    ])
    def test_break_detection_reductions(self, db_session, days_ago, expected_mult):
        """Test break detection with parametrized break durations."""
        # Create athlete using factory
        athlete = AthleteFactory.create(db_session)
        
        # Create workout plan and day using factories
        plan = WorkoutPlanFactory.create(db_session, athlete_id=athlete.id)
        workout_day = WorkoutDayFactory.create(db_session, workout_plan_id=plan.id)
        
        # Create workout session
        session = WorkoutSessionFactory.create(
            db_session,
            athlete_id=athlete.id,
            workout_day_id=workout_day.id,
            session_date=datetime.now(timezone.utc) - timedelta(days=days_ago)
        )
        db_session.commit()
        
        engine = ProgressiveOverloadEngine(db_session)
        days_since, volume_mult, intensity_mult = engine._detect_extended_break(athlete.id)
        
        # Verify break detection
        assert days_since == days_ago
        assert volume_mult == expected_mult
        assert intensity_mult == expected_mult


@pytest.mark.unit
class TestBreakDetectionIntegration:
    """Test break detection integration with workout parameter calculation."""
    
    def test_break_detection_applies_to_parameters(self, db_session):
        """Test that break detection reduces workout parameters."""
        # Create athlete
        athlete = Athlete(
            age=25,
            gender=Gender.MALE,
            training_experience=TrainingExperience.INTERMEDIATE,
            rpe_calibration_factor=1.0
        )
        db_session.add(athlete)
        db_session.flush()
        
        # Create workout plan and day
        plan = WorkoutPlan(
            athlete_id=athlete.id,
            name="Test Plan",
            training_type=TrainingType.HYPERTROPHY,
            periodization_model=PeriodizationModel.LINEAR,
            frequency=3,
            duration_weeks=12,
            start_date=datetime.now(timezone.utc) - timedelta(days=30)
        )
        db_session.add(plan)
        db_session.flush()
        
        workout_day = WorkoutDay(
            workout_plan_id=plan.id,
            name="Test Day",
            day_of_week=0,
            order_in_week=1,
        )
        db_session.add(workout_day)
        db_session.flush()
        
        # Create workout session 10 days ago
        session = WorkoutSession(
            athlete_id=athlete.id,
            workout_day_id=workout_day.id,
            session_date=datetime.now(timezone.utc) - timedelta(days=10)
        )
        db_session.add(session)
        db_session.commit()
        
        engine = ProgressiveOverloadEngine(db_session)
        
        # Create plan context
        plan_context = {
            "has_plan": True,
            "plan_id": plan.id,
            "training_type": TrainingType.HYPERTROPHY,
            "current_phase": TrainingPhase.ACCUMULATION,
            "week_number": 1,
            "is_deload_week": False,
            "target_volume_multiplier": 1.0,
            "target_intensity_multiplier": 1.0
        }
        
        # Create performance analysis (on target)
        performance = {
            "performance_level": "on_target",
            "exercise_analyses": []
        }
        
        # Create recovery data (good recovery)
        recovery = {
            "readiness_score": 0.8,
            "fatigue_status": {"fatigue_level": "low"},
            "needs_deload": False
        }
        
        # Create injury risk (low)
        injury_risk = {
            "risk_level": "low",
            "warnings": []
        }
        
        # Calculate parameters
        adjustments = engine.calculate_next_workout_parameters(
            athlete=athlete,
            plan_context=plan_context,
            performance=performance,
            recovery=recovery,
            injury_risk=injury_risk
        )
        
        # Volume and intensity should be reduced by 15% (0.85 multiplier)
        # But also affected by other factors, so check it's less than 1.0
        assert adjustments["volume_multiplier"] < 1.0
        assert adjustments["intensity_multiplier"] < 1.0
        
        # Reasoning should mention the break
        assert "Extended break" in adjustments["reasoning"]
        assert "10 days" in adjustments["reasoning"] or "10" in adjustments["reasoning"]
    
    def test_break_detection_reasoning_includes_break_info(self, db_session):
        """Test that reasoning message includes break information."""
        # Create athlete
        athlete = Athlete(
            age=25,
            gender=Gender.MALE,
            training_experience=TrainingExperience.INTERMEDIATE,
            rpe_calibration_factor=1.0
        )
        db_session.add(athlete)
        db_session.flush()
        
        # Create workout plan and day
        plan = WorkoutPlan(
            athlete_id=athlete.id,
            name="Test Plan",
            training_type=TrainingType.HYPERTROPHY,
            periodization_model=PeriodizationModel.LINEAR,
            frequency=3,
            duration_weeks=12,
            start_date=datetime.now(timezone.utc) - timedelta(days=30)
        )
        db_session.add(plan)
        db_session.flush()
        
        workout_day = WorkoutDay(
            workout_plan_id=plan.id,
            name="Test Day",
            day_of_week=0,
            order_in_week=1,
        )
        db_session.add(workout_day)
        db_session.flush()
        
        # Create workout session 25 days ago (should trigger 40% reduction)
        session = WorkoutSession(
            athlete_id=athlete.id,
            workout_day_id=workout_day.id,
            session_date=datetime.now(timezone.utc) - timedelta(days=25)
        )
        db_session.add(session)
        db_session.commit()
        
        engine = ProgressiveOverloadEngine(db_session)
        
        # Create plan context
        plan_context = {
            "has_plan": True,
            "plan_id": plan.id,
            "training_type": TrainingType.HYPERTROPHY,
            "current_phase": TrainingPhase.ACCUMULATION,
            "week_number": 1,
            "is_deload_week": False,
            "target_volume_multiplier": 1.0,
            "target_intensity_multiplier": 1.0
        }
        
        # Create performance analysis
        performance = {
            "performance_level": "on_target",
            "exercise_analyses": []
        }
        
        # Create recovery data
        recovery = {
            "readiness_score": 0.8,
            "fatigue_status": {"fatigue_level": "low"},
            "needs_deload": False
        }
        
        # Create injury risk
        injury_risk = {
            "risk_level": "low",
            "warnings": []
        }
        
        # Calculate parameters
        adjustments = engine.calculate_next_workout_parameters(
            athlete=athlete,
            plan_context=plan_context,
            performance=performance,
            recovery=recovery,
            injury_risk=injury_risk
        )
        
        # Reasoning should include break information
        reasoning = adjustments["reasoning"]
        assert "Extended break" in reasoning
        assert "25 days" in reasoning or "25" in reasoning
        assert "reducing volume" in reasoning.lower() or "reduction" in reasoning.lower()
        assert "detraining" in reasoning.lower()


@pytest.mark.unit
class TestBreakDetectionPriority:
    """Test that break detection respects priority order."""
    
    def test_deload_week_overrides_break_detection(self, db_session):
        """Test that deload week takes priority over break detection."""
        # Create athlete
        athlete = Athlete(
            age=25,
            gender=Gender.MALE,
            training_experience=TrainingExperience.INTERMEDIATE,
            rpe_calibration_factor=1.0
        )
        db_session.add(athlete)
        db_session.flush()
        
        # Create workout plan and day
        plan = WorkoutPlan(
            athlete_id=athlete.id,
            name="Test Plan",
            training_type=TrainingType.HYPERTROPHY,
            periodization_model=PeriodizationModel.LINEAR,
            frequency=3,
            duration_weeks=12,
            start_date=datetime.now(timezone.utc) - timedelta(days=30)
        )
        db_session.add(plan)
        db_session.flush()
        
        workout_day = WorkoutDay(
            workout_plan_id=plan.id,
            name="Test Day",
            day_of_week=0,
            order_in_week=1,
        )
        db_session.add(workout_day)
        db_session.flush()
        
        # Create workout session 10 days ago
        session = WorkoutSession(
            athlete_id=athlete.id,
            workout_day_id=workout_day.id,
            session_date=datetime.now(timezone.utc) - timedelta(days=10)
        )
        db_session.add(session)
        db_session.commit()
        
        engine = ProgressiveOverloadEngine(db_session)
        
        # Create plan context with deload week
        plan_context = {
            "has_plan": True,
            "plan_id": plan.id,
            "training_type": TrainingType.HYPERTROPHY,
            "current_phase": TrainingPhase.ACCUMULATION,
            "week_number": 1,
            "is_deload_week": True,  # Deload week!
            "target_volume_multiplier": 1.0,
            "target_intensity_multiplier": 1.0
        }
        
        # Create performance analysis
        performance = {
            "performance_level": "on_target",
            "exercise_analyses": []
        }
        
        # Create recovery data
        recovery = {
            "readiness_score": 0.8,
            "fatigue_status": {"fatigue_level": "low"},
            "needs_deload": False
        }
        
        # Create injury risk
        injury_risk = {
            "risk_level": "low",
            "warnings": []
        }
        
        # Calculate parameters
        adjustments = engine.calculate_next_workout_parameters(
            athlete=athlete,
            plan_context=plan_context,
            performance=performance,
            recovery=recovery,
            injury_risk=injury_risk
        )
        
        # Should return early with deload parameters (Priority 1)
        # Deload week: volume_multiplier = 0.5, intensity_multiplier = 0.9
        assert adjustments["volume_multiplier"] == 0.5
        assert adjustments["intensity_multiplier"] == 0.9
        assert "deload week" in adjustments["reasoning"].lower()
        # Should NOT mention break (deload takes priority)
        assert "Extended break" not in adjustments["reasoning"]
    
    def test_high_injury_risk_overrides_break_detection(self, db_session):
        """Test that high injury risk takes priority over break detection."""
        # Create athlete
        athlete = Athlete(
            age=25,
            gender=Gender.MALE,
            training_experience=TrainingExperience.INTERMEDIATE,
            rpe_calibration_factor=1.0
        )
        db_session.add(athlete)
        db_session.flush()
        
        # Create workout plan and day
        plan = WorkoutPlan(
            athlete_id=athlete.id,
            name="Test Plan",
            training_type=TrainingType.HYPERTROPHY,
            periodization_model=PeriodizationModel.LINEAR,
            frequency=3,
            duration_weeks=12,
            start_date=datetime.now(timezone.utc) - timedelta(days=30)
        )
        db_session.add(plan)
        db_session.flush()
        
        workout_day = WorkoutDay(
            workout_plan_id=plan.id,
            name="Test Day",
            day_of_week=0,
            order_in_week=1,
        )
        db_session.add(workout_day)
        db_session.flush()
        
        # Create workout session 10 days ago
        session = WorkoutSession(
            athlete_id=athlete.id,
            workout_day_id=workout_day.id,
            session_date=datetime.now(timezone.utc) - timedelta(days=10)
        )
        db_session.add(session)
        db_session.commit()
        
        engine = ProgressiveOverloadEngine(db_session)
        
        # Create plan context
        plan_context = {
            "has_plan": True,
            "plan_id": plan.id,
            "training_type": TrainingType.HYPERTROPHY,
            "current_phase": TrainingPhase.ACCUMULATION,
            "week_number": 1,
            "is_deload_week": False,
            "target_volume_multiplier": 1.0,
            "target_intensity_multiplier": 1.0
        }
        
        # Create performance analysis
        performance = {
            "performance_level": "on_target",
            "exercise_analyses": []
        }
        
        # Create recovery data
        recovery = {
            "readiness_score": 0.8,
            "fatigue_status": {"fatigue_level": "low"},
            "needs_deload": False
        }
        
        # Create HIGH injury risk
        injury_risk = {
            "risk_level": "high",  # High injury risk!
            "warnings": ["Test warning"]
        }
        
        # Calculate parameters
        adjustments = engine.calculate_next_workout_parameters(
            athlete=athlete,
            plan_context=plan_context,
            performance=performance,
            recovery=recovery,
            injury_risk=injury_risk
        )
        
        # Should return early with injury risk parameters (Priority 2)
        # High injury risk: volume_multiplier = 0.5, intensity_multiplier = 0.85
        assert adjustments["volume_multiplier"] == 0.5
        assert adjustments["intensity_multiplier"] == 0.85
        assert "injury risk" in adjustments["reasoning"].lower()
        # Should NOT mention break (injury risk takes priority)
        assert "Extended break" not in adjustments["reasoning"]
    
    def test_break_detection_applies_after_moderate_injury_risk(self, db_session):
        """Test that break detection applies after moderate injury risk."""
        # Create athlete
        athlete = Athlete(
            age=25,
            gender=Gender.MALE,
            training_experience=TrainingExperience.INTERMEDIATE,
            rpe_calibration_factor=1.0
        )
        db_session.add(athlete)
        db_session.flush()
        
        # Create workout plan and day
        plan = WorkoutPlan(
            athlete_id=athlete.id,
            name="Test Plan",
            training_type=TrainingType.HYPERTROPHY,
            periodization_model=PeriodizationModel.LINEAR,
            frequency=3,
            duration_weeks=12,
            start_date=datetime.now(timezone.utc) - timedelta(days=30)
        )
        db_session.add(plan)
        db_session.flush()
        
        workout_day = WorkoutDay(
            workout_plan_id=plan.id,
            name="Test Day",
            day_of_week=0,
            order_in_week=1,
        )
        db_session.add(workout_day)
        db_session.flush()
        
        # Create workout session 10 days ago
        session = WorkoutSession(
            athlete_id=athlete.id,
            workout_day_id=workout_day.id,
            session_date=datetime.now(timezone.utc) - timedelta(days=10)
        )
        db_session.add(session)
        db_session.commit()
        
        engine = ProgressiveOverloadEngine(db_session)
        
        # Create plan context
        plan_context = {
            "has_plan": True,
            "plan_id": plan.id,
            "training_type": TrainingType.HYPERTROPHY,
            "current_phase": TrainingPhase.ACCUMULATION,
            "week_number": 1,
            "is_deload_week": False,
            "target_volume_multiplier": 1.0,
            "target_intensity_multiplier": 1.0
        }
        
        # Create performance analysis
        performance = {
            "performance_level": "on_target",
            "exercise_analyses": []
        }
        
        # Create recovery data
        recovery = {
            "readiness_score": 0.8,
            "fatigue_status": {"fatigue_level": "low"},
            "needs_deload": False
        }
        
        # Create MODERATE injury risk (doesn't return early)
        injury_risk = {
            "risk_level": "moderate",  # Moderate injury risk
            "warnings": []
        }
        
        # Calculate parameters
        adjustments = engine.calculate_next_workout_parameters(
            athlete=athlete,
            plan_context=plan_context,
            performance=performance,
            recovery=recovery,
            injury_risk=injury_risk
        )
        
        # Both moderate injury risk AND break detection should apply
        # Moderate injury risk: volume *= 0.8, intensity *= 0.95
        # Break (10 days): volume *= 0.85, intensity *= 0.85
        # Note: Volume has a safety cap at 0.80, so it will be capped even with break detection
        # Intensity should be reduced: 0.95 * 0.85 = 0.8075, but capped at 0.85
        assert adjustments["volume_multiplier"] <= 0.8  # Capped at 0.80 by safety limit
        assert adjustments["intensity_multiplier"] <= 0.85  # Should be reduced and capped at 0.85
        # Should mention break in reasoning (this verifies break detection is applied)
        assert "Extended break" in adjustments["reasoning"]

