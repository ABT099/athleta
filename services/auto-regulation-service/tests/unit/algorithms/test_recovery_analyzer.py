"""
Unit tests for recovery analyzer.
"""
import pytest
from app.modules.volume import RecoveryAnalyzer
from app.utils.constants import SleepQuality


class TestRecoveryAnalyzer:
    """Test suite for recovery analyzer."""
    
    def test_calculate_readiness_score_all_factors(self, db_session):
        """Test readiness score with all factors."""
        analyzer = RecoveryAnalyzer(db_session)
        
        # Perfect recovery scenario
        sleep_quality = SleepQuality.EXCELLENT
        sleep_hours = 8.0
        overall_soreness = 1  # No soreness
        stress_level = 2  # Low stress
        energy_level = 9  # High energy
        
        # Calculate readiness score
        readiness = analyzer.calculate_readiness_score(
            sleep_quality=sleep_quality,
            sleep_hours=sleep_hours,
            overall_soreness=overall_soreness,
            stress_level=stress_level,
            energy_level=energy_level
        )
        
        # Should give a high readiness score (>0.8)
        assert readiness > 0.8
        assert readiness <= 1.0
        
        # Poor recovery scenario
        poor_readiness = analyzer.calculate_readiness_score(
            sleep_quality=SleepQuality.POOR,
            sleep_hours=5.0,
            overall_soreness=8,  # High soreness
            stress_level=9,  # High stress
            energy_level=3  # Low energy
        )
        
        # Should give a low readiness score (<0.5)
        assert poor_readiness < 0.5
        assert poor_readiness >= 0.0
    
    def test_sleep_quality_multipliers(self):
        """Test sleep quality scoring."""
        from app.utils.constants import SLEEP_QUALITY_MULTIPLIERS
        
        # Verify sleep quality multipliers are correct
        assert SLEEP_QUALITY_MULTIPLIERS[SleepQuality.POOR] == 0.7
        assert SLEEP_QUALITY_MULTIPLIERS[SleepQuality.NOT_BAD] == 0.85
        assert SLEEP_QUALITY_MULTIPLIERS[SleepQuality.GOOD] == 0.95
        assert SLEEP_QUALITY_MULTIPLIERS[SleepQuality.EXCELLENT] == 1.0
    
    def test_recovery_recommendations_logic(self, db_session):
        """Test recovery recommendation generation logic."""
        analyzer = RecoveryAnalyzer(db_session)
        
        # Test low readiness recommendations
        readiness_low = 0.4
        recommendations_low = analyzer.get_recovery_recommendations(
            readiness_score=readiness_low,
            fatigue_level="high",
            sleep_quality=SleepQuality.POOR
        )
        
        # Should recommend rest or reduced training
        assert len(recommendations_low) > 0
        assert any("skip" in rec.lower() or "reduce" in rec.lower() for rec in recommendations_low)
        
        # Test high readiness
        readiness_high = 0.95
        recommendations_high = analyzer.get_recovery_recommendations(
            readiness_score=readiness_high,
            fatigue_level="low",
            sleep_quality=SleepQuality.EXCELLENT
        )
        
        # Should allow normal training or have positive recommendations
        assert len(recommendations_high) > 0
        # High readiness should not recommend skipping
        assert not any("skip" in rec.lower() for rec in recommendations_high)


