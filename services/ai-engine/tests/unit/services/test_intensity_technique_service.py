"""
Unit tests for Intensity Technique Service.

Tests the AI-powered recommendation system for set types and rep styles.
"""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, MagicMock, patch

from app.services.intensity_technique_service import IntensityTechniqueService
from app.utils.constants import (
    SetType, RepStyle, TrainingType, TrainingPhase, TrainingExperience,
    ExerciseType, MuscleGroup, SET_TYPE_CONFIG, REP_STYLE_CONFIG,
    VALID_TECHNIQUE_COMBINATIONS, MRV_SETS_PER_WEEK
)


class TestIntensityTechniqueServiceDefaults:
    """Test default behavior when no triggers are detected."""
    
    def setup_method(self):
        """Setup for each test."""
        self.db = Mock()
        self.service = IntensityTechniqueService(self.db)
    
    def test_default_straight_sets_when_no_triggers(self):
        """Test that straight sets with normal reps are returned when no triggers detected."""
        # Mock no plateau, no struggling, no volume ceiling
        self.service._check_plateau = Mock(return_value={"is_plateau": False})
        self.service._check_struggling = Mock(return_value={"is_struggling": False})
        self.service._check_volume_ceiling = Mock(return_value={"at_ceiling": False})
        
        result = self.service.recommend_techniques(
            athlete_id=1,
            exercise_id=1,
            training_type=TrainingType.HYPERTROPHY,
            training_phase=TrainingPhase.ACCUMULATION,
            exercise_type=ExerciseType.COMPOUND,
            experience=TrainingExperience.INTERMEDIATE,
            readiness_score=0.8,
            is_primary=True,
            order_in_workout=1,
            performance_level="progressing",
            week_number=1,
            muscle_group=MuscleGroup.CHEST
        )
        
        assert result["set_type"] == SetType.STRAIGHT
        assert result["rep_style"] == RepStyle.NORMAL
        assert "no intensity technique needed" in result["reasoning"].lower()
        assert result["triggers"]["any_triggered"] == False
    
    def test_default_for_beginner_athlete(self):
        """Test that beginners get straight sets even in late accumulation."""
        self.service._check_plateau = Mock(return_value={"is_plateau": False})
        self.service._check_struggling = Mock(return_value={"is_struggling": False})
        self.service._check_volume_ceiling = Mock(return_value={"at_ceiling": False})
        
        result = self.service.recommend_techniques(
            athlete_id=1,
            exercise_id=1,
            training_type=TrainingType.HYPERTROPHY,
            training_phase=TrainingPhase.ACCUMULATION,
            exercise_type=ExerciseType.ISOLATION,
            experience=TrainingExperience.BEGINNER,
            readiness_score=0.9,
            is_primary=False,
            order_in_workout=3,
            performance_level="progressing",
            week_number=1,
            muscle_group=MuscleGroup.BICEPS
        )
        
        # Beginners should get straight sets (most techniques require intermediate+)
        assert result["set_type"] == SetType.STRAIGHT
    
    def test_no_triggers_early_accumulation_phase(self):
        """Test that early accumulation phase (week 1-2) doesn't trigger phase-based technique."""
        self.service._check_plateau = Mock(return_value={"is_plateau": False})
        self.service._check_struggling = Mock(return_value={"is_struggling": False})
        self.service._check_volume_ceiling = Mock(return_value={"at_ceiling": False})
        
        result = self.service.recommend_techniques(
            athlete_id=1,
            exercise_id=1,
            training_type=TrainingType.HYPERTROPHY,
            training_phase=TrainingPhase.ACCUMULATION,
            exercise_type=ExerciseType.ISOLATION,
            experience=TrainingExperience.INTERMEDIATE,
            readiness_score=0.8,
            is_primary=False,
            order_in_workout=2,
            performance_level="progressing",
            week_number=2,  # Week 2 - early accumulation
            muscle_group=MuscleGroup.BICEPS
        )
        
        # No phase-based trigger for early weeks
        assert result["triggers"]["phase_based_triggered"] == False


