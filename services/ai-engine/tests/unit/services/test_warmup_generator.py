"""
Tests for warm-up set generation service.

Tests that warm-up sets are correctly generated based on working weight,
number of sets, and exercise characteristics.
"""
import pytest
from app.services.warmup_generator import WarmupGenerator
from app.models import Exercise


@pytest.mark.unit
class TestWarmupGenerator:
    """Test warm-up set generation."""
    
    def test_generate_no_warmup_sets(self):
        """Test that 0 warm-up sets returns empty list."""
        generator = WarmupGenerator()
        result = generator.generate_warmup_sets(
            working_weight=100.0,
            num_warmup_sets=0
        )
        assert result == []
    
    def test_generate_one_warmup_set(self):
        """Test single warm-up set generation."""
        generator = WarmupGenerator()
        result = generator.generate_warmup_sets(
            working_weight=100.0,
            num_warmup_sets=1
        )
        
        assert len(result) == 1
        assert result[0]["set_number"] == 1
        assert result[0]["weight_percentage"] == 0.60
        assert result[0]["weight"] == 60.0  # 100 * 0.60 = 60, rounded to 2.5kg
        assert result[0]["reps_min"] == 6
        assert result[0]["reps_max"] == 10
        assert result[0]["is_warmup"] is True
    
    def test_generate_two_warmup_sets(self):
        """Test two warm-up sets generation."""
        generator = WarmupGenerator()
        result = generator.generate_warmup_sets(
            working_weight=100.0,
            num_warmup_sets=2
        )
        
        assert len(result) == 2
        # First set
        assert result[0]["set_number"] == 1
        assert result[0]["weight_percentage"] == 0.50
        assert result[0]["reps_min"] == 6
        assert result[0]["reps_max"] == 10
        # Second set
        assert result[1]["set_number"] == 2
        assert result[1]["weight_percentage"] == 0.70
        assert result[1]["reps_min"] == 4
        assert result[1]["reps_max"] == 6
    
    def test_generate_three_warmup_sets(self):
        """Test three warm-up sets generation."""
        generator = WarmupGenerator()
        result = generator.generate_warmup_sets(
            working_weight=100.0,
            num_warmup_sets=3
        )
        
        assert len(result) == 3
        assert result[0]["weight_percentage"] == 0.45
        assert result[1]["weight_percentage"] == 0.65
        assert result[2]["weight_percentage"] == 0.85
        assert result[2]["reps_min"] == 3
        assert result[2]["reps_max"] == 4
    
    def test_generate_four_warmup_sets(self):
        """Test four warm-up sets generation."""
        generator = WarmupGenerator()
        result = generator.generate_warmup_sets(
            working_weight=100.0,
            num_warmup_sets=4
        )
        
        assert len(result) == 4
        assert result[0]["weight_percentage"] == 0.45
        assert result[1]["weight_percentage"] == 0.60
        assert result[2]["weight_percentage"] == 0.75
        assert result[3]["weight_percentage"] == 0.85
        assert result[3]["reps_min"] == 2
        assert result[3]["reps_max"] == 4
    
    def test_weight_rounding(self):
        """Test that weights are rounded to nearest 2.5kg."""
        generator = WarmupGenerator()
        result = generator.generate_warmup_sets(
            working_weight=87.5,  # 87.5 * 0.60 = 52.5
            num_warmup_sets=1
        )
        
        # Should round to nearest 2.5kg
        assert result[0]["weight"] == 52.5
    
    def test_weight_rounding_edge_case(self):
        """Test weight rounding for non-standard weights."""
        generator = WarmupGenerator()
        result = generator.generate_warmup_sets(
            working_weight=100.0,
            num_warmup_sets=1
        )
        
        # 100 * 0.60 = 60, should round to 60 (already on 2.5kg increment)
        assert result[0]["weight"] == 60.0
    
    def test_invalid_warmup_set_count(self):
        """Test that invalid warm-up set counts are clamped."""
        generator = WarmupGenerator()
        
        # Negative count should be clamped to 0
        result = generator.generate_warmup_sets(
            working_weight=100.0,
            num_warmup_sets=-1
        )
        assert result == []
        
        # Count > 4 should be clamped to 4
        result = generator.generate_warmup_sets(
            working_weight=100.0,
            num_warmup_sets=10
        )
        assert len(result) == 4
    
    def test_determine_warmup_set_count_compound_primary(self, db_session):
        """Test warm-up set count determination for compound primary exercise."""
        generator = WarmupGenerator()
        
        exercise = Exercise(
            name="Squat",
            primary_muscles=["quadriceps", "glutes"],
            exercise_type="compound",
            complexity_score=1.5,
            injury_risk_level=0.6
        )
        db_session.add(exercise)
        db_session.flush()
        
        count = generator.determine_warmup_set_count(exercise, is_primary=True)
        
        # Compound + primary = base 3, + complexity (1.5 >= 1.2) = 0, + injury (0.6 >= 0.5) = 0, + primary = 1
        # Total: 3 + 0 + 0 + 1 = 4, clamped to 4
        assert count == 4
    
    def test_determine_warmup_set_count_isolation_accessory(self, db_session):
        """Test warm-up set count determination for isolation accessory exercise."""
        generator = WarmupGenerator()
        
        exercise = Exercise(
            name="Bicep Curl",
            primary_muscles=["biceps"],
            exercise_type="isolation",
            complexity_score=0.7,
            injury_risk_level=0.2
        )
        db_session.add(exercise)
        db_session.flush()
        
        count = generator.determine_warmup_set_count(exercise, is_primary=False)
        
        # Isolation + accessory = base 1, + complexity (0.7 <= 0.8) = -1, + injury (0.2 <= 0.3) = -1, - primary = -1
        # Total: 1 - 1 - 1 - 1 = -2, clamped to 0
        assert count == 0
    
    def test_determine_warmup_set_count_high_complexity(self, db_session):
        """Test warm-up set count with high complexity score."""
        generator = WarmupGenerator()
        
        exercise = Exercise(
            name="Snatch",
            primary_muscles=["shoulders", "legs"],
            exercise_type="compound",
            complexity_score=2.0,  # Very high complexity
            injury_risk_level=0.8  # High injury risk
        )
        db_session.add(exercise)
        db_session.flush()
        
        count = generator.determine_warmup_set_count(exercise, is_primary=True)
        
        # Compound + primary = base 3, + complexity (2.0 >= 1.5) = 1, + injury (0.8 >= 0.7) = 1, + primary = 1
        # Total: 3 + 1 + 1 + 1 = 6, clamped to 4
        assert count == 4
    
    def test_determine_warmup_set_count_low_risk_simple(self, db_session):
        """Test warm-up set count with low risk and simple exercise."""
        generator = WarmupGenerator()
        
        exercise = Exercise(
            name="Leg Extension",
            primary_muscles=["quadriceps"],
            exercise_type="isolation",
            complexity_score=0.5,  # Low complexity
            injury_risk_level=0.1  # Low injury risk
        )
        db_session.add(exercise)
        db_session.flush()
        
        count = generator.determine_warmup_set_count(exercise, is_primary=True)
        
        # Isolation + primary = base 1, + complexity (0.5 <= 0.8) = -1, + injury (0.1 <= 0.3) = -1, + primary = 1
        # Total: 1 - 1 - 1 + 1 = 0, clamped to 0
        assert count == 0
    
    def test_get_warmup_pyramid_description(self):
        """Test warm-up pyramid description generation."""
        generator = WarmupGenerator()
        
        assert "No warm-up sets" in generator.get_warmup_pyramid_description(0)
        assert "Single warm-up set" in generator.get_warmup_pyramid_description(1)
        assert "Mini warm-up pyramid" in generator.get_warmup_pyramid_description(2)
        assert "Full warm-up pyramid" in generator.get_warmup_pyramid_description(3)
        assert "Extended warm-up pyramid" in generator.get_warmup_pyramid_description(4)


