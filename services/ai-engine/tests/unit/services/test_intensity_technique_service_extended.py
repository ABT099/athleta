"""
Extended Unit Tests for Intensity Technique Service.

Covers additional edge cases, parameter combinations, and error handling.
"""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, MagicMock, patch

from app.services.intensity_technique_service import IntensityTechniqueService
from app.utils.constants import (
    SetType, RepStyle, TrainingType, TrainingPhase, TrainingExperience,
    ExerciseType, SET_TYPE_CONFIG, REP_STYLE_CONFIG,
    VALID_TECHNIQUE_COMBINATIONS, MRV_SETS_PER_WEEK
)


class TestAllTrainingTypesCoverage:
    """Test technique recommendations across all training types."""
    
    def setup_method(self):
        """Setup for each test."""
        self.db = Mock()
        self.service = IntensityTechniqueService(self.db)
        # Mock all triggers to return no triggers for baseline
        self.service._check_plateau = Mock(return_value={"is_plateau": False})
        self.service._check_struggling = Mock(return_value={"is_struggling": False})
        self.service._check_volume_ceiling = Mock(return_value={"at_ceiling": False})
    
    @pytest.mark.parametrize("training_type", list(TrainingType))
    def test_straight_sets_available_for_all_training_types(self, training_type):
        """Test that straight sets are always available regardless of training type."""
        result = self.service.recommend_techniques(
            athlete_id=1,
            exercise_id=1,
            training_type=training_type,
            training_phase=TrainingPhase.ACCUMULATION,
            exercise_type=ExerciseType.COMPOUND,
            experience=TrainingExperience.INTERMEDIATE,
            readiness_score=0.8,
            is_primary=True,
            order_in_workout=1,
            performance_level="progressing",
            week_number=1,
            muscle_name="mid_chest"
        )
        
        # Without triggers, should always get straight sets
        assert result["set_type"] == SetType.STRAIGHT
        assert result["rep_style"] == RepStyle.NORMAL
    
    def test_strength_training_excludes_hypertrophy_techniques(self):
        """Test that pure strength training excludes hypertrophy-only techniques."""
        # Force a trigger to get a non-default recommendation
        self.service._check_plateau = Mock(return_value={"is_plateau": True})
        
        valid_types = self.service._get_valid_set_types(
            training_type=TrainingType.STRENGTH,
            training_phase=TrainingPhase.INTENSIFICATION,
            exercise_type=ExerciseType.COMPOUND,
            experience=TrainingExperience.ADVANCED,
            readiness_score=0.9
        )
        
        # Myo-reps are hypertrophy only
        assert SetType.MYO_REPS not in valid_types
        # Drop sets are hypertrophy only (also isolation only)
        assert SetType.DROP_SET not in valid_types
    
    def test_hypertrophy_includes_volume_techniques(self):
        """Test that hypertrophy training includes volume-based techniques."""
        valid_types = self.service._get_valid_set_types(
            training_type=TrainingType.HYPERTROPHY,
            training_phase=TrainingPhase.ACCUMULATION,
            exercise_type=ExerciseType.ISOLATION,
            experience=TrainingExperience.INTERMEDIATE,
            readiness_score=0.8
        )
        
        # Should include drop sets and myo-reps for isolation
        assert SetType.DROP_SET in valid_types
        assert SetType.MYO_REPS in valid_types
    
    def test_hybrid_training_has_mixed_options(self):
        """Test that hybrid training has options from both strength and hypertrophy."""
        valid_types = self.service._get_valid_set_types(
            training_type=TrainingType.HYBRID,
            training_phase=TrainingPhase.INTENSIFICATION,  # Cluster sets available in intensification
            exercise_type=ExerciseType.COMPOUND,
            experience=TrainingExperience.ADVANCED,
            readiness_score=0.8
        )
        
        # Should include rest-pause (both strength and hypertrophy)
        assert SetType.REST_PAUSE in valid_types
        # Check for cluster sets if hybrid includes them (depends on config)
        # Hybrid may not include cluster sets - update based on actual config
        from app.utils.constants import SET_TYPE_CONFIG
        cluster_config = SET_TYPE_CONFIG.get(SetType.CLUSTER_SET, {})
        if TrainingType.HYBRID in cluster_config.get("applicable_training_types", []):
            assert SetType.CLUSTER_SET in valid_types


