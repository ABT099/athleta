"""
Unit tests for training calculations.
"""
import pytest
from autoregulation.services.training_calculations import TrainingCalculations
from autoregulation.utils.constants import TrainingExperience, TrainingType, MuscleSize


class TestTrainingCalculations:
    """Test suite for training calculations."""
    
    def setup_method(self):
        """Setup for each test."""
        self.calc = TrainingCalculations()
    
    def test_estimate_1rm_epley(self):
        """Test 1RM estimation using Epley formula."""
        # Test case: 100kg x 5 reps
        result = self.calc.estimate_1rm_epley(100, 5)
        expected = 100 * (1 + 5/30)  # 116.67
        assert abs(result - expected) < 0.01
        
        # Test case: 1 rep should return the weight
        assert self.calc.estimate_1rm_epley(100, 1) == 100
    
    def test_estimate_1rm_brzycki(self):
        """Test 1RM estimation using Brzycki formula."""
        # Test case: 100kg x 5 reps
        result = self.calc.estimate_1rm_brzycki(100, 5)
        expected = 100 * (36 / (37 - 5))  # 112.5
        assert abs(result - expected) < 0.01
        
        # Test case: 1 rep should return the weight
        assert self.calc.estimate_1rm_brzycki(100, 1) == 100
    
    def test_estimate_1rm_average(self):
        """Test averaged 1RM estimation."""
        result = self.calc.estimate_1rm_average(100, 5)
        
        # Should be average of Epley and Brzycki
        epley = self.calc.estimate_1rm_epley(100, 5)
        brzycki = self.calc.estimate_1rm_brzycki(100, 5)
        expected = (epley + brzycki) / 2
        
        assert abs(result - expected) < 0.01
    
    def test_calculate_relative_intensity(self):
        """Test relative intensity calculation."""
        # Test case: 80kg with 100kg 1RM = 0.8 (80%)
        result = self.calc.calculate_relative_intensity(80, 100)
        assert result == 0.8
        
        # Test edge case: weight equals 1RM
        assert self.calc.calculate_relative_intensity(100, 100) == 1.0
        
        # Test edge case: zero 1RM
        assert self.calc.calculate_relative_intensity(80, 0) == 0.0
    
    def test_calculate_volume_load(self):
        """Test volume load calculation."""
        sets = [
            (100, 5),  # 500
            (100, 5),  # 500
            (100, 5),  # 500
        ]
        result = self.calc.calculate_volume_load(sets)
        assert result == 1500
        
        # Test empty sets
        assert self.calc.calculate_volume_load([]) == 0
    
    def test_rpe_to_rir_conversion(self):
        """Test RPE to RIR conversion."""
        assert self.calc.rpe_to_rir(10.0) == 0
        assert self.calc.rpe_to_rir(9.0) == 1
        assert self.calc.rpe_to_rir(8.0) == 2
        assert self.calc.rpe_to_rir(7.0) == 3
        assert self.calc.rpe_to_rir(6.0) == 4
        assert self.calc.rpe_to_rir(5.0) == 5
    
    def test_rir_to_rpe_conversion(self):
        """Test RIR to RPE conversion."""
        assert self.calc.rir_to_rpe(0) == 10.0
        assert self.calc.rir_to_rpe(1) == 9.0
        assert self.calc.rir_to_rpe(2) == 8.0
        assert self.calc.rir_to_rpe(3) == 7.0
    
    def test_calculate_acute_chronic_workload_ratio(self):
        """Test ACWR calculation."""
        recent_loads = [100, 100, 100, 100, 100, 100, 100]  # 7 days
        chronic_loads = [80] * 28  # 28 days
        
        result = self.calc.calculate_acute_chronic_workload_ratio(
            recent_loads, chronic_loads
        )
        
        expected = 100 / 80  # 1.25
        assert abs(result - expected) < 0.01
    
    def test_calculate_training_monotony(self):
        """Test training monotony calculation."""
        # Highly variable loads - low monotony
        variable_loads = [100, 50, 150, 75, 125]
        monotony_variable = self.calc.calculate_training_monotony(variable_loads)
        
        # Very similar loads - high monotony
        monotonous_loads = [100, 100, 100, 100, 100]
        monotony_high = self.calc.calculate_training_monotony(monotonous_loads)
        
        # Monotonous loads (std=0) should have high monotony (10.0)
        assert monotony_high == 10.0
        
        # Variable loads should have lower monotony
        assert monotony_high > monotony_variable
    
    def test_get_mev_mrv_for_experience(self):
        """Test MEV/MRV volume landmarks."""
        # Test beginner with large muscle
        result = self.calc.get_mev_mrv_for_experience(
            TrainingExperience.BEGINNER,
            MuscleSize.LARGE
        )
        
        assert "mev" in result
        assert "mav" in result
        assert "mrv" in result
        assert result["mev"] < result["mav"] < result["mrv"]
        
        # Advanced should have higher volumes than beginner
        advanced = self.calc.get_mev_mrv_for_experience(
            TrainingExperience.ADVANCED,
            MuscleSize.LARGE
        )
        
        assert advanced["mev"] > result["mev"]
        assert advanced["mrv"] > result["mrv"]
    
    def test_calculate_optimal_load_increase(self):
        """Test load increase calculation."""
        # Test: Current RPE too low (7), target RPE 8.5
        # Should increase weight
        result = self.calc.calculate_optimal_load_increase(
            current_rpe=7.0,
            target_rpe=8.5,
            current_weight=100,
            experience=TrainingExperience.INTERMEDIATE,
            training_type=TrainingType.STRENGTH
        )
        
        assert result > 100  # Should increase
        
        # Test: Current RPE too high (9.5), target RPE 8.5
        # Should decrease weight
        result = self.calc.calculate_optimal_load_increase(
            current_rpe=9.5,
            target_rpe=8.5,
            current_weight=100,
            experience=TrainingExperience.INTERMEDIATE,
            training_type=TrainingType.STRENGTH
        )
        
        assert result < 100  # Should decrease
    
    def test_calculate_deload_parameters(self):
        """Test deload parameter calculation."""
        result = self.calc.calculate_deload_parameters(
            normal_volume=1000,
            normal_intensity=0.8,
            deload_week=4
        )
        
        assert "volume_multiplier" in result
        assert "intensity_multiplier" in result
        assert result["volume_multiplier"] < 1.0
        assert result["intensity_multiplier"] < 1.0


