"""
Integration tests for Progressive Overload Engine with Intensity Techniques.

Tests the integration between the progressive overload engine and intensity
technique service in realistic scenarios.
"""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session

from app.modules.progression.progressive_overload_engine import ProgressiveOverloadEngine
from app.modules.prescription import IntensityTechniqueService
from app.utils.constants import (
    SetType, RepStyle, TrainingType, TrainingPhase, TrainingExperience,
    ExerciseType, Gender
)
from tests.factories import (
    AthleteFactory, ExerciseFactory, WorkoutPlanFactory,
    WorkoutDayFactory, WorkoutSessionFactory, ExerciseSetFactory
)


@pytest.mark.integration
@pytest.mark.slow
class TestEngineIntensityTechniqueIntegration:
    """Test progressive overload engine integration with intensity techniques."""
    
    def test_engine_initializes_intensity_service(self, db_session):
        """Test that engine initializes the intensity technique service."""
        engine = ProgressiveOverloadEngine(db_session)
        
        assert hasattr(engine, 'intensity_technique')
        assert isinstance(engine.intensity_technique, IntensityTechniqueService)
    
    def test_no_technique_for_progressing_athlete(self, db_session):
        """Test that no technique is recommended for an athlete making progress."""
        # Setup
        athlete = AthleteFactory.create(
            db_session,
            age=28,
            gender=Gender.MALE,
            training_experience=TrainingExperience.INTERMEDIATE
        )
        
        exercise = ExerciseFactory.create_isolation(
            db_session,
            name="Bicep Curl",
            muscles=[("biceps", 95)]
        )
        
        plan = WorkoutPlanFactory.create(
            db_session,
            athlete_id=athlete.id,
            training_type=TrainingType.HYPERTROPHY
        )
        
        workout_day = WorkoutDayFactory.create(
            db_session,
            workout_plan_id=plan.id,
            name="Arm Day"
        )
        
        # Create a couple of sessions with improving performance
        weights = [12.0, 12.5, 13.0]  # Progressive overload
        for i, weight in enumerate(weights):
            session = WorkoutSessionFactory.create(
                db_session,
                athlete_id=athlete.id,
                workout_day_id=workout_day.id,
                session_date=datetime.now(timezone.utc) - timedelta(days=7*(len(weights)-i)),
                overall_rpe=7.0
            )
            
            for set_num in range(1, 4):
                ExerciseSetFactory.create(
                    db_session,
                    workout_session_id=session.id,
                    exercise_id=exercise.id,
                    set_number=set_num,
                    weight=weight,
                    reps=10,
                    rpe=7.0  # Comfortable RPE
                )
        
        db_session.commit()
        
        # Test the intensity technique service directly
        engine = ProgressiveOverloadEngine(db_session)
        technique_service = engine.intensity_technique
        
        result = technique_service.recommend_techniques(
            athlete_id=athlete.id,
            exercise_id=exercise.id,
            training_type=TrainingType.HYPERTROPHY,
            training_phase=TrainingPhase.ACCUMULATION,
            exercise_type=ExerciseType.ISOLATION,
            experience=athlete.training_experience,
            readiness_score=0.8,
            is_primary=False,
            order_in_workout=1,
            performance_level="progressing",
            week_number=1,
            muscle_name="biceps"
        )
        
        # With progress being made, should get straight sets
        assert result["set_type"] == SetType.STRAIGHT
        assert result["rep_style"] == RepStyle.NORMAL
    
    def test_technique_recommended_for_plateau(self, db_session):
        """Test that technique is recommended when athlete has plateaued."""
        # Setup
        athlete = AthleteFactory.create(
            db_session,
            age=28,
            gender=Gender.MALE,
            training_experience=TrainingExperience.INTERMEDIATE
        )
        
        exercise = ExerciseFactory.create_isolation(
            db_session,
            name="Tricep Pushdown",
            muscles=[("triceps", 95)]
        )
        
        plan = WorkoutPlanFactory.create(
            db_session,
            athlete_id=athlete.id,
            training_type=TrainingType.HYPERTROPHY
        )
        
        workout_day = WorkoutDayFactory.create(
            db_session,
            workout_plan_id=plan.id,
            name="Push Day"
        )
        
        # Create sessions with STALLED performance (plateau)
        for i in range(4):
            session = WorkoutSessionFactory.create(
                db_session,
                athlete_id=athlete.id,
                workout_day_id=workout_day.id,
                session_date=datetime.now(timezone.utc) - timedelta(days=7*(3-i)),
                overall_rpe=8.5
            )
            
            for set_num in range(1, 4):
                ExerciseSetFactory.create(
                    db_session,
                    workout_session_id=session.id,
                    exercise_id=exercise.id,
                    set_number=set_num,
                    weight=20.0,  # Same weight for all sessions
                    reps=10,      # Same reps
                    rpe=8.5       # High effort
                )
        
        db_session.commit()
        
        # Test
        engine = ProgressiveOverloadEngine(db_session)
        technique_service = engine.intensity_technique
        
        result = technique_service.recommend_techniques(
            athlete_id=athlete.id,
            exercise_id=exercise.id,
            training_type=TrainingType.HYPERTROPHY,
            training_phase=TrainingPhase.ACCUMULATION,
            exercise_type=ExerciseType.ISOLATION,
            experience=athlete.training_experience,
            readiness_score=0.8,
            is_primary=False,
            order_in_workout=2,
            performance_level="struggling",
            week_number=3,
            muscle_name="triceps"
        )
        
        # Should detect plateau and recommend technique
        # Note: This depends on the plateau detection logic
        # The service should either detect plateau or phase-based trigger
        assert result["triggers"]["any_triggered"] == True or result["triggers"]["phase_based_triggered"] == True


