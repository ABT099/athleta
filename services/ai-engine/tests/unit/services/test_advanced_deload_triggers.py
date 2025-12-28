"""
Tests for enhanced autoregulated deload triggers.

Tests ACWR, HRV trends, and session RPE detection.
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from app.services.progressive_overload_engine import ProgressiveOverloadEngine
from app.services.training_calculations import TrainingCalculations


class TestACWRDeloadTrigger:
    """Test ACWR-based deload detection."""
    
    def test_acwr_above_threshold(self):
        """Test that ACWR > 1.5 triggers deload."""
        from app.services.progressive_overload_engine import ProgressiveOverloadEngine
        from unittest.mock import Mock
        
        db = Mock()
        engine = ProgressiveOverloadEngine(db)
        
        # Mock SQL aggregation results for ACWR calculation
        # Acute: sum=100, count=5 -> mean=20
        # Chronic: sum=200, count=20 -> mean=10
        # ACWR = 20/10 = 2.0 (above threshold)
        mock_acute_result = Mock()
        mock_acute_result.acute_sum = 100.0
        mock_acute_result.acute_count = 5
        
        mock_chronic_result = Mock()
        mock_chronic_result.chronic_sum = 200.0
        mock_chronic_result.chronic_count = 20
        
        # Mock the query chain: query().filter().first()
        # Need separate query chains for acute and chronic
        mock_acute_query = Mock()
        mock_acute_query.filter.return_value.first.return_value = mock_acute_result
        
        mock_chronic_query = Mock()
        mock_chronic_query.filter.return_value.first.return_value = mock_chronic_result
        
        # Return different query mocks for each call
        query_call_count = [0]
        def mock_query_side_effect(*args, **kwargs):
            query_call_count[0] += 1
            if query_call_count[0] == 1:
                return mock_acute_query
            else:
                return mock_chronic_query
        
        db.query.side_effect = mock_query_side_effect
        
        result = engine._check_acwr(athlete_id=1)
        assert result[0] is True
        assert "ACWR" in result[1]
        assert "exceeds" in result[1] or "high injury risk" in result[1]
    
    def test_acwr_in_safe_zone(self):
        """Test that ACWR in safe zone (0.8-1.3) doesn't trigger deload."""
        from app.services.progressive_overload_engine import ProgressiveOverloadEngine
        from unittest.mock import Mock
        
        db = Mock()
        engine = ProgressiveOverloadEngine(db)
        
        # Mock SQL aggregation results for ACWR calculation
        # Acute: sum=110, count=10 -> mean=11
        # Chronic: sum=100, count=10 -> mean=10
        # ACWR = 11/10 = 1.1 (in safe zone)
        mock_acute_result = Mock()
        mock_acute_result.acute_sum = 110.0
        mock_acute_result.acute_count = 10
        
        mock_chronic_result = Mock()
        mock_chronic_result.chronic_sum = 100.0
        mock_chronic_result.chronic_count = 10
        
        # Mock the query chain: query().filter().first()
        # Need separate query chains for acute and chronic
        mock_acute_query = Mock()
        mock_acute_query.filter.return_value.first.return_value = mock_acute_result
        
        mock_chronic_query = Mock()
        mock_chronic_query.filter.return_value.first.return_value = mock_chronic_result
        
        # Return different query mocks for each call
        query_call_count = [0]
        def mock_query_side_effect(*args, **kwargs):
            query_call_count[0] += 1
            if query_call_count[0] == 1:
                return mock_acute_query
            else:
                return mock_chronic_query
        
        db.query.side_effect = mock_query_side_effect
        
        result = engine._check_acwr(athlete_id=1)
        assert result[0] is False


class TestSessionRPEDeloadTrigger:
    """Test session RPE (sRPE) spike detection."""
    
    def test_srpe_spike_detection(self):
        """Test that sRPE spike (>20% increase) triggers deload."""
        from app.services.progressive_overload_engine import ProgressiveOverloadEngine
        from app.models import WorkoutSession
        from unittest.mock import Mock
        
        db = Mock()
        engine = ProgressiveOverloadEngine(db)
        
        # Create mock sessions - MOST RECENT FIRST (due to order_by desc)
        # Recent sessions: RPE 8.5 × 60 min = 510
        recent_session_1 = Mock(spec=WorkoutSession)
        recent_session_1.overall_rpe = 8.5
        recent_session_1.duration_minutes = 60
        
        recent_session_2 = Mock(spec=WorkoutSession)
        recent_session_2.overall_rpe = 8.5
        recent_session_2.duration_minutes = 60
        
        # Previous session: RPE 7 × 60 min = 420 (21% decrease from recent)
        prev_session = Mock(spec=WorkoutSession)
        prev_session.overall_rpe = 7.0
        prev_session.duration_minutes = 60
        
        # Order: most recent first
        mock_sessions = [recent_session_1, recent_session_2, prev_session]
        
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = mock_sessions
        
        result = engine._check_session_rpe_spike(athlete_id=1, lookback_sessions=3)
        assert result[0] is True
        assert "sRPE" in result[1] or "Session RPE" in result[1]
    
    def test_no_srpe_spike(self):
        """Test that normal sRPE doesn't trigger deload."""
        from app.services.progressive_overload_engine import ProgressiveOverloadEngine
        from app.models import WorkoutSession
        from unittest.mock import Mock
        
        db = Mock()
        engine = ProgressiveOverloadEngine(db)
        
        # Create mock sessions with stable sRPE
        mock_sessions = []
        for rpe in [7.0, 7.0, 7.2]:  # Small variation
            session = Mock(spec=WorkoutSession)
            session.overall_rpe = rpe
            session.duration_minutes = 60
            mock_sessions.append(session)
        
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = mock_sessions
        
        result = engine._check_session_rpe_spike(athlete_id=1, lookback_sessions=3)
        assert result[0] is False


class TestCombinedDeloadTriggers:
    """Test that multiple triggers work together."""
    
    def test_multiple_triggers_any_one_triggers(self):
        """Test that any single trigger can cause deload."""
        from app.services.progressive_overload_engine import ProgressiveOverloadEngine
        from app.models import PerformanceTrend
        from unittest.mock import Mock, patch
        
        db = Mock()
        engine = ProgressiveOverloadEngine(db)
        
        # Create mock performance trends with good metrics (no trigger on their own)
        mock_trends = []
        for i in range(6):
            trend = Mock(spec=PerformanceTrend)
            trend.performance_score = 0.8  # Stable performance
            trend.readiness_score = 0.7  # OK readiness
            trend.average_rpe = 7.0  # Stable RPE
            trend.total_volume = 10000  # Stable volume
            mock_trends.append(trend)
        
        # Mock PerformanceTrend query to return these trends
        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = mock_trends
        db.query.return_value = mock_query
        
        # Mock all individual deload checks to return False except ACWR
        with patch.object(engine, '_check_acwr', return_value=(True, "ACWR high")):
            with patch.object(engine, '_check_session_rpe_spike', return_value=(False, None)):
                # Even if other checks pass, ACWR should trigger deload
                result = engine.should_deload(
                    athlete_id=1,
                    current_readiness=0.7,
                    lookback_sessions=6
                )
                # Should return True due to ACWR
                assert result[0] is True
                assert "ACWR" in result[1]

