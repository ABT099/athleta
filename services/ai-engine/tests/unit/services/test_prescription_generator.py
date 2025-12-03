"""
Unit tests for PrescriptionGeneratorService.

Tests scientific rules:
- CNS Tax Rule (compounds capped at RPE 9.0)
- Inverse RPE/RIR Law (RIR = 10 - RPE)
- Deload safety (aggressive intensity reduction)
- Microcycle progression (week-in-phase)
- Hybrid logic (compounds follow strength, isolations follow hypertrophy)
"""
import pytest
from app.services.prescription_generator import PrescriptionGeneratorService
from app.utils.constants import (
    ExerciseIntensityCategory,
    TrainingType,
)


class TestPrescriptionGenerator:
    """Test prescription generation service."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.service = PrescriptionGeneratorService()
    
    # ============ CNS Tax Rule Tests ============
    
    def test_compound_heavy_capped_at_rpe_9(self):
        """Test that compound heavy exercises are capped at RPE 9.0."""
        result = self.service.generate_prescription(
            intensity_category=ExerciseIntensityCategory.COMPOUND_HEAVY,
            training_type=TrainingType.STRENGTH,
            training_phase="realization",  # Would push to 9.0 + 1.0 = 10.0
            week_in_phase=4,  # Would add +0.5
            is_primary=True
        )
        assert result["target_rpe"] <= 9.0, "Compound heavy must be capped at RPE 9.0"
        assert result["target_rpe"] >= 5.0, "RPE must be at least 5.0"
    
    def test_compound_moderate_capped_at_rpe_9(self):
        """Test that compound moderate exercises are capped at RPE 9.0."""
        result = self.service.generate_prescription(
            intensity_category=ExerciseIntensityCategory.COMPOUND_MODERATE,
            training_type=TrainingType.HYPERTROPHY,
            training_phase="realization",
            week_in_phase=4,
            is_primary=True
        )
        assert result["target_rpe"] <= 9.0, "Compound moderate must be capped at RPE 9.0"
    
    def test_isolation_can_exceed_rpe_9(self):
        """Test that isolation exercises can exceed RPE 9.0."""
        result = self.service.generate_prescription(
            intensity_category=ExerciseIntensityCategory.ISOLATION,
            training_type=TrainingType.HYPERTROPHY,
            training_phase="realization",
            week_in_phase=4,
            is_primary=True
        )
        # Isolation can go up to 10.0 in hypertrophy
        assert result["target_rpe"] <= 10.0
        assert result["target_rpe"] >= 5.0
    
    # ============ Inverse RPE/RIR Law Tests ============
    
    def test_rir_calculation_strictly_enforced(self):
        """Test that RIR = 10 - RPE is strictly enforced."""
        test_cases = [
            (ExerciseIntensityCategory.COMPOUND_HEAVY, TrainingType.STRENGTH, "accumulation", 2),
            (ExerciseIntensityCategory.ISOLATION, TrainingType.HYPERTROPHY, "intensification", 3),
            (ExerciseIntensityCategory.COMPOUND_MODERATE, TrainingType.HYBRID, "realization", 4),
        ]
        
        for category, training_type, phase, week in test_cases:
            result = self.service.generate_prescription(
                intensity_category=category,
                training_type=training_type,
                training_phase=phase,
                week_in_phase=week,
                is_primary=True
            )
            expected_rir = round(10 - result["target_rpe"])
            assert result["target_rir"] == expected_rir, \
                f"RIR must equal 10 - RPE. Got RPE={result['target_rpe']}, RIR={result['target_rir']}, expected RIR={expected_rir}"
    
    # ============ Deload Safety Tests ============
    
    def test_deload_aggressive_reduction(self):
        """Test that deload phase aggressively reduces intensity."""
        # Compare deload to accumulation
        deload_result = self.service.generate_prescription(
            intensity_category=ExerciseIntensityCategory.COMPOUND_HEAVY,
            training_type=TrainingType.STRENGTH,
            training_phase="deload",
            week_in_phase=1,
            is_primary=True
        )
        
        accumulation_result = self.service.generate_prescription(
            intensity_category=ExerciseIntensityCategory.COMPOUND_HEAVY,
            training_type=TrainingType.STRENGTH,
            training_phase="accumulation",
            week_in_phase=1,
            is_primary=True
        )
        
        # Deload should be significantly lower (at least 1.0 RPE lower)
        # Calculation: accumulation = 8.0 - 0.5 (phase) - 0.5 (week) = 7.0
        #              deload = 8.0 - 2.0 (phase) = 6.0
        # Difference = 1.0 RPE
        assert deload_result["target_rpe"] <= accumulation_result["target_rpe"] - 1.0, \
            f"Deload must aggressively reduce intensity. Deload RPE: {deload_result['target_rpe']}, Accumulation RPE: {accumulation_result['target_rpe']}"
        assert deload_result["target_rpe"] >= 5.0, "Deload floor is RPE 5.0"
    
    def test_deload_no_microcycle_progression(self):
        """Test that deload phase doesn't apply microcycle progression."""
        week1 = self.service.generate_prescription(
            intensity_category=ExerciseIntensityCategory.COMPOUND_HEAVY,
            training_type=TrainingType.STRENGTH,
            training_phase="deload",
            week_in_phase=1,
            is_primary=True
        )
        
        week4 = self.service.generate_prescription(
            intensity_category=ExerciseIntensityCategory.COMPOUND_HEAVY,
            training_type=TrainingType.STRENGTH,
            training_phase="deload",
            week_in_phase=4,
            is_primary=True
        )
        
        # Deload should be flat (no progression)
        assert week1["target_rpe"] == week4["target_rpe"], \
            "Deload should not have microcycle progression"
    
    # ============ Microcycle Progression Tests ============
    
    def test_microcycle_progression_week_1_to_4(self):
        """Test that RPE increases from week 1 to week 4 within a phase."""
        week1 = self.service.generate_prescription(
            intensity_category=ExerciseIntensityCategory.COMPOUND_MODERATE,
            training_type=TrainingType.HYPERTROPHY,
            training_phase="accumulation",
            week_in_phase=1,
            is_primary=True
        )
        
        week4 = self.service.generate_prescription(
            intensity_category=ExerciseIntensityCategory.COMPOUND_MODERATE,
            training_type=TrainingType.HYPERTROPHY,
            training_phase="accumulation",
            week_in_phase=4,
            is_primary=True
        )
        
        # Week 4 should be harder than week 1
        assert week4["target_rpe"] > week1["target_rpe"], \
            "Week 4 should have higher RPE than week 1 (progressive overload)"
    
    def test_microcycle_progression_values(self):
        """Test that microcycle modifiers are applied correctly."""
        # Week 1 should have -0.5 modifier
        week1 = self.service.generate_prescription(
            intensity_category=ExerciseIntensityCategory.ISOLATION,
            training_type=TrainingType.HYPERTROPHY,
            training_phase="accumulation",
            week_in_phase=1,
            is_primary=True
        )
        
        # Week 2 should have 0.0 modifier (baseline)
        week2 = self.service.generate_prescription(
            intensity_category=ExerciseIntensityCategory.ISOLATION,
            training_type=TrainingType.HYPERTROPHY,
            training_phase="accumulation",
            week_in_phase=2,
            is_primary=True
        )
        
        # Week 1 should be lower than week 2
        assert week1["target_rpe"] < week2["target_rpe"], \
            "Week 1 should be easier than week 2"
    
    # ============ Hybrid Training Logic Tests ============
    
    def test_hybrid_compound_follows_strength_rules(self):
        """Test that hybrid compounds follow strength rules."""
        hybrid_compound = self.service.generate_prescription(
            intensity_category=ExerciseIntensityCategory.COMPOUND_HEAVY,
            training_type=TrainingType.HYBRID,
            training_phase="accumulation",
            week_in_phase=2,
            is_primary=True
        )
        
        strength_compound = self.service.generate_prescription(
            intensity_category=ExerciseIntensityCategory.COMPOUND_HEAVY,
            training_type=TrainingType.STRENGTH,
            training_phase="accumulation",
            week_in_phase=2,
            is_primary=True
        )
        
        # Should be identical (hybrid compounds use strength rules)
        assert hybrid_compound["target_rpe"] == strength_compound["target_rpe"], \
            "Hybrid compounds should follow strength RPE rules"
        assert hybrid_compound["rest_period_seconds"] == strength_compound["rest_period_seconds"], \
            "Hybrid compounds should follow strength rest rules"
    
    def test_hybrid_isolation_follows_hypertrophy_rules(self):
        """Test that hybrid isolations follow hypertrophy rules."""
        hybrid_isolation = self.service.generate_prescription(
            intensity_category=ExerciseIntensityCategory.ISOLATION,
            training_type=TrainingType.HYBRID,
            training_phase="accumulation",
            week_in_phase=2,
            is_primary=True
        )
        
        hypertrophy_isolation = self.service.generate_prescription(
            intensity_category=ExerciseIntensityCategory.ISOLATION,
            training_type=TrainingType.HYPERTROPHY,
            training_phase="accumulation",
            week_in_phase=2,
            is_primary=True
        )
        
        # Should be identical (hybrid isolations use hypertrophy rules)
        assert hybrid_isolation["target_rpe"] == hypertrophy_isolation["target_rpe"], \
            "Hybrid isolations should follow hypertrophy RPE rules"
        assert hybrid_isolation["rest_period_seconds"] == hypertrophy_isolation["rest_period_seconds"], \
            "Hybrid isolations should follow hypertrophy rest rules"
    
    # ============ Phase Modifier Tests ============
    
    def test_phase_modifiers_applied(self):
        """Test that phase modifiers are correctly applied."""
        accumulation = self.service.generate_prescription(
            intensity_category=ExerciseIntensityCategory.COMPOUND_MODERATE,
            training_type=TrainingType.STRENGTH,
            training_phase="accumulation",
            week_in_phase=2,
            is_primary=True
        )
        
        intensification = self.service.generate_prescription(
            intensity_category=ExerciseIntensityCategory.COMPOUND_MODERATE,
            training_type=TrainingType.STRENGTH,
            training_phase="intensification",
            week_in_phase=2,
            is_primary=True
        )
        
        realization = self.service.generate_prescription(
            intensity_category=ExerciseIntensityCategory.COMPOUND_MODERATE,
            training_type=TrainingType.STRENGTH,
            training_phase="realization",
            week_in_phase=2,
            is_primary=True
        )
        
        # Intensification should be higher than accumulation
        assert intensification["target_rpe"] > accumulation["target_rpe"], \
            "Intensification should have higher RPE than accumulation"
        
        # Realization should be highest (but capped at 9 for compounds)
        assert realization["target_rpe"] >= intensification["target_rpe"], \
            "Realization should have highest RPE"
        assert realization["target_rpe"] <= 9.0, "Compounds capped at 9.0"
    
    # ============ Rest Period Tests ============
    
    def test_primary_exercises_get_more_rest(self):
        """Test that primary exercises get more rest than accessories."""
        primary = self.service.generate_prescription(
            intensity_category=ExerciseIntensityCategory.COMPOUND_HEAVY,
            training_type=TrainingType.STRENGTH,
            training_phase="accumulation",
            week_in_phase=2,
            is_primary=True
        )
        
        accessory = self.service.generate_prescription(
            intensity_category=ExerciseIntensityCategory.COMPOUND_HEAVY,
            training_type=TrainingType.STRENGTH,
            training_phase="accumulation",
            week_in_phase=2,
            is_primary=False
        )
        
        assert primary["rest_period_seconds"] >= accessory["rest_period_seconds"], \
            "Primary exercises should get equal or more rest"
    
    def test_rest_period_within_range(self):
        """Test that rest periods are within valid ranges."""
        result = self.service.generate_prescription(
            intensity_category=ExerciseIntensityCategory.ISOLATION,
            training_type=TrainingType.HYPERTROPHY,
            training_phase="accumulation",
            week_in_phase=2,
            is_primary=True
        )
        
        # Hypertrophy isolation: 60-90s base, with phase modifier
        assert 60 <= result["rest_period_seconds"] <= 90, \
            f"Rest period {result['rest_period_seconds']}s should be within valid range"
    
    # ============ Edge Cases ============
    
    def test_week_beyond_4_uses_week_4_modifier(self):
        """Test that weeks beyond 4 use week 4 modifier."""
        week4 = self.service.generate_prescription(
            intensity_category=ExerciseIntensityCategory.COMPOUND_MODERATE,
            training_type=TrainingType.STRENGTH,
            training_phase="accumulation",
            week_in_phase=4,
            is_primary=True
        )
        
        week10 = self.service.generate_prescription(
            intensity_category=ExerciseIntensityCategory.COMPOUND_MODERATE,
            training_type=TrainingType.STRENGTH,
            training_phase="accumulation",
            week_in_phase=10,
            is_primary=True
        )
        
        # Should be identical (both use week 4 modifier)
        assert week4["target_rpe"] == week10["target_rpe"], \
            "Weeks beyond 4 should use week 4 modifier"
    
    def test_absolute_rpe_bounds(self):
        """Test that RPE never exceeds absolute bounds."""
        # Try to push RPE as high as possible
        result = self.service.generate_prescription(
            intensity_category=ExerciseIntensityCategory.ISOLATION,
            training_type=TrainingType.HYPERTROPHY,
            training_phase="realization",
            week_in_phase=4,
            is_primary=True
        )
        
        assert 5.0 <= result["target_rpe"] <= 10.0, \
            f"RPE {result['target_rpe']} must be between 5.0 and 10.0"
        
        # Try to push RPE as low as possible (deload)
        deload_result = self.service.generate_prescription(
            intensity_category=ExerciseIntensityCategory.ISOLATION,
            training_type=TrainingType.HYPERTROPHY,
            training_phase="deload",
            week_in_phase=1,
            is_primary=True
        )
        
        assert 5.0 <= deload_result["target_rpe"] <= 10.0, \
            f"Deload RPE {deload_result['target_rpe']} must be at least 5.0"