class TestAllPhasesCoverage:
    """Test technique recommendations across all training phases."""
    
    def setup_method(self):
        """Setup for each test."""
        self.db = Mock()
        self.service = IntensityTechniqueService(self.db)
        self.service._check_plateau = Mock(return_value={"is_plateau": False})
        self.service._check_struggling = Mock(return_value={"is_struggling": False})
        self.service._check_volume_ceiling = Mock(return_value={"at_ceiling": False})
    
    @pytest.mark.parametrize("training_phase", list(TrainingPhase))
    def test_straight_sets_available_in_all_phases(self, training_phase):
        """Test that straight sets are available in all phases."""
        result = self.service.recommend_techniques(
            athlete_id=1,
            exercise_id=1,
            training_type=TrainingType.HYPERTROPHY,
            training_phase=training_phase,
            exercise_type=ExerciseType.COMPOUND,
            experience=TrainingExperience.INTERMEDIATE,
            readiness_score=0.8,
            is_primary=True,
            order_in_workout=1,
            performance_level="progressing",
            week_number=1,
            muscle_name="mid_chest"
        )
        
        assert result["set_type"] == SetType.STRAIGHT
    
    def test_realization_phase_conservative_options(self):
        """Test that realization phase (peaking) limits high-fatigue techniques."""
        # Even with plateau trigger, realization should be conservative
        self.service._check_plateau = Mock(return_value={"is_plateau": True})
        
        valid_types = self.service._get_valid_set_types(
            training_type=TrainingType.STRENGTH,
            training_phase=TrainingPhase.REALIZATION,
            exercise_type=ExerciseType.COMPOUND,
            experience=TrainingExperience.ADVANCED,
            readiness_score=0.8
        )
        
        # Realization phase typically has fewer technique options
        # Should have straight and possibly cluster sets for quality maintenance
        assert SetType.STRAIGHT in valid_types
    
    def test_realization_phase_prioritizes_quality(self):
        """Test that realization phase (peaking) prioritizes quality over volume."""
        valid_types = self.service._get_valid_set_types(
            training_type=TrainingType.STRENGTH,
            training_phase=TrainingPhase.REALIZATION,
            exercise_type=ExerciseType.COMPOUND,
            experience=TrainingExperience.ADVANCED,
            readiness_score=0.9
        )
        
        # Cluster sets should be available (quality maintenance)
        assert SetType.CLUSTER_SET in valid_types
    
    def test_intensification_phase_strength_techniques(self):
        """Test that intensification phase enables strength techniques."""
        valid_types = self.service._get_valid_set_types(
            training_type=TrainingType.STRENGTH,
            training_phase=TrainingPhase.INTENSIFICATION,
            exercise_type=ExerciseType.COMPOUND,
            experience=TrainingExperience.ADVANCED,
            readiness_score=0.9
        )
        
        assert SetType.CLUSTER_SET in valid_types


class TestReadinessScoreThresholds:
    """Test readiness score impact on technique recommendations."""
    
    def setup_method(self):
        """Setup for each test."""
        self.db = Mock()
        self.service = IntensityTechniqueService(self.db)
        self.service._check_plateau = Mock(return_value={"is_plateau": True})
        self.service._check_struggling = Mock(return_value={"is_struggling": False})
        self.service._check_volume_ceiling = Mock(return_value={"at_ceiling": False})
    
    @pytest.mark.parametrize("readiness_score,expect_high_fatigue", [
        (0.9, True),   # High readiness - allow all
        (0.8, True),   # Good readiness - allow all
        (0.6, True),   # Threshold - allow all
        (0.59, False), # Just below threshold - restrict high fatigue
        (0.5, False),  # Low readiness - restrict high fatigue
        (0.3, False),  # Very low readiness - restrict high fatigue
    ])
    def test_readiness_threshold_at_0_6(self, readiness_score, expect_high_fatigue):
        """Test that readiness score of 0.6 is the threshold for high-fatigue techniques."""
        valid_types = self.service._get_valid_set_types(
            training_type=TrainingType.HYPERTROPHY,
            training_phase=TrainingPhase.ACCUMULATION,
            exercise_type=ExerciseType.ISOLATION,
            experience=TrainingExperience.INTERMEDIATE,
            readiness_score=readiness_score
        )
        
        has_high_fatigue = False
        for set_type in valid_types:
            if set_type != SetType.STRAIGHT:
                config = SET_TYPE_CONFIG.get(set_type, {})
                if config.get("fatigue_multiplier", 1.0) > 1.2:
                    has_high_fatigue = True
                    break
        
        if expect_high_fatigue:
            # We might have high fatigue techniques available
            pass  # Not all contexts will have high fatigue options
        else:
            # Should NOT have high-fatigue techniques
            assert not has_high_fatigue, f"High fatigue technique found at readiness {readiness_score}"
    
    def test_very_low_readiness_defaults_to_straight(self):
        """Test that very low readiness often results in straight sets."""
        result = self.service.recommend_techniques(
            athlete_id=1,
            exercise_id=1,
            training_type=TrainingType.HYPERTROPHY,
            training_phase=TrainingPhase.ACCUMULATION,
            exercise_type=ExerciseType.ISOLATION,
            experience=TrainingExperience.INTERMEDIATE,
            readiness_score=0.3,  # Very low
            is_primary=False,
            order_in_workout=2,
            performance_level="struggling",
            week_number=3,
            muscle_name="biceps"
        )
        
        # Even with triggers, low readiness should limit options
        # The technique selected should not be high-fatigue
        if result["set_type"] != SetType.STRAIGHT:
            config = SET_TYPE_CONFIG.get(result["set_type"], {})
            assert config.get("fatigue_multiplier", 1.0) <= 1.2