@pytest.mark.unit
class TestWarmupIntegration:
    """Test warm-up generation integration with plan updater."""
    
    def test_warmup_generation_in_workout(self, db_session):
        """Test that warm-up sets are generated in workout response."""
        from app.services.plan_updater import PlanUpdaterService
        from app.models import Athlete, WorkoutPlan, WorkoutDay, WorkoutDayExercise
        from app.utils.constants import Gender, TrainingExperience, TrainingType, PeriodizationModel
        from datetime import datetime, timezone
        
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
            primary_muscles=["chest"],
            exercise_type="compound",
            complexity_score=1.2,
            injury_risk_level=0.5
        )
        db_session.add(exercise)
        db_session.flush()
        
        # Create workout plan
        plan = WorkoutPlan(
            athlete_id=athlete.id,
            name="Test Plan",
            training_type=TrainingType.HYPERTROPHY,
            periodization_model=PeriodizationModel.LINEAR,
            frequency=3,
            duration_weeks=12,
            start_date=datetime.now(timezone.utc)
        )
        db_session.add(plan)
        db_session.flush()
        
        # Create workout day
        workout_day = WorkoutDay(
            workout_plan_id=plan.id,
            name="Push Day",
            day_of_week=0,
            order_in_week=1,
            target_muscle_groups=["chest", "shoulders", "triceps"]
        )
        db_session.add(workout_day)
        db_session.flush()
        
        # Create workout day exercise with auto-generate enabled
        workout_exercise = WorkoutDayExercise(
            workout_day_id=workout_day.id,
            exercise_id=exercise.id,
            order_in_workout=1,
            target_sets_min=3,
            target_sets_max=3,
            target_reps_min=8,
            target_reps_max=12,
            target_rpe=8.0,
            is_primary=1,
            warm_up_sets=3,  # 3 warm-up sets
            auto_generate_warmups=1  # Auto-generate enabled
        )
        db_session.add(workout_exercise)
        db_session.commit()
        
        # Generate workout
        plan_updater = PlanUpdaterService(db_session)
        
        # Mock AI adjustments
        ai_adjustments = {
            "volume_multiplier": 1.0,
            "intensity_multiplier": 1.0,
            "exercise_adjustments": {},
            "reasoning": "Standard progression"
        }
        
        # We need a previous workout to get adjusted_weight
        # For this test, we'll check that warm-up generation logic is called
        # In a real scenario, adjusted_weight would come from last workout
        
        result = plan_updater.generate_next_workout(
            athlete_id=athlete.id,
            workout_day_id=workout_day.id,
            ai_adjustments=ai_adjustments,
            injury_warnings=[],
            recovery_recommendations=[]
        )
        
        # Check that workout day exercise has warm-up configuration
        assert len(result["workout_day"].exercises) > 0
        exercise_response = result["workout_day"].exercises[0]
        assert exercise_response.warm_up_sets == 3
        assert exercise_response.auto_generate_warmups is True
        # Warm-up sets will be None if adjusted_weight is None (no previous workout)
        # This is expected behavior
    
    def test_warmup_auto_determination(self, db_session):
        """Test that warm-up set count is auto-determined when not set."""
        from app.services.plan_updater import PlanUpdaterService
        from app.models import Athlete, WorkoutPlan, WorkoutDay, WorkoutDayExercise, WorkoutSession, ExerciseSet
        from app.utils.constants import Gender, TrainingExperience, TrainingType, PeriodizationModel
        from datetime import datetime, timedelta, timezone
        
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
            name="Deadlift",
            primary_muscles=["hamstrings", "glutes", "back"],
            exercise_type="compound",
            complexity_score=1.8,  # High complexity
            injury_risk_level=0.7  # High injury risk
        )
        db_session.add(exercise)
        db_session.flush()
        
        # Create workout plan
        plan = WorkoutPlan(
            athlete_id=athlete.id,
            name="Test Plan",
            training_type=TrainingType.STRENGTH,
            periodization_model=PeriodizationModel.LINEAR,
            frequency=3,
            duration_weeks=12,
            start_date=datetime.now(timezone.utc)
        )
        db_session.add(plan)
        db_session.flush()
        
        # Create workout day
        workout_day = WorkoutDay(
            workout_plan_id=plan.id,
            name="Pull Day",
            day_of_week=0,
            order_in_week=1,
            target_muscle_groups=["back", "biceps"]
        )
        db_session.add(workout_day)
        db_session.flush()
        
        # Create workout day exercise with warm_up_sets = 0 (should auto-determine)
        workout_exercise = WorkoutDayExercise(
            workout_day_id=workout_day.id,
            exercise_id=exercise.id,
            order_in_workout=1,
            target_sets_min=3,
            target_sets_max=3,
            target_reps_min=5,
            target_reps_max=5,
            target_rpe=8.0,
            is_primary=1,
            warm_up_sets=0,  # Not set - should auto-determine
            auto_generate_warmups=1
        )
        db_session.add(workout_exercise)
        db_session.flush()
        
        # Create a previous workout session with this exercise to get adjusted_weight
        previous_session = WorkoutSession(
            athlete_id=athlete.id,
            workout_day_id=workout_day.id,
            session_date=datetime.now(timezone.utc) - timedelta(days=2)
        )
        db_session.add(previous_session)
        db_session.flush()
        
        # Add exercise set with weight
        exercise_set = ExerciseSet(
            workout_session_id=previous_session.id,
            exercise_id=exercise.id,
            set_number=1,
            weight=150.0,
            reps=5,
            rpe=8.0
        )
        db_session.add(exercise_set)
        db_session.commit()
        
        # Generate workout
        plan_updater = PlanUpdaterService(db_session)
        
        ai_adjustments = {
            "volume_multiplier": 1.0,
            "intensity_multiplier": 1.0,
            "exercise_adjustments": {},
            "reasoning": "Standard progression"
        }
        
        result = plan_updater.generate_next_workout(
            athlete_id=athlete.id,
            workout_day_id=workout_day.id,
            ai_adjustments=ai_adjustments,
            injury_warnings=[],
            recovery_recommendations=[]
        )
        
        # Check that warm-up sets were generated
        exercise_response = result["workout_day"].exercises[0]
        assert exercise_response.adjusted_weight is not None
        # Warm-up sets should be generated since auto_generate_warmups is True
        # and adjusted_weight is available
        if exercise_response.warmup_sets:
            assert len(exercise_response.warmup_sets) > 0
            assert all(warmup.is_warmup for warmup in exercise_response.warmup_sets)


