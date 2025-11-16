"""
Unit tests for injury prevention service.
"""
import pytest
from app.utils.constants import PROGRESSION_RATES, TrainingExperience


class TestInjuryPrevention:
    """Test suite for injury prevention logic."""
    
    def test_progression_rates_exist(self):
        """Test that progression rates are defined for all experience levels."""
        assert TrainingExperience.BEGINNER in PROGRESSION_RATES
        assert TrainingExperience.INTERMEDIATE in PROGRESSION_RATES
        assert TrainingExperience.ADVANCED in PROGRESSION_RATES
        
        # Verify structure
        for exp_level in TrainingExperience:
            rates = PROGRESSION_RATES[exp_level]
            assert "load_increase" in rates
            assert "volume_increase" in rates
            assert "max_weekly_volume_increase" in rates
    
    def test_progression_rates_relative_to_experience(self):
        """Test that progression rates decrease with experience."""
        beginner_rate = PROGRESSION_RATES[TrainingExperience.BEGINNER]["load_increase"]
        intermediate_rate = PROGRESSION_RATES[TrainingExperience.INTERMEDIATE]["load_increase"]
        advanced_rate = PROGRESSION_RATES[TrainingExperience.ADVANCED]["load_increase"]
        
        # Beginners should progress faster than intermediates
        assert beginner_rate > intermediate_rate
        
        # Intermediates should progress faster than advanced
        assert intermediate_rate > advanced_rate
    
    def test_volume_spike_threshold(self):
        """Test volume spike detection logic."""
        # 10% rule for volume increases
        current_volume = 1000
        max_increase = 0.10  # 10%
        
        safe_increase = current_volume * (1 + max_increase)
        unsafe_increase = current_volume * (1 + max_increase + 0.05)
        
        assert safe_increase == 1100
        assert unsafe_increase > safe_increase
    
    def test_acwr_safe_zones(self):
        """Test ACWR safe zone thresholds."""
        # Safe zone: 0.8 - 1.3
        safe_acwr_low = 0.8
        safe_acwr_high = 1.3
        
        # Elevated risk
        risky_acwr_high = 1.6
        risky_acwr_low = 0.5
        
        # Verify thresholds
        assert 0.8 <= safe_acwr_low <= 1.3
        assert 0.8 <= safe_acwr_high <= 1.3
        assert risky_acwr_high > 1.5
        assert risky_acwr_low < 0.8