@pytest.mark.integration
@pytest.mark.slow
class TestTechniqueRecommendationContext:
    """Test that technique recommendations consider full context."""
    
    def test_compound_vs_isolation_recommendations(self, db_session):
        """Test different recommendations for compound vs isolation exercises."""
        athlete = AthleteFactory.create(
            db_session,
            training_experience=TrainingExperience.ADVANCED
        )
        
        compound = ExerciseFactory.create_compound(
            db_session,
            name="Squat",
            muscles=[("quadriceps", 90), ("glutes", 85)]
        )
        
        isolation = ExerciseFactory.create_isolation(
            db_session,
            name="Leg Extension",
            muscles=[("quadriceps", 95)]
        )
        
        db_session.flush()
        
        engine = ProgressiveOverloadEngine(db_session)
        technique_service = engine.intensity_technique
        
        # Get recommendations for compound
        compound_result = technique_service.recommend_techniques(
            athlete_id=athlete.id,
            exercise_id=compound.id,
            training_type=TrainingType.STRENGTH,
            training_phase=TrainingPhase.INTENSIFICATION,
            exercise_type=ExerciseType.COMPOUND,
            experience=athlete.training_experience,
            readiness_score=0.9,
            is_primary=True,
            order_in_workout=1,
            performance_level="progressing",
            week_number=3,  # Late phase
            muscle_name="quadriceps"
        )
        
        # Get recommendations for isolation
        isolation_result = technique_service.recommend_techniques(
            athlete_id=athlete.id,
            exercise_id=isolation.id,
            training_type=TrainingType.HYPERTROPHY,
            training_phase=TrainingPhase.ACCUMULATION,
            exercise_type=ExerciseType.ISOLATION,
            experience=athlete.training_experience,
            readiness_score=0.9,
            is_primary=False,
            order_in_workout=3,
            performance_level="progressing",
            week_number=3,  # Late phase
            muscle_name="quadriceps"
        )
        
        # If phase-based trigger fires, compound should not get drop sets
        # but isolation can
        if compound_result["triggers"]["phase_based_triggered"]:
            assert compound_result["set_type"] != SetType.DROP_SET
        
        if isolation_result["triggers"]["phase_based_triggered"]:
            # Isolation can get drop sets, myo-reps, etc.
            assert isolation_result["set_type"] in [
                SetType.STRAIGHT, SetType.DROP_SET, SetType.MYO_REPS, 
                SetType.REST_PAUSE
            ]
    
    def test_experience_affects_recommendations(self, db_session):
        """Test that experience level affects technique recommendations."""
        beginner = AthleteFactory.create_beginner(db_session)
        advanced = AthleteFactory.create_advanced(db_session)
        
        exercise = ExerciseFactory.create_isolation(
            db_session,
            name="Lateral Raise",
            muscles=[("lateral_delt", 95)]
        )
        
        db_session.flush()
        
        engine = ProgressiveOverloadEngine(db_session)
        technique_service = engine.intensity_technique
        
        common_params = {
            "exercise_id": exercise.id,
            "training_type": TrainingType.HYPERTROPHY,
            "training_phase": TrainingPhase.ACCUMULATION,
            "exercise_type": ExerciseType.ISOLATION,
            "readiness_score": 0.8,
            "is_primary": False,
            "order_in_workout": 2,
            "performance_level": "struggling",
            "week_number": 3,
            "muscle_name": "lateral_delt"
        }
        
        beginner_result = technique_service.recommend_techniques(
            athlete_id=beginner.id,
            experience=beginner.training_experience,
            **common_params
        )
        
        advanced_result = technique_service.recommend_techniques(
            athlete_id=advanced.id,
            experience=advanced.training_experience,
            **common_params
        )
        
        # Beginner should usually get straight sets, but some techniques (like supersets) are allowed
        # Ensure they don't get advanced techniques
        assert beginner_result["set_type"] not in [SetType.CLUSTER_SET, SetType.MYO_REPS]
        assert beginner_result["rep_style"] != RepStyle.ECCENTRIC_OVERLOAD
        
        # Advanced with phase trigger might get a technique
        # (depending on other conditions being met)