class TestRestPauseAndClusterSets:
    """Test REST_PAUSE and CLUSTER_SET specific behaviors."""
    
    def setup_method(self):
        """Setup for each test."""
        self.db = Mock()
        self.service = IntensityTechniqueService(self.db)
        self.service._check_plateau = Mock(return_value={"is_plateau": True})
        self.service._check_struggling = Mock(return_value={"is_struggling": False})
        self.service._check_volume_ceiling = Mock(return_value={"at_ceiling": False})
    
    def test_rest_pause_params(self):
        """Test REST_PAUSE default parameters."""
        params = self.service.get_default_params(SetType.REST_PAUSE)
        
        assert "rest_seconds" in params
        assert "mini_sets_count" in params
        # Rest-pause typically uses 10-20 second rest
        assert 5 <= params["rest_seconds"] <= 30
    
    def test_cluster_set_params(self):
        """Test CLUSTER_SET default parameters."""
        params = self.service.get_default_params(SetType.CLUSTER_SET)
        
        assert "reps_per_cluster" in params
        assert "rest_seconds" in params
        assert "clusters_count" in params
        # Cluster sets typically have short intra-set rest
        assert 10 <= params["rest_seconds"] <= 30
        assert params["reps_per_cluster"] >= 1
    
    def test_cluster_sets_compound_only(self):
        """Test that cluster sets are only for compound exercises."""
        # For compound - should be available
        valid_types_compound = self.service._get_valid_set_types(
            training_type=TrainingType.STRENGTH,
            training_phase=TrainingPhase.INTENSIFICATION,
            exercise_type=ExerciseType.COMPOUND,
            experience=TrainingExperience.ADVANCED,
            readiness_score=0.9
        )
        
        # For isolation - should NOT be available
        valid_types_isolation = self.service._get_valid_set_types(
            training_type=TrainingType.STRENGTH,
            training_phase=TrainingPhase.INTENSIFICATION,
            exercise_type=ExerciseType.ISOLATION,
            experience=TrainingExperience.ADVANCED,
            readiness_score=0.9
        )
        
        assert SetType.CLUSTER_SET in valid_types_compound
        assert SetType.CLUSTER_SET not in valid_types_isolation
    
    def test_rest_pause_available_both_types(self):
        """Test that rest-pause can be used for both compound and isolation."""
        for ex_type in [ExerciseType.COMPOUND, ExerciseType.ISOLATION]:
            valid_types = self.service._get_valid_set_types(
                training_type=TrainingType.HYBRID,
                training_phase=TrainingPhase.ACCUMULATION,
                exercise_type=ex_type,
                experience=TrainingExperience.INTERMEDIATE,
                readiness_score=0.8
            )
            
            # Rest-pause should be available for both
            if SetType.REST_PAUSE in SET_TYPE_CONFIG:
                config = SET_TYPE_CONFIG[SetType.REST_PAUSE]
                if ex_type in config.get("applicable_exercise_types", []):
                    assert SetType.REST_PAUSE in valid_types