class TestPlateauTrigger:
    """Test plateau detection trigger."""
    
    def setup_method(self):
        """Setup for each test."""
        self.db = Mock()
        self.service = IntensityTechniqueService(self.db)
    
    def test_plateau_detection_with_stalled_progress(self):
        """Test that plateau is detected when performance is stalled."""
        from app.models import ExerciseSet, WorkoutSession
        
        # Create mock sets with stalled progress (same volume across sessions)
        mock_sets = []
        for i in range(12):  # 4 sessions x 3 sets
            mock_set = Mock()
            mock_set.workout_session_id = i // 3 + 1
            mock_set.weight = 100.0
            mock_set.reps = 8
            mock_sets.append(mock_set)
        
        # Configure the mock query chain
        mock_query = Mock()
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_sets
        self.db.query.return_value = mock_query
        
        result = self.service._check_plateau(athlete_id=1, exercise_id=1)
        
        assert result["is_plateau"] == True
        assert result["sessions_analyzed"] >= 3
        assert result["improvement_percent"] < 2.0
    
    def test_no_plateau_with_insufficient_data(self):
        """Test that plateau is not detected with insufficient session data."""
        # Only return 3 sets (less than 2 sessions worth)
        mock_sets = []
        for i in range(3):
            mock_set = Mock()
            mock_set.workout_session_id = 1
            mock_set.weight = 100.0
            mock_set.reps = 8
            mock_sets.append(mock_set)
        
        mock_query = Mock()
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_sets
        self.db.query.return_value = mock_query
        
        result = self.service._check_plateau(athlete_id=1, exercise_id=1)
        
        assert result["is_plateau"] == False
    
    def test_no_plateau_with_progress(self):
        """Test that plateau is not detected when there's improvement."""
        # Create mock sets with improving volume
        mock_sets = []
        # Older to newer sessions: 100, 100, 102.5, 102.5
        # We need to present them in reverse order (newest first) for the service
        session_weights = [102.5, 102.5, 100, 100]
        for session_id, weight in enumerate(session_weights, 1):
            for _ in range(3):
                mock_set = Mock()
                # Give distinct session IDs in descending order effectively
                mock_set.workout_session_id = 10 - session_id 
                mock_set.weight = weight
                mock_set.reps = 8
                mock_sets.append(mock_set)
        
        mock_query = Mock()
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_sets
        self.db.query.return_value = mock_query
        
        result = self.service._check_plateau(athlete_id=1, exercise_id=1)
        
        # 2.5% improvement should not be a plateau
        assert result["improvement_percent"] >= 2.0 or result["sessions_analyzed"] < 3


class TestStrugglingTrigger:
    """Test struggling detection trigger."""
    
    def setup_method(self):
        """Setup for each test."""
        self.db = Mock()
        self.service = IntensityTechniqueService(self.db)
    
    def test_struggling_detected_high_rpe(self):
        """Test that struggling is detected with consistently high RPE."""
        mock_sets = []
        for i in range(6):
            mock_set = Mock()
            mock_set.rpe = 9.0  # High RPE
            mock_sets.append(mock_set)
        
        mock_query = Mock()
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_sets
        self.db.query.return_value = mock_query
        
        result = self.service._check_struggling(athlete_id=1, exercise_id=1)
        
        assert result["is_struggling"] == True
        assert result["avg_rpe"] >= 8.0
    
    def test_not_struggling_moderate_rpe(self):
        """Test that struggling is not detected with moderate RPE."""
        mock_sets = []
        for i in range(6):
            mock_set = Mock()
            mock_set.rpe = 7.0  # Moderate RPE
            mock_sets.append(mock_set)
        
        mock_query = Mock()
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_sets
        self.db.query.return_value = mock_query
        
        result = self.service._check_struggling(athlete_id=1, exercise_id=1)
        
        assert result["is_struggling"] == False
        assert result["avg_rpe"] < 8.0
    
    def test_not_struggling_insufficient_data(self):
        """Test that struggling is not detected with insufficient data."""
        mock_sets = []
        for i in range(2):  # Only 2 sets
            mock_set = Mock()
            mock_set.rpe = 9.0
            mock_sets.append(mock_set)
        
        mock_query = Mock()
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_sets
        self.db.query.return_value = mock_query
        
        result = self.service._check_struggling(athlete_id=1, exercise_id=1)
        
        assert result["is_struggling"] == False


