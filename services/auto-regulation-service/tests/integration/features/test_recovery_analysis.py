"""
Tests for refined gender and age-based recovery adjustments.

Tests the nuanced approach to gender recovery modifiers and age-based progression,
including training age considerations.
"""
import pytest
from autoregulation.services.recovery_analyzer import RecoveryAnalyzer
from autoregulation.utils.constants import Gender, TrainingExperience


@pytest.mark.integration
@pytest.mark.slow
class TestGenderRecoveryModifiers:
    """Test gender-based recovery modifier calculations."""
    
    def test_male_baseline(self):
        """Test that males get baseline modifier."""
        modifier = RecoveryAnalyzer.calculate_gender_recovery_modifier(
            Gender.MALE, age=30
        )
        assert modifier == 1.0
    
    def test_female_fatigue_resistance(self):
        """Test that females show greater fatigue resistance."""
        modifier = RecoveryAnalyzer.calculate_gender_recovery_modifier(
            Gender.FEMALE, age=30
        )
        # Should be ~1.08 (8% greater fatigue resistance)
        assert 1.05 <= modifier <= 1.10
    
    def test_gender_with_age_interaction(self):
        """Test gender modifier combined with age."""
        young_female = RecoveryAnalyzer.calculate_gender_recovery_modifier(
            Gender.FEMALE, age=22
        )
        older_female = RecoveryAnalyzer.calculate_gender_recovery_modifier(
            Gender.FEMALE, age=50
        )
        
        # Young female should have higher modifier
        assert young_female > older_female
    
    def test_individual_variability_note(self):
        """Test that modifiers are within reasonable range (emphasizing individual variability)."""
        # Test various combinations
        modifiers = []
        for gender in [Gender.MALE, Gender.FEMALE]:
            for age in [20, 30, 40, 50, 60]:
                modifier = RecoveryAnalyzer.calculate_gender_recovery_modifier(
                    gender, age
                )
                modifiers.append(modifier)
                # All should be in reasonable range (0.7 - 1.2)
                assert 0.7 <= modifier <= 1.2
        
        # Modifiers should show variation but not extreme differences
        # (emphasizing that individual variability is large)
        assert max(modifiers) - min(modifiers) < 0.5


@pytest.mark.integration
@pytest.mark.slow
class TestAgeProgressionModifiers:
    """Test age-based progression modifier calculations."""
    
    def test_age_brackets(self):
        """Test that age brackets return appropriate modifiers."""
        # Young athletes
        young = RecoveryAnalyzer.calculate_age_progression_modifier(22)
        assert young >= 1.0
        
        # Middle age baseline
        middle = RecoveryAnalyzer.calculate_age_progression_modifier(30)
        assert middle == 1.0
        
        # Older athletes
        older = RecoveryAnalyzer.calculate_age_progression_modifier(50)
        assert older < 1.0
        assert older >= 0.7  # Softer than before
    
    def test_training_age_offset(self):
        """Test that training age can offset chronological age decline."""
        # 50-year-old with no training experience
        no_training = RecoveryAnalyzer.calculate_age_progression_modifier(
            age=50, training_age_years=0
        )
        
        # 50-year-old with 10 years training
        experienced = RecoveryAnalyzer.calculate_age_progression_modifier(
            age=50, training_age_years=10
        )
        
        # Experienced should be higher (can offset age penalty)
        assert experienced > no_training
    
    def test_well_trained_older_athlete(self):
        """Test that well-trained older athletes can progress similar to younger novices."""
        # 55-year-old with 15 years training
        experienced_older = RecoveryAnalyzer.calculate_age_progression_modifier(
            age=55, training_age_years=15
        )
        
        # 25-year-old beginner
        young_beginner = RecoveryAnalyzer.calculate_age_progression_modifier(
            age=25, training_age_years=0
        )
        
        # Experienced older athlete should be closer to young beginner
        # (well-trained older athletes may progress similar to younger novices)
        assert abs(experienced_older - young_beginner) < 0.3
    
    def test_softer_age_ranges(self):
        """Test that age ranges are softer than before."""
        # 45-year-old should have less severe penalty
        modifier_45 = RecoveryAnalyzer.calculate_age_progression_modifier(45)
        assert modifier_45 >= 0.85  # Softer than old 0.85
        
        # 60-year-old should have less severe penalty
        modifier_60 = RecoveryAnalyzer.calculate_age_progression_modifier(60)
        assert modifier_60 >= 0.65  # Softer than old 0.60
    
    def test_senior_masters_bracket(self):
        """Test new senior masters bracket (66+)."""
        senior = RecoveryAnalyzer.calculate_age_progression_modifier(70)
        assert 0.60 <= senior <= 0.70