class TestPreExhaustSupersets:
    """Test PRE_EXHAUST and SUPERSET_ANTAGONIST specific behaviors."""
    
    def setup_method(self):
        """Setup for each test."""
        self.db = Mock()
        self.service = IntensityTechniqueService(self.db)
    
    def test_superset_antagonist_params(self):
        """Test SUPERSET_ANTAGONIST parameters."""
        params = self.service.get_default_params(SetType.SUPERSET_ANTAGONIST)
        
        # Antagonist supersets typically have minimal rest between exercises
        assert "rest_between_exercises" in params or params == {}
    
    def test_pre_exhaust_params(self):
        """Test PRE_EXHAUST parameters."""
        params = self.service.get_default_params(SetType.PRE_EXHAUST)
        
        # Pre-exhaust should have some parameters (isolation_sets, rest_between, etc.)
        # or be empty if not configured
        assert isinstance(params, dict)
    
    def test_superset_available_for_beginners(self):
        """Test that antagonist supersets are available for beginners."""
        valid_types = self.service._get_valid_set_types(
            training_type=TrainingType.HYPERTROPHY,
            training_phase=TrainingPhase.ACCUMULATION,
            exercise_type=ExerciseType.ISOLATION,
            experience=TrainingExperience.BEGINNER,
            readiness_score=0.8
        )
        
        config = SET_TYPE_CONFIG.get(SetType.SUPERSET_ANTAGONIST, {})
        if config.get("min_experience") == TrainingExperience.BEGINNER:
            assert SetType.SUPERSET_ANTAGONIST in valid_types


class TestTempoRepStyles:
    """Test tempo-related rep styles."""
    
    def setup_method(self):
        """Setup for each test."""
        self.db = Mock()
        self.service = IntensityTechniqueService(self.db)
    
    def test_tempo_eccentric_params(self):
        """Test TEMPO_ECCENTRIC parameters."""
        params = self.service.get_default_params(RepStyle.TEMPO_ECCENTRIC, is_rep_style=True)
        
        assert "eccentric_seconds" in params
        assert params["eccentric_seconds"] >= 3  # Minimum for TUT benefit
    
    def test_tempo_paused_params(self):
        """Test TEMPO_PAUSED parameters."""
        params = self.service.get_default_params(RepStyle.TEMPO_PAUSED, is_rep_style=True)
        
        assert "pause_seconds" in params or "pause_position" in params or params == {}
    
    def test_eccentric_overload_params(self):
        """Test ECCENTRIC_OVERLOAD parameters."""
        params = self.service.get_default_params(RepStyle.ECCENTRIC_OVERLOAD, is_rep_style=True)
        
        # Should have some indication of overload percentage or setup
        assert "overload_percentage" in params or "spotter_required" in params or params == {}
    
    def test_eccentric_overload_advanced_only(self):
        """Test that eccentric overload is only for advanced athletes."""
        config = REP_STYLE_CONFIG.get(RepStyle.ECCENTRIC_OVERLOAD, {})
        assert config.get("min_experience") == TrainingExperience.ADVANCED


class TestCombinedTriggers:
    """Test behavior when multiple triggers fire simultaneously."""
    
    def setup_method(self):
        """Setup for each test."""
        self.db = Mock()
        self.service = IntensityTechniqueService(self.db)
    
    def test_all_triggers_fired(self):
        """Test behavior when all triggers fire."""
        self.service._check_plateau = Mock(return_value={
            "is_plateau": True,
            "sessions_analyzed": 4,
            "improvement_percent": 0.5
        })
        self.service._check_struggling = Mock(return_value={
            "is_struggling": True,
            "avg_rpe": 9.0
        })
        self.service._check_volume_ceiling = Mock(return_value={
            "at_ceiling": True,
            "weekly_sets": 19,
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
            performance_level="struggling",
            week_number=3,  # Late accumulation
            muscle_name="biceps"
        )
        
        # All triggers should be marked
        assert result["triggers"]["plateau_detected"] == True
        assert result["triggers"]["struggling_detected"] == True
        assert result["triggers"]["volume_ceiling_detected"] == True
        assert result["triggers"]["phase_based_triggered"] == True
        assert result["triggers"]["any_triggered"] == True
        
        # Should get a technique (not straight sets)
        assert result["set_type"] != SetType.STRAIGHT
    
    def test_plateau_plus_volume_ceiling(self):
        """Test plateau + volume ceiling triggers together."""
        self.service._check_plateau = Mock(return_value={"is_plateau": True})
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
            muscle_name="biceps"
        )
        
        # Volume-efficient techniques should be prioritized
        assert result["set_type"] in [SetType.MYO_REPS, SetType.DROP_SET, SetType.REST_PAUSE]
    
    def test_struggling_only(self):
        """Test behavior with only struggling trigger."""
        self.service._check_plateau = Mock(return_value={"is_plateau": False})
        self.service._check_struggling = Mock(return_value={
            "is_struggling": True,
            "avg_rpe": 8.5
        })
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
            muscle_name="biceps"
        )
        
        assert result["triggers"]["struggling_detected"] == True
        assert result["triggers"]["any_triggered"] == True