class TestVolumeCeilingTrigger:
    """Test volume ceiling (MRV) detection trigger."""
    
    def setup_method(self):
        """Setup for each test."""
        self.db = Mock()
        self.service = IntensityTechniqueService(self.db)
    
    def test_at_volume_ceiling(self):
        """Test detection when weekly sets are at MRV."""
        # Mock exercise query
        mock_exercise = Mock()
        mock_exercise.id = 1
        mock_exercise.primary_muscles = ["chest"]
        
        mock_ex_query = Mock()
        mock_ex_query.filter.return_value = mock_ex_query
        mock_ex_query.all.return_value = [mock_exercise]
        
        # Mock set count query - return count near MRV
        mock_set_query = Mock()
        mock_set_query.join.return_value = mock_set_query
        mock_set_query.filter.return_value = mock_set_query
        mock_set_query.count.return_value = 18  # 90% of intermediate MRV (20)
        
        def query_side_effect(model):
            from app.models import Exercise, ExerciseSet
            if model.__name__ == 'Exercise':
                return mock_ex_query
            return mock_set_query
        
        self.db.query.side_effect = query_side_effect
        
        result = self.service._check_volume_ceiling(
            athlete_id=1,
            experience=TrainingExperience.INTERMEDIATE,
            muscle_group=MuscleGroup.CHEST
        )
        
        assert result["at_ceiling"] == True
        assert result["percentage_of_mrv"] >= 90.0
    
    def test_below_volume_ceiling(self):
        """Test detection when weekly sets are well below MRV."""
        mock_exercise = Mock()
        mock_exercise.id = 1
        mock_exercise.primary_muscles = ["chest"]
        
        mock_ex_query = Mock()
        mock_ex_query.filter.return_value = mock_ex_query
        mock_ex_query.all.return_value = [mock_exercise]
        
        mock_set_query = Mock()
        mock_set_query.join.return_value = mock_set_query
        mock_set_query.filter.return_value = mock_set_query
        mock_set_query.count.return_value = 10  # 50% of intermediate MRV
        
        def query_side_effect(model):
            from app.models import Exercise, ExerciseSet
            if model.__name__ == 'Exercise':
                return mock_ex_query
            return mock_set_query
        
        self.db.query.side_effect = query_side_effect
        
        result = self.service._check_volume_ceiling(
            athlete_id=1,
            experience=TrainingExperience.INTERMEDIATE,
            muscle_group=MuscleGroup.CHEST
        )
        
        assert result["at_ceiling"] == False
        assert result["percentage_of_mrv"] < 90.0


class TestPhaseTrigger:
    """Test phase-based trigger (late accumulation)."""
    
    def setup_method(self):
        """Setup for each test."""
        self.db = Mock()
        self.service = IntensityTechniqueService(self.db)
    
    def test_late_accumulation_triggers_technique(self):
        """Test that late accumulation phase (week 3-4) triggers technique recommendation."""
        self.service._check_plateau = Mock(return_value={"is_plateau": False})
        self.service._check_struggling = Mock(return_value={"is_struggling": False})
        self.service._check_volume_ceiling = Mock(return_value={"at_ceiling": False})
        
        result = self.service.recommend_techniques(
            athlete_id=1,
            exercise_id=1,
            training_type=TrainingType.HYPERTROPHY,
            training_phase=TrainingPhase.ACCUMULATION,
            exercise_type=ExerciseType.ISOLATION,
            experience=TrainingExperience.INTERMEDIATE,
            readiness_score=0.8,
            is_primary=False,
            order_in_workout=2,
            performance_level="progressing",
            week_number=3,  # Week 3 - late accumulation
            muscle_group=MuscleGroup.BICEPS
        )
        
        assert result["triggers"]["phase_based_triggered"] == True
        assert result["triggers"]["any_triggered"] == True
        # Should recommend a technique (not just straight sets)
        assert result["set_type"] != SetType.STRAIGHT or result["rep_style"] != RepStyle.NORMAL
    
    def test_deload_week_no_trigger(self):
        """Test that deload week (week 4 of every 4) doesn't trigger technique."""
        self.service._check_plateau = Mock(return_value={"is_plateau": False})
        self.service._check_struggling = Mock(return_value={"is_struggling": False})
        self.service._check_volume_ceiling = Mock(return_value={"at_ceiling": False})
        
        result = self.service.recommend_techniques(
            athlete_id=1,
            exercise_id=1,
            training_type=TrainingType.HYPERTROPHY,
            training_phase=TrainingPhase.ACCUMULATION,
            exercise_type=ExerciseType.ISOLATION,
            experience=TrainingExperience.INTERMEDIATE,
            readiness_score=0.8,
            is_primary=False,
            order_in_workout=2,
            performance_level="progressing",
            week_number=4,  # Week 4 - deload
            muscle_group=MuscleGroup.BICEPS
        )
        
        # Week 4 (deload) should not trigger phase-based technique
        assert result["triggers"]["phase_based_triggered"] == False


