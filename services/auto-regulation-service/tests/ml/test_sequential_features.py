"""
Tests for Sequential Feature Engineering.
"""
import pytest
import numpy as np
from unittest.mock import Mock, MagicMock
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from autoregulation.ml.sequential_features import SequentialFeatureEngineer
from autoregulation.models import PerformanceTrend, RecoveryMetrics
from autoregulation.utils.constants import SleepQuality


class TestSequentialFeatureEngineer:
    """Test sequential feature extraction."""
    
    def test_extract_sequence_features(self):
        """Test sequence feature extraction."""
        db = Mock(spec=Session)
        
        # Mock athlete
        mock_athlete = Mock()
        mock_athlete.id = 1
        mock_athlete.age = 30
        
        # Mock performance trends
        trends = []
        for i in range(20):
            trend = Mock(spec=PerformanceTrend)
            trend.session_date = datetime.now() - timedelta(days=20-i)
            trend.total_volume = 1000 + i * 10
            trend.average_intensity = 0.7 + i * 0.01
            trend.average_rpe = 7.0 + i * 0.1
            trend.readiness_score = 0.8
            trend.performance_score = 0.75
            trend.fatigue_index = 0.3
            trends.append(trend)
        
        # Mock recovery metrics
        recovery = Mock(spec=RecoveryMetrics)
        recovery.sleep_hours = 8.0
        recovery.sleep_quality = SleepQuality.GOOD
        recovery.soreness_level = 3.0
        recovery.stress_level = 2.0
        recovery.energy_level = 7.0
        
        # Setup query mocks
        mock_trend_query = Mock()
        mock_trend_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = list(reversed(trends))
        
        mock_recovery_query = Mock()
        mock_recovery_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [recovery] * 20
        
        def query_side_effect(model):
            if model == PerformanceTrend:
                return mock_trend_query
            elif model == RecoveryMetrics:
                return mock_recovery_query
            elif model.__name__ == 'Athlete':
                mock_athlete_query = Mock()
                mock_athlete_query.filter.return_value.first.return_value = mock_athlete
                return mock_athlete_query
            return Mock()
        
        db.query.side_effect = query_side_effect
        
        engineer = SequentialFeatureEngineer(db)
        sequence, feature_names = engineer.extract_sequence_features(
            athlete_id=1,
            sequence_length=15
        )
        
        # Should return sequence array
        assert sequence is not None
        assert feature_names is not None
        assert sequence.shape[0] == 15  # sequence_length
        assert len(feature_names) > 0
    
    def test_normalize_sequence(self):
        """Test sequence normalization."""
        db = Mock(spec=Session)
        engineer = SequentialFeatureEngineer(db)
        
        # Create test sequence
        sequence = np.random.rand(10, 15) * 100
        
        feature_names = [f"feature_{i}" for i in range(15)]
        
        normalized = engineer._normalize_sequence(
            athlete_id=1,
            sequence=sequence,
            feature_names=feature_names
        )
        
        assert normalized.shape == sequence.shape
        # Check that normalization was applied (mean should be close to 0)
        assert np.abs(np.mean(normalized)) < 1.0
    
    def test_prepare_sequential_dataset_insufficient_data(self):
        """Test dataset preparation with insufficient data."""
        db = Mock(spec=Session)
        
        # Mock insufficient sessions
        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.all.return_value = []
        
        db.query.return_value = mock_query
        
        engineer = SequentialFeatureEngineer(db)
        result = engineer.prepare_sequential_dataset(
            athlete_id=1,
            min_sessions=20
        )
        
        X, y, feature_names, target_names = result
        assert X is None
        assert y is None