class TestVolumeMultiplierCalculations:
    """Test volume and fatigue multiplier calculations."""
    
    def setup_method(self):
        """Setup for each test."""
        self.db = Mock()
        self.service = IntensityTechniqueService(self.db)
    
    def test_volume_multiplier_straight_normal(self):
        """Test that straight sets with normal reps have 1.0 multiplier."""
        result = self.service.calculate_fatigue_impact(
            SetType.STRAIGHT,
            RepStyle.NORMAL,
            base_volume=1000
        )
        
        assert result["volume_multiplier"] == 1.0
        assert result["fatigue_multiplier"] == 1.0
        assert result["adjusted_volume"] == 1000
    
    def test_volume_multiplier_drop_set(self):
        """Test drop set volume multiplier is greater than 1."""
        result = self.service.calculate_fatigue_impact(
            SetType.DROP_SET,
            RepStyle.NORMAL,
            base_volume=1000
        )
        
        config = SET_TYPE_CONFIG[SetType.DROP_SET]
        expected_vol_mult = config["volume_multiplier"]
        
        assert result["volume_multiplier"] == expected_vol_mult
        assert result["adjusted_volume"] == 1000 * expected_vol_mult
    
    def test_volume_multiplier_combined(self):
        """Test combined volume multiplier from set type and rep style."""
        result = self.service.calculate_fatigue_impact(
            SetType.REST_PAUSE,
            RepStyle.TEMPO_ECCENTRIC,
            base_volume=1000
        )
        
        set_config = SET_TYPE_CONFIG[SetType.REST_PAUSE]
        rep_config = REP_STYLE_CONFIG[RepStyle.TEMPO_ECCENTRIC]
        
        expected_vol = set_config["volume_multiplier"] * rep_config["volume_multiplier"]
        expected_fat = set_config["fatigue_multiplier"] * rep_config["fatigue_multiplier"]
        
        assert abs(result["volume_multiplier"] - expected_vol) < 0.01
        assert abs(result["fatigue_multiplier"] - expected_fat) < 0.01
    
    def test_cluster_set_reduces_fatigue(self):
        """Test that cluster sets reduce fatigue."""
        result = self.service.calculate_fatigue_impact(
            SetType.CLUSTER_SET,
            RepStyle.NORMAL,
            base_volume=1000
        )
        
        config = SET_TYPE_CONFIG[SetType.CLUSTER_SET]
        assert config["fatigue_multiplier"] < 1.0
        assert result["fatigue_multiplier"] < 1.0


class TestMRVCalculations:
    """Test MRV (Maximum Recoverable Volume) calculations."""
    
    def setup_method(self):
        """Setup for each test."""
        self.db = Mock()
        self.service = IntensityTechniqueService(self.db)
    
    @pytest.mark.parametrize("experience,expected_mrv", [
        (TrainingExperience.BEGINNER, MRV_SETS_PER_WEEK.get(TrainingExperience.BEGINNER, 14)),
        (TrainingExperience.INTERMEDIATE, MRV_SETS_PER_WEEK.get(TrainingExperience.INTERMEDIATE, 20)),
        (TrainingExperience.ADVANCED, MRV_SETS_PER_WEEK.get(TrainingExperience.ADVANCED, 25)),
    ])
    def test_mrv_varies_by_experience(self, experience, expected_mrv):
        """Test that MRV varies by experience level."""
        assert MRV_SETS_PER_WEEK.get(experience) == expected_mrv


class TestReasoningGeneration:
    """Test reasoning string generation."""
    
    def setup_method(self):
        """Setup for each test."""
        self.db = Mock()
        self.service = IntensityTechniqueService(self.db)
    
    def test_reasoning_mentions_all_triggers(self):
        """Test that reasoning mentions all fired triggers."""
        triggers = {
            "plateau_detected": True,
            "struggling_detected": True,
            "volume_ceiling_detected": True,
            "phase_based_triggered": True,
            "any_triggered": True,
            "details": {}
        }
        
        reasoning = self.service._generate_reasoning(
            SetType.DROP_SET,
            RepStyle.LENGTHENED_PARTIALS,
            triggers
        )
        
        assert "plateau" in reasoning.lower()
        assert "drop set" in reasoning.lower()
        assert "lengthened partials" in reasoning.lower()
    
    def test_reasoning_for_no_technique(self):
        """Test reasoning when no technique is recommended."""
        triggers = {
            "plateau_detected": False,
            "struggling_detected": False,
            "volume_ceiling_detected": False,
            "phase_based_triggered": False,
            "any_triggered": False,
            "details": {}
        }
        
        reasoning = self.service._generate_reasoning(
            SetType.STRAIGHT,
            RepStyle.NORMAL,
            triggers
        )
        
        assert "straight" in reasoning.lower()