class TestTechniqueSelection:
    """Test technique selection based on triggers and context."""
    
    def setup_method(self):
        """Setup for each test."""
        self.db = Mock()
        self.service = IntensityTechniqueService(self.db)
    
    def test_isolation_plateau_gets_drop_set(self):
        """Test that isolation exercise with plateau gets drop set recommendation."""
        self.service._check_plateau = Mock(return_value={"is_plateau": True})
        self.service._check_struggling = Mock(return_value={"is_struggling": False})
        self.service._check_volume_ceiling = Mock(return_value={"at_ceiling": False})
        
        result = self.service.recommend_techniques(
            athlete_id=1,
            exercise_id=1,
            training_type=TrainingType.HYPERTROPHY,
            training_phase=TrainingPhase.ACCUMULATION,
            exercise_type=ExerciseType.ISOLATION,
            experience=TrainingExperience.INTERMEDIATE,
            readiness_score=0.8,
            is_primary=False,
            order_in_workout=2,
            performance_level="struggling",
            week_number=2,
            muscle_group=MuscleGroup.BICEPS
        )
        
        # Isolation with plateau should get drop set or myo-reps
        assert result["set_type"] in [SetType.DROP_SET, SetType.MYO_REPS]
        assert "plateau" in result["reasoning"].lower()
    
    def test_compound_strength_plateau_gets_cluster(self):
        """Test that compound strength exercise with plateau gets cluster sets."""
        self.service._check_plateau = Mock(return_value={"is_plateau": True})
        self.service._check_struggling = Mock(return_value={"is_struggling": False})
        self.service._check_volume_ceiling = Mock(return_value={"at_ceiling": False})
        
        result = self.service.recommend_techniques(
            athlete_id=1,
            exercise_id=1,
            training_type=TrainingType.STRENGTH,
            training_phase=TrainingPhase.INTENSIFICATION,
            exercise_type=ExerciseType.COMPOUND,
            experience=TrainingExperience.ADVANCED,
            readiness_score=0.8,
            is_primary=True,
            order_in_workout=1,
            performance_level="struggling",
            week_number=2,
            muscle_group=MuscleGroup.CHEST
        )
        
        # Compound strength with plateau should get cluster sets
        assert result["set_type"] in [SetType.CLUSTER_SET, SetType.REST_PAUSE]
    
    def test_volume_ceiling_isolation_gets_myo_reps(self):
        """Test that isolation at volume ceiling gets myo-reps."""
        self.service._check_plateau = Mock(return_value={"is_plateau": False})
        self.service._check_struggling = Mock(return_value={"is_struggling": False})
        self.service._check_volume_ceiling = Mock(return_value={"at_ceiling": True})
        
        result = self.service.recommend_techniques(
            athlete_id=1,
            exercise_id=1,
            training_type=TrainingType.HYPERTROPHY,
            training_phase=TrainingPhase.ACCUMULATION,
            exercise_type=ExerciseType.ISOLATION,
            experience=TrainingExperience.INTERMEDIATE,
            readiness_score=0.8,
            is_primary=False,
            order_in_workout=2,
            performance_level="progressing",
            week_number=2,
            muscle_group=MuscleGroup.BICEPS
        )
        
        # Isolation at volume ceiling should get myo-reps (efficient volume)
        assert result["set_type"] in [SetType.MYO_REPS, SetType.DROP_SET]
    
    def test_low_readiness_no_high_fatigue_techniques(self):
        """Test that low readiness prevents high-fatigue techniques."""
        self.service._check_plateau = Mock(return_value={"is_plateau": True})
        self.service._check_struggling = Mock(return_value={"is_struggling": False})
        self.service._check_volume_ceiling = Mock(return_value={"at_ceiling": False})
        
        result = self.service.recommend_techniques(
            athlete_id=1,
            exercise_id=1,
            training_type=TrainingType.HYPERTROPHY,
            training_phase=TrainingPhase.ACCUMULATION,
            exercise_type=ExerciseType.ISOLATION,
            experience=TrainingExperience.INTERMEDIATE,
            readiness_score=0.4,  # Low readiness
            is_primary=False,
            order_in_workout=2,
            performance_level="struggling",
            week_number=2,
            muscle_group=MuscleGroup.BICEPS
        )
        
        # With low readiness, should avoid high-fatigue techniques
        if result["set_type"] != SetType.STRAIGHT:
            set_config = SET_TYPE_CONFIG.get(result["set_type"], {})
            assert set_config.get("fatigue_multiplier", 1.0) <= 1.2