@pytest.mark.integration
@pytest.mark.slow
class TestTrainingAgeEstimation:
    """Test training age estimation from experience level."""
    
    def test_beginner_estimation(self):
        """Test beginner training age estimation."""
        years = RecoveryAnalyzer.estimate_training_age_from_experience(
            TrainingExperience.BEGINNER
        )
        assert years == 0
    
    def test_intermediate_estimation(self):
        """Test intermediate training age estimation."""
        years = RecoveryAnalyzer.estimate_training_age_from_experience(
            TrainingExperience.INTERMEDIATE
        )
        assert years == 2
    
    def test_advanced_estimation(self):
        """Test advanced training age estimation."""
        years = RecoveryAnalyzer.estimate_training_age_from_experience(
            TrainingExperience.ADVANCED
        )
        assert years == 5


@pytest.mark.integration
@pytest.mark.slow
class TestCombinedGenderAgeModifiers:
    """Test combined gender and age modifier calculations."""
    
    def test_young_female_combined(self):
        """Test young female with training age."""
        modifier = RecoveryAnalyzer.calculate_gender_recovery_modifier(
            Gender.FEMALE, age=25, training_age_years=3
        )
        # Should combine gender boost with age boost
        assert modifier > 1.0
        assert modifier <= 1.2
    
    def test_older_male_experienced(self):
        """Test older experienced male."""
        modifier = RecoveryAnalyzer.calculate_gender_recovery_modifier(
            Gender.MALE, age=55, training_age_years=12
        )
        # Training age should offset some age decline
        assert modifier >= 0.7
        assert modifier <= 1.0
    
    def test_edge_cases(self):
        """Test edge cases and boundary conditions."""
        # Very young
        young = RecoveryAnalyzer.calculate_gender_recovery_modifier(
            Gender.MALE, age=18
        )
        assert 1.0 <= young <= 1.2
        
        # Very old
        old = RecoveryAnalyzer.calculate_gender_recovery_modifier(
            Gender.FEMALE, age=75
        )
        assert 0.7 <= old <= 1.0
        
        # High training age
        high_training = RecoveryAnalyzer.calculate_gender_recovery_modifier(
            Gender.MALE, age=50, training_age_years=20
        )
        assert 0.7 <= high_training <= 1.2


@pytest.mark.integration
@pytest.mark.slow
class TestIndividualVariabilityEmphasis:
    """Test that individual variability is emphasized in calculations."""
    
    def test_modifier_ranges_are_reasonable(self):
        """Test that all modifiers stay in reasonable ranges."""
        # Test many combinations
        for gender in [Gender.MALE, Gender.FEMALE]:
            for age in range(18, 80, 5):
                for training_years in [0, 2, 5, 10, 15]:
                    modifier = RecoveryAnalyzer.calculate_gender_recovery_modifier(
                        gender, age, training_years
                    )
                    # All should be in reasonable range
                    assert 0.7 <= modifier <= 1.2, \
                        f"Modifier {modifier} out of range for gender={gender}, age={age}, training={training_years}"
    
    def test_no_extreme_differences(self):
        """Test that differences between groups aren't extreme."""
        modifiers = []
        for gender in [Gender.MALE, Gender.FEMALE]:
            for age in [20, 30, 40, 50, 60]:
                modifier = RecoveryAnalyzer.calculate_gender_recovery_modifier(
                    gender, age
                )
                modifiers.append(modifier)
        
        # Range should be reasonable (not too extreme)
        # This emphasizes that individual variability is large
        assert max(modifiers) - min(modifiers) < 0.5