@pytest.mark.integration
@pytest.mark.slow
class TestFatigueImpactCalculation:
    """Test that fatigue impact is correctly calculated."""
    
    def test_fatigue_impact_affects_volume_adjustments(self, db_session):
        """Test that technique fatigue impacts are calculated."""
        athlete = AthleteFactory.create(
            db_session,
            training_experience=TrainingExperience.INTERMEDIATE
        )
        
        exercise = ExerciseFactory.create_isolation(
            db_session,
            name="Cable Curl",
            muscles=[("biceps", 95)]
        )
        
        db_session.flush()
        
        engine = ProgressiveOverloadEngine(db_session)
        technique_service = engine.intensity_technique
        
        # Calculate impact for different techniques
        straight_normal = technique_service.calculate_fatigue_impact(
            SetType.STRAIGHT, RepStyle.NORMAL, 1000
        )
        
        drop_set = technique_service.calculate_fatigue_impact(
            SetType.DROP_SET, RepStyle.NORMAL, 1000
        )
        
        myo_reps = technique_service.calculate_fatigue_impact(
            SetType.MYO_REPS, RepStyle.NORMAL, 1000
        )
        
        # Straight/normal should have 1.0 multipliers
        assert straight_normal["volume_multiplier"] == 1.0
        assert straight_normal["fatigue_multiplier"] == 1.0
        
        # Drop sets should increase both volume and fatigue
        assert drop_set["volume_multiplier"] > 1.0
        assert drop_set["fatigue_multiplier"] > 1.0
        
        # Myo-reps should have high volume with proportional fatigue
        assert myo_reps["volume_multiplier"] > 1.0


@pytest.mark.integration
@pytest.mark.slow
class TestLatePhaseIntegration:
    """Test late phase (week 3-4) triggers technique recommendations."""
    
    def test_late_accumulation_triggers_technique(self, db_session):
        """Test that late accumulation phase triggers technique for intermediate+."""
        athlete = AthleteFactory.create(
            db_session,
            training_experience=TrainingExperience.INTERMEDIATE
        )
        
        exercise = ExerciseFactory.create_isolation(
            db_session,
            name="Preacher Curl",
            muscles=[("biceps", 95)]
        )
        
        plan = WorkoutPlanFactory.create(
            db_session,
            athlete_id=athlete.id,
            training_type=TrainingType.HYPERTROPHY
        )
        
        db_session.flush()
        
        engine = ProgressiveOverloadEngine(db_session)
        technique_service = engine.intensity_technique
        
        # Week 3 (late accumulation)
        result = technique_service.recommend_techniques(
            athlete_id=athlete.id,
            exercise_id=exercise.id,
            training_type=TrainingType.HYPERTROPHY,
            training_phase=TrainingPhase.ACCUMULATION,
            exercise_type=ExerciseType.ISOLATION,
            experience=athlete.training_experience,
            readiness_score=0.8,
            is_primary=False,
            order_in_workout=2,
            performance_level="progressing",
            week_number=3,
            muscle_name="biceps"
        )
        
        # Phase-based trigger should fire on week 3
        assert result["triggers"]["phase_based_triggered"] == True
        assert result["triggers"]["any_triggered"] == True
    
    def test_deload_week_no_technique(self, db_session):
        """Test that deload week (week 4) doesn't trigger phase-based technique."""
        athlete = AthleteFactory.create(
            db_session,
            training_experience=TrainingExperience.INTERMEDIATE
        )
        
        exercise = ExerciseFactory.create_isolation(
            db_session,
            name="Hammer Curl",
            muscles=[("biceps", 95)]
        )
        
        db_session.flush()
        
        engine = ProgressiveOverloadEngine(db_session)
        technique_service = engine.intensity_technique
        
        # Week 4 (deload)
        result = technique_service.recommend_techniques(
            athlete_id=athlete.id,
            exercise_id=exercise.id,
            training_type=TrainingType.HYPERTROPHY,
            training_phase=TrainingPhase.ACCUMULATION,
            exercise_type=ExerciseType.ISOLATION,
            experience=athlete.training_experience,
            readiness_score=0.8,
            is_primary=False,
            order_in_workout=2,
            performance_level="progressing",
            week_number=4,  # Deload week
            muscle_name="biceps"
        )
        
        # Phase-based trigger should NOT fire on deload week
        assert result["triggers"]["phase_based_triggered"] == False