class TestRepStyleSelection:
    """Test rep style selection."""
    
    def setup_method(self):
        """Setup for each test."""
        self.db = Mock()
        self.service = IntensityTechniqueService(self.db)
    
    def test_lengthened_partials_for_isolation_plateau(self):
        """Test that isolation plateau can get lengthened partials."""
        self.service._check_plateau = Mock(return_value={"is_plateau": True})
        self.service._check_struggling = Mock(return_value={"is_struggling": False})
        self.service._check_volume_ceiling = Mock(return_value={"at_ceiling": False})
        
        result = self.service.recommend_techniques(
            athlete_id=1,
            exercise_id=1,
            training_type=TrainingType.HYPERTROPHY,
            training_phase=TrainingPhase.ACCUMULATION,
            exercise_type=ExerciseType.ISOLATION,
            experience=TrainingExperience.INTERMEDIATE,
            readiness_score=0.8,
            is_primary=False,
            order_in_workout=2,
            performance_level="struggling",
            week_number=2,
            muscle_group=MuscleGroup.BICEPS
        )
        
        # For hypertrophy isolation, lengthened partials are a valid choice
        if result["rep_style"] != RepStyle.NORMAL:
            assert result["rep_style"] in [RepStyle.LENGTHENED_PARTIALS, RepStyle.TEMPO_ECCENTRIC]


class TestValidateCombination:
    """Test set type and rep style combination validation."""
    
    def setup_method(self):
        """Setup for each test."""
        self.db = Mock()
        self.service = IntensityTechniqueService(self.db)
    
    def test_valid_straight_set_combinations(self):
        """Test that straight sets work with all rep styles."""
        valid_combinations = [
            (SetType.STRAIGHT, RepStyle.NORMAL),
            (SetType.STRAIGHT, RepStyle.LENGTHENED_PARTIALS),
            (SetType.STRAIGHT, RepStyle.TEMPO_ECCENTRIC),
            (SetType.STRAIGHT, RepStyle.TEMPO_PAUSED),
            (SetType.STRAIGHT, RepStyle.ECCENTRIC_OVERLOAD),
        ]
        
        for set_type, rep_style in valid_combinations:
            assert self.service.validate_combination(set_type, rep_style) == True
    
    def test_invalid_myo_reps_with_tempo(self):
        """Test that myo-reps only work with normal tempo."""
        # Myo-reps should only work with normal reps
        assert self.service.validate_combination(SetType.MYO_REPS, RepStyle.NORMAL) == True
        assert self.service.validate_combination(SetType.MYO_REPS, RepStyle.TEMPO_ECCENTRIC) == False
        assert self.service.validate_combination(SetType.MYO_REPS, RepStyle.LENGTHENED_PARTIALS) == False
    
    def test_invalid_drop_set_with_eccentric_overload(self):
        """Test that drop sets don't work with eccentric overload."""
        assert self.service.validate_combination(SetType.DROP_SET, RepStyle.ECCENTRIC_OVERLOAD) == False
    
    def test_cluster_set_valid_combinations(self):
        """Test cluster set valid combinations."""
        assert self.service.validate_combination(SetType.CLUSTER_SET, RepStyle.NORMAL) == True
        assert self.service.validate_combination(SetType.CLUSTER_SET, RepStyle.TEMPO_ECCENTRIC) == True
        assert self.service.validate_combination(SetType.CLUSTER_SET, RepStyle.ECCENTRIC_OVERLOAD) == True
        # Lengthened partials don't make sense with cluster sets
        assert self.service.validate_combination(SetType.CLUSTER_SET, RepStyle.LENGTHENED_PARTIALS) == False