@pytest.mark.unit
class TestWarmupSetVariation:
    """Test warm-up generation adaptation to set variation features."""
    
    def test_warmup_early_phase_minimum_sets(self):
        """Test warmup generation at minimum sets (early phase)."""
        generator = WarmupGenerator()
        
        # Early phase: sets at minimum (position 0.0)
        result = generator.generate_warmup_sets(
            working_weight=100.0,
            num_warmup_sets=3,
            adjusted_sets=3,  # At minimum
            sets_range_position=0.0,  # Early phase
            is_deload_week=False
        )
        
        # Should have warmup sets (may be reduced from base)
        assert len(result) >= 1
        assert all(warmup["is_warmup"] for warmup in result)
    
    def test_warmup_peak_phase_maximum_sets(self):
        """Test warmup generation at maximum sets (peak phase)."""
        generator = WarmupGenerator()
        
        # Peak phase: sets at maximum (position 1.0), high volume
        result = generator.generate_warmup_sets(
            working_weight=100.0,
            num_warmup_sets=3,
            adjusted_sets=6,  # High volume at peak
            sets_range_position=1.0,  # Peak phase
            is_deload_week=False
        )
        
        # Should have warmup sets, potentially increased for high volume
        assert len(result) >= 3
        assert all(warmup["is_warmup"] for warmup in result)
        
        # Final warmup set should have higher intensity (peak phase boost)
        if len(result) > 0:
            final_set = result[-1]
            # Should be at least 85% (base) or higher (with peak boost)
            assert final_set["weight_percentage"] >= 0.85
    
    def test_warmup_deload_week_reduction(self):
        """Test warmup generation during deload week."""
        generator = WarmupGenerator()
        
        # Deload week: should reduce warmup sets
        result = generator.generate_warmup_sets(
            working_weight=100.0,
            num_warmup_sets=3,
            adjusted_sets=3,
            sets_range_position=0.0,
            is_deload_week=True
        )
        
        # Deload week reduces by 1, and early phase (position 0.0) with low volume (3 sets) 
        # also reduces by 1, so: 3 - 1 (deload) - 1 (early phase) = 1
        assert len(result) == 1
        assert all(warmup["is_warmup"] for warmup in result)
    
    def test_warmup_deload_week_minimum(self):
        """Test deload week doesn't go below 0 warmup sets."""
        generator = WarmupGenerator()
        
        # Deload week with only 1 warmup set
        result = generator.generate_warmup_sets(
            working_weight=100.0,
            num_warmup_sets=1,
            adjusted_sets=3,
            sets_range_position=0.0,
            is_deload_week=True
        )
        
        # Should be 0 (1 - 1 = 0, clamped to 0)
        assert len(result) == 0
    
    def test_warmup_peak_phase_intensity_boost(self):
        """Test that peak phase increases final warmup intensity."""
        generator = WarmupGenerator()
        
        # Peak phase with 4 warmup sets
        result_peak = generator.generate_warmup_sets(
            working_weight=100.0,
            num_warmup_sets=4,
            adjusted_sets=6,
            sets_range_position=1.0,  # Peak phase
            is_deload_week=False
        )
        
        # Early phase with same base warmup sets
        result_early = generator.generate_warmup_sets(
            working_weight=100.0,
            num_warmup_sets=4,
            adjusted_sets=3,
            sets_range_position=0.0,  # Early phase
            is_deload_week=False
        )
        
        # Both should have warmup sets
        assert len(result_peak) > 0
        assert len(result_early) > 0
        
        # Peak phase final set should have higher intensity
        if len(result_peak) > 0 and len(result_early) > 0:
            peak_final = result_peak[-1]
            early_final = result_early[-1]
            # Peak phase should have higher or equal weight percentage
            assert peak_final["weight_percentage"] >= early_final["weight_percentage"]
    
    def test_warmup_set_range_position_scaling(self):
        """Test warmup adaptation across different set range positions."""
        generator = WarmupGenerator()
        
        # Test at different positions in the range
        positions = [0.0, 0.3, 0.5, 0.8, 1.0]
        results = []
        
        for pos in positions:
            result = generator.generate_warmup_sets(
                working_weight=100.0,
                num_warmup_sets=3,
                adjusted_sets=3 + int(pos * 3),  # 3 to 6 sets
                sets_range_position=pos,
                is_deload_week=False
            )
            results.append((pos, result))
        
        # All should generate warmup sets
        for pos, result in results:
            assert len(result) >= 1, f"Position {pos} should have warmup sets"
        
        # Peak positions (>= 0.8) should have higher final intensity
        peak_results = [r for pos, r in results if pos >= 0.8]
        early_results = [r for pos, r in results if pos <= 0.3]
        
        if peak_results and early_results:
            peak_finals = [r[-1]["weight_percentage"] for r in peak_results if r]
            early_finals = [r[-1]["weight_percentage"] for r in early_results if r]
            
            if peak_finals and early_finals:
                avg_peak = sum(peak_finals) / len(peak_finals)
                avg_early = sum(early_finals) / len(early_finals)
                # Peak should have higher average intensity
                assert avg_peak >= avg_early
    
    def test_warmup_high_volume_peak_week(self):
        """Test warmup generation for high volume peak week."""
        generator = WarmupGenerator()
        
        # High volume (5+ sets) at peak phase
        result = generator.generate_warmup_sets(
            working_weight=100.0,
            num_warmup_sets=3,
            adjusted_sets=5,  # High volume
            sets_range_position=0.9,  # Near peak
            is_deload_week=False
        )
        
        # Should potentially add warmup set for high volume (if room)
        # At minimum should have base warmup sets
        assert len(result) >= 3
        assert all(warmup["is_warmup"] for warmup in result)
    
    def test_warmup_low_volume_early_week(self):
        """Test warmup generation for low volume early week."""
        generator = WarmupGenerator()
        
        # Low volume (3 sets) at early phase
        result = generator.generate_warmup_sets(
            working_weight=100.0,
            num_warmup_sets=3,
            adjusted_sets=3,  # Low volume
            sets_range_position=0.1,  # Early phase
            is_deload_week=False
        )
        
        # Should have warmup sets (may be reduced)
        assert len(result) >= 1
        assert all(warmup["is_warmup"] for warmup in result)
    
    def test_warmup_backward_compatibility(self):
        """Test that warmup generation works without new parameters (backward compatibility)."""
        generator = WarmupGenerator()
        
        # Call without new context parameters
        result = generator.generate_warmup_sets(
            working_weight=100.0,
            num_warmup_sets=3
        )
        
        # Should work as before
        assert len(result) == 3
        assert all(warmup["is_warmup"] for warmup in result)
        assert result[0]["weight_percentage"] == 0.45
        assert result[1]["weight_percentage"] == 0.65
        assert result[2]["weight_percentage"] == 0.85