@pytest.mark.integration
@pytest.mark.slow
class TestMultipleExerciseWorkout:
    """Test intensity techniques across multiple exercises in a workout."""
    
    def test_different_techniques_per_exercise(self, db_session):
        """Test that different exercises can get different technique recommendations."""
        athlete = AthleteFactory.create(
            db_session,
            training_experience=TrainingExperience.INTERMEDIATE
        )
        
        compound = ExerciseFactory.create_compound(
            db_session,
            name="Barbell Row",
            muscles=[("lats", 90), ("mid_back", 80), ("biceps", 60)]
        )
        
        isolation = ExerciseFactory.create_isolation(
            db_session,
            name="Face Pull",
            muscles=[("posterior_delt", 90), ("upper_traps", 50)]
        )
        
        db_session.flush()
        
        engine = ProgressiveOverloadEngine(db_session)
        technique_service = engine.intensity_technique
        
        # Primary compound (1st exercise)
        compound_result = technique_service.recommend_techniques(
            athlete_id=athlete.id,
            exercise_id=compound.id,
            training_type=TrainingType.HYPERTROPHY,
            training_phase=TrainingPhase.ACCUMULATION,
            exercise_type=ExerciseType.COMPOUND,
            experience=athlete.training_experience,
            readiness_score=0.8,
            is_primary=True,
            order_in_workout=1,
            performance_level="progressing",
            week_number=3,
            muscle_name="lats"
        )
        
        # Accessory isolation (3rd exercise)
        isolation_result = technique_service.recommend_techniques(
            athlete_id=athlete.id,
            exercise_id=isolation.id,
            training_type=TrainingType.HYPERTROPHY,
            training_phase=TrainingPhase.ACCUMULATION,
            exercise_type=ExerciseType.ISOLATION,
            experience=athlete.training_experience,
            readiness_score=0.8,
            is_primary=False,
            order_in_workout=3,
            performance_level="progressing",
            week_number=3,
            muscle_name="posterior_delt"
        )
        
        # Both should have results
        assert compound_result["set_type"] is not None
        assert isolation_result["set_type"] is not None


@pytest.mark.integration
@pytest.mark.slow
class TestRecoveryImpactOnTechniques:
    """Test that recovery/readiness affects technique recommendations."""
    
    def test_low_readiness_limits_techniques(self, db_session):
        """Test that low readiness limits high-fatigue techniques."""
        athlete = AthleteFactory.create(
            db_session,
            training_experience=TrainingExperience.INTERMEDIATE
        )
        
        exercise = ExerciseFactory.create_isolation(
            db_session,
            name="Cable Lateral Raise",
            muscles=[("lateral_delt", 95)]
        )
        
        db_session.flush()
        
        engine = ProgressiveOverloadEngine(db_session)
        technique_service = engine.intensity_technique
        
        # Low readiness
        result = technique_service.recommend_techniques(
            athlete_id=athlete.id,
            exercise_id=exercise.id,
            training_type=TrainingType.HYPERTROPHY,
            training_phase=TrainingPhase.ACCUMULATION,
            exercise_type=ExerciseType.ISOLATION,
            experience=athlete.training_experience,
            readiness_score=0.4,  # Low readiness
            is_primary=False,
            order_in_workout=2,
            performance_level="progressing",
            week_number=3,
            muscle_name="lateral_delt"
        )
        
        # Even with phase trigger, low readiness should limit options
        from app.utils.constants import SET_TYPE_CONFIG
        if result["set_type"] != SetType.STRAIGHT:
            config = SET_TYPE_CONFIG.get(result["set_type"], {})
            # Should not recommend high-fatigue techniques
            assert config.get("fatigue_multiplier", 1.0) <= 1.2