class TestGetDefaultParams:
    """Test getting default parameters for techniques."""
    
    def setup_method(self):
        """Setup for each test."""
        self.db = Mock()
        self.service = IntensityTechniqueService(self.db)
    
    def test_drop_set_default_params(self):
        """Test default parameters for drop sets."""
        params = self.service.get_default_params(SetType.DROP_SET)
        
        assert "drop_percentage" in params
        assert "drops_count" in params
        assert params["drop_percentage"] == 0.20  # 20%
        assert params["drops_count"] >= 1
    
    def test_myo_reps_default_params(self):
        """Test default parameters for myo-reps."""
        params = self.service.get_default_params(SetType.MYO_REPS)
        
        assert "activation_reps" in params
        assert "rest_seconds" in params
        assert "mini_sets_reps" in params
        assert "target_total_reps" in params
    
    def test_cluster_set_default_params(self):
        """Test default parameters for cluster sets."""
        params = self.service.get_default_params(SetType.CLUSTER_SET)
        
        assert "reps_per_cluster" in params
        assert "rest_seconds" in params
        assert "clusters_count" in params
    
    def test_tempo_eccentric_default_params(self):
        """Test default parameters for tempo eccentric."""
        params = self.service.get_default_params(RepStyle.TEMPO_ECCENTRIC, is_rep_style=True)
        
        assert "eccentric_seconds" in params
        assert params["eccentric_seconds"] >= 3
    
    def test_straight_set_empty_params(self):
        """Test that straight sets have no special params."""
        params = self.service.get_default_params(SetType.STRAIGHT)
        
        assert params == {}
    
    def test_normal_rep_style_empty_params(self):
        """Test that normal rep style has no special params."""
        params = self.service.get_default_params(RepStyle.NORMAL, is_rep_style=True)
        
        assert params == {}


class TestCalculateFatigueImpact:
    """Test fatigue impact calculation."""
    
    def setup_method(self):
        """Setup for each test."""
        self.db = Mock()
        self.service = IntensityTechniqueService(self.db)
    
    def test_straight_set_normal_no_change(self):
        """Test that straight sets with normal reps have no fatigue change."""
        result = self.service.calculate_fatigue_impact(
            SetType.STRAIGHT,
            RepStyle.NORMAL,
            base_volume=1000
        )
        
        assert result["volume_multiplier"] == 1.0
        assert result["fatigue_multiplier"] == 1.0
        assert result["adjusted_volume"] == 1000
    
    def test_drop_set_increases_volume(self):
        """Test that drop sets increase effective volume."""
        result = self.service.calculate_fatigue_impact(
            SetType.DROP_SET,
            RepStyle.NORMAL,
            base_volume=1000
        )
        
        assert result["volume_multiplier"] > 1.0  # Drop sets add volume
        assert result["fatigue_multiplier"] > 1.0  # And fatigue
        assert result["adjusted_volume"] > 1000
    
    def test_myo_reps_high_volume_efficiency(self):
        """Test that myo-reps have high volume efficiency."""
        result = self.service.calculate_fatigue_impact(
            SetType.MYO_REPS,
            RepStyle.NORMAL,
            base_volume=1000
        )
        
        # Myo-reps: high volume multiplier, relatively low fatigue
        assert result["volume_multiplier"] > 1.3
        assert result["fatigue_multiplier"] < result["volume_multiplier"]
    
    def test_cluster_set_reduces_fatigue(self):
        """Test that cluster sets reduce fatigue per set."""
        result = self.service.calculate_fatigue_impact(
            SetType.CLUSTER_SET,
            RepStyle.NORMAL,
            base_volume=1000
        )
        
        # Cluster sets maintain volume but reduce fatigue
        assert result["volume_multiplier"] == 1.0
        assert result["fatigue_multiplier"] < 1.0
    
    def test_combined_set_type_and_rep_style(self):
        """Test combined impact of set type and rep style."""
        result = self.service.calculate_fatigue_impact(
            SetType.DROP_SET,
            RepStyle.TEMPO_ECCENTRIC,
            base_volume=1000
        )
        
        # Combined should multiply the individual multipliers
        drop_vol = SET_TYPE_CONFIG[SetType.DROP_SET]["volume_multiplier"]
        tempo_vol = REP_STYLE_CONFIG[RepStyle.TEMPO_ECCENTRIC]["volume_multiplier"]
        
        expected_vol_mult = drop_vol * tempo_vol
        assert abs(result["volume_multiplier"] - expected_vol_mult) < 0.01