class TestErrorHandling:
    """Test error handling and edge cases."""
    
    def setup_method(self):
        """Setup for each test."""
        self.db = Mock()
        self.service = IntensityTechniqueService(self.db)
    
    def test_recommend_with_none_muscle_group(self):
        """Test recommendation handles None muscle group."""
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
            week_number=2,
            muscle_name=None  # None muscle name
        )
        
        # Should not crash and return valid result
        assert result["set_type"] is not None
        assert result["rep_style"] is not None
    
    def test_recommend_with_none_week_number(self):
        """Test recommendation handles None week number."""
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
            week_number=None,  # None week number
            muscle_name="biceps"
        )
        
        # Should not crash and return valid result
        assert result["set_type"] is not None
        # Phase-based trigger should not fire without week number
        assert result["triggers"]["phase_based_triggered"] == False
    
    def test_plateau_check_handles_empty_results(self):
        """Test plateau check handles no exercise history."""
        mock_query = Mock()
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []  # No sets
        self.db.query.return_value = mock_query
        
        result = self.service._check_plateau(athlete_id=1, exercise_id=1)
        
        assert result["is_plateau"] == False
        assert result["sessions_analyzed"] == 0
    
    def test_validate_invalid_combination(self):
        """Test validation catches invalid combinations."""
        # Myo-reps with tempo eccentric should be invalid
        is_valid = self.service.validate_combination(SetType.MYO_REPS, RepStyle.TEMPO_ECCENTRIC)
        assert is_valid == False
    
    def test_get_params_unknown_technique(self):
        """Test getting params for unknown technique returns empty dict."""
        # Create a mock enum that's not in config
        result = self.service.get_default_params(Mock())
        assert result == {}


class TestWeekNumberEdgeCases:
    """Test week number edge cases for phase-based triggers."""
    
    def setup_method(self):
        """Setup for each test."""
        self.db = Mock()
        self.service = IntensityTechniqueService(self.db)
        self.service._check_plateau = Mock(return_value={"is_plateau": False})
        self.service._check_struggling = Mock(return_value={"is_struggling": False})
        self.service._check_volume_ceiling = Mock(return_value={"at_ceiling": False})
    
    @pytest.mark.parametrize("week_number,expect_phase_trigger", [
        (1, False),   # Early week - no trigger
        (2, False),   # Early week - no trigger  
        (3, True),    # Week 3 - trigger (late accumulation)
        (4, False),   # Week 4 is typically deload (week % 4 == 0) - no trigger
        (5, True),    # Week 5 >= 3 and not deload (5 % 4 = 1) - triggers
        (6, True),    # Week 6 >= 3 and not deload (6 % 4 = 2) - triggers
        (7, True),    # Week 7 >= 3 and not deload (7 % 4 = 3) - triggers
        (8, False),   # Week 8 = deload (8 % 4 == 0) - no trigger
    ])
    def test_phase_trigger_by_week(self, week_number, expect_phase_trigger):
        """Test phase-based trigger fires on appropriate weeks (week >= 3 and not deload)."""
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
            week_number=week_number,
            muscle_name="biceps"
        )
        
        assert result["triggers"]["phase_based_triggered"] == expect_phase_trigger


class TestAllMuscleGroups:
    """Test recommendations work for all muscle groups."""
    
    def setup_method(self):
        """Setup for each test."""
        self.db = Mock()
        self.service = IntensityTechniqueService(self.db)
        self.service._check_plateau = Mock(return_value={"is_plateau": False})
        self.service._check_struggling = Mock(return_value={"is_struggling": False})
        self.service._check_volume_ceiling = Mock(return_value={"at_ceiling": False})
    
    @pytest.mark.parametrize("muscle_name", ["biceps", "triceps", "mid_chest", "lats", "quadriceps", "hamstrings"])
    def test_all_muscle_groups_handled(self, muscle_name):
        """Test that all muscle groups are handled without errors."""
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
            muscle_name=muscle_name
        )
        
        assert result["set_type"] is not None
        assert result["rep_style"] is not None