class TestGenerateReasoning:
    """Test reasoning generation."""
    
    def setup_method(self):
        """Setup for each test."""
        self.db = Mock()
        self.service = IntensityTechniqueService(self.db)
    
    def test_plateau_reasoning(self):
        """Test reasoning includes plateau information."""
        triggers = {
            "plateau_detected": True,
            "struggling_detected": False,
            "volume_ceiling_detected": False,
            "phase_based_triggered": False,
            "any_triggered": True,
            "details": {}
        }
        
        reasoning = self.service._generate_reasoning(
            SetType.DROP_SET,
            RepStyle.NORMAL,
            triggers
        )
        
        assert "plateau" in reasoning.lower()
        assert "drop set" in reasoning.lower()
    
    def test_volume_ceiling_reasoning(self):
        """Test reasoning includes volume ceiling information."""
        triggers = {
            "plateau_detected": False,
            "struggling_detected": False,
            "volume_ceiling_detected": True,
            "phase_based_triggered": False,
            "any_triggered": True,
            "details": {}
        }
        
        reasoning = self.service._generate_reasoning(
            SetType.MYO_REPS,
            RepStyle.NORMAL,
            triggers
        )
        
        assert "volume ceiling" in reasoning.lower()
    
    def test_multiple_triggers_reasoning(self):
        """Test reasoning includes multiple triggers."""
        triggers = {
            "plateau_detected": True,
            "struggling_detected": True,
            "volume_ceiling_detected": False,
            "phase_based_triggered": True,
            "any_triggered": True,
            "details": {}
        }
        
        reasoning = self.service._generate_reasoning(
            SetType.REST_PAUSE,
            RepStyle.TEMPO_ECCENTRIC,
            triggers
        )
        
        # Should mention multiple triggers
        assert "plateau" in reasoning.lower()
        assert "tempo eccentric" in reasoning.lower()


class TestGetValidSetTypes:
    """Test getting valid set types for context."""
    
    def setup_method(self):
        """Setup for each test."""
        self.db = Mock()
        self.service = IntensityTechniqueService(self.db)
    
    def test_beginner_limited_options(self):
        """Test that beginners have limited technique options."""
        valid_types = self.service._get_valid_set_types(
            training_type=TrainingType.HYPERTROPHY,
            training_phase=TrainingPhase.ACCUMULATION,
            exercise_type=ExerciseType.ISOLATION,
            experience=TrainingExperience.BEGINNER,
            readiness_score=0.8
        )
        
        # Beginners should only have straight and maybe superset_antagonist
        assert SetType.STRAIGHT in valid_types
        assert SetType.DROP_SET not in valid_types  # Requires intermediate
        assert SetType.MYO_REPS not in valid_types  # Requires intermediate
    
    def test_advanced_more_options(self):
        """Test that advanced athletes have more technique options."""
        valid_types = self.service._get_valid_set_types(
            training_type=TrainingType.STRENGTH,
            training_phase=TrainingPhase.INTENSIFICATION,
            exercise_type=ExerciseType.COMPOUND,
            experience=TrainingExperience.ADVANCED,
            readiness_score=0.8
        )
        
        assert SetType.STRAIGHT in valid_types
        assert SetType.CLUSTER_SET in valid_types  # Advanced only
    
    def test_strength_excludes_hypertrophy_techniques(self):
        """Test that strength training excludes hypertrophy-specific techniques."""
        valid_types = self.service._get_valid_set_types(
            training_type=TrainingType.STRENGTH,
            training_phase=TrainingPhase.INTENSIFICATION,
            exercise_type=ExerciseType.COMPOUND,
            experience=TrainingExperience.ADVANCED,
            readiness_score=0.8
        )
        
        # Myo-reps are hypertrophy only
        assert SetType.MYO_REPS not in valid_types
    
    def test_isolation_excludes_compound_techniques(self):
        """Test that isolation exercises exclude compound-only techniques."""
        valid_types = self.service._get_valid_set_types(
            training_type=TrainingType.STRENGTH,
            training_phase=TrainingPhase.INTENSIFICATION,
            exercise_type=ExerciseType.ISOLATION,
            experience=TrainingExperience.ADVANCED,
            readiness_score=0.8
        )
        
        # Cluster sets are compound only
        assert SetType.CLUSTER_SET not in valid_types
    
    def test_low_readiness_excludes_high_fatigue(self):
        """Test that low readiness excludes high-fatigue techniques."""
        valid_types = self.service._get_valid_set_types(
            training_type=TrainingType.HYPERTROPHY,
            training_phase=TrainingPhase.ACCUMULATION,
            exercise_type=ExerciseType.ISOLATION,
            experience=TrainingExperience.INTERMEDIATE,
            readiness_score=0.4  # Low readiness
        )
        
        # With low readiness, high-fatigue techniques should be excluded
        for set_type in valid_types:
            if set_type != SetType.STRAIGHT:
                config = SET_TYPE_CONFIG.get(set_type, {})
                # Low readiness (< 0.6) should exclude fatigue_multiplier > 1.2
                assert config.get("fatigue_multiplier", 1.0) <= 1.2


class TestIntegrationScenarios:
    """Integration tests for complete recommendation scenarios."""
    
    def setup_method(self):
        """Setup for each test."""
        self.db = Mock()
        self.service = IntensityTechniqueService(self.db)
    
    def test_complete_hypertrophy_scenario_no_triggers(self):
        """Test complete scenario: intermediate hypertrophy, no triggers."""
        self.service._check_plateau = Mock(return_value={"is_plateau": False})
        self.service._check_struggling = Mock(return_value={"is_struggling": False})
        self.service._check_volume_ceiling = Mock(return_value={"at_ceiling": False})
        
        result = self.service.recommend_techniques(
            athlete_id=1,
            exercise_id=1,
            training_type=TrainingType.HYPERTROPHY,
            training_phase=TrainingPhase.ACCUMULATION,
            exercise_type=ExerciseType.COMPOUND,
            experience=TrainingExperience.INTERMEDIATE,
            readiness_score=0.8,
            is_primary=True,
            order_in_workout=1,
            performance_level="progressing",
            week_number=1,
            muscle_group=MuscleGroup.CHEST
        )
        
        # Should return defaults
        assert result["set_type"] == SetType.STRAIGHT
        assert result["rep_style"] == RepStyle.NORMAL
        assert result["triggers"]["any_triggered"] == False
        
        # Verify structure
        assert "set_type_params" in result
        assert "rep_style_params" in result
        assert "reasoning" in result
    
    def test_complete_plateau_breakthrough_scenario(self):
        """Test scenario: breaking through a plateau with techniques."""
        self.service._check_plateau = Mock(return_value={
            "is_plateau": True,
            "sessions_analyzed": 4,
            "improvement_percent": 0.5
        })
        self.service._check_struggling = Mock(return_value={"is_struggling": False})
        self.service._check_volume_ceiling = Mock(return_value={"at_ceiling": False})
        
        result = self.service.recommend_techniques(
            athlete_id=1,
            exercise_id=1,
            training_type=TrainingType.HYPERTROPHY,
            training_phase=TrainingPhase.ACCUMULATION,
            exercise_type=ExerciseType.ISOLATION,
            experience=TrainingExperience.INTERMEDIATE,
            readiness_score=0.75,
            is_primary=False,
            order_in_workout=3,
            performance_level="stalled",
            week_number=2,
            muscle_group=MuscleGroup.BICEPS
        )
        
        # Should recommend an intensity technique to break plateau
        assert result["set_type"] != SetType.STRAIGHT
        assert result["triggers"]["plateau_detected"] == True
        assert result["triggers"]["any_triggered"] == True
        
        # Verify params are provided
        assert len(result["set_type_params"]) > 0
    
    def test_complete_late_phase_scenario(self):
        """Test scenario: late accumulation with volume ceiling."""
        self.service._check_plateau = Mock(return_value={"is_plateau": False})
        self.service._check_struggling = Mock(return_value={"is_struggling": False})
        self.service._check_volume_ceiling = Mock(return_value={
            "at_ceiling": True,
            "weekly_sets": 18,
            "mrv": 20
        })
        
        result = self.service.recommend_techniques(
            athlete_id=1,
            exercise_id=1,
            training_type=TrainingType.HYPERTROPHY,
            training_phase=TrainingPhase.ACCUMULATION,
            exercise_type=ExerciseType.ISOLATION,
            experience=TrainingExperience.INTERMEDIATE,
            readiness_score=0.8,
            is_primary=False,
            order_in_workout=2,
            performance_level="progressing",
            week_number=3,  # Late accumulation
            muscle_group=MuscleGroup.BICEPS
        )
        
        # Should trigger from both volume ceiling and phase
        assert result["triggers"]["volume_ceiling_detected"] == True
        assert result["triggers"]["phase_based_triggered"] == True
        assert result["triggers"]["any_triggered"] == True
        
        # Should recommend volume-efficient technique
        assert result["set_type"] in [SetType.MYO_REPS, SetType.DROP_SET]

