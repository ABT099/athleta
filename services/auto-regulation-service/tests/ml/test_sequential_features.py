"""
Tests for Sequential Feature Engineering.
"""
import numpy as np
from unittest.mock import Mock
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from app.modules.ml.sequential_features import SequentialFeatureEngineer
from app.models import PerformanceTrend
from app.clients.api_client import AthleteDTO, RecoveryMetricsDTO
from app.modules.analysis import AnalysisContext
from tests.factories import WorkoutSessionFactory


def _ctx(recovery=None):
    athlete = AthleteDTO(id=1, age=30, gender="male", training_experience="intermediate",
                         rpe_calibration_factor=1.0, body_weight_kg=80.0)
    session = WorkoutSessionFactory.create(athlete_id=1, workout_day_id=1, sets=[])
    return AnalysisContext(
        athlete=athlete, plan=None, session=session, recovery=recovery, personal_records={},
        current_plan_entry=None, recent_performance_trends=[], exercise_progressions={},
        rpe_calibrations={}, form_trends={},
    )


class TestSequentialFeatureEngineer:
    def test_extract_sequence_features(self):
        db = Mock(spec=Session)

        trends = []
        for i in range(20):
            trend = Mock(spec=PerformanceTrend)
            trend.session_date = datetime.now(timezone.utc) - timedelta(days=20 - i)
            trend.total_volume = 1000 + i * 10
            trend.average_intensity = 0.7 + i * 0.01
            trend.average_rpe = 7.0 + i * 0.1
            trend.readiness_score = 0.8
            trend.performance_score = 0.75
            trend.fatigue_index = 0.3
            trends.append(trend)

        mock_trend_query = Mock()
        mock_trend_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = list(reversed(trends))
        db.query.return_value = mock_trend_query

        recovery = RecoveryMetricsDTO(
            id=1, athlete_id=1, date=datetime.now(timezone.utc), sleep_quality="good",
            sleep_hours=8.0, overall_soreness=3, stress_level=2, energy_level=7,
        )

        engineer = SequentialFeatureEngineer(db)
        sequence, feature_names = engineer.extract_sequence_features(_ctx(recovery), sequence_length=15)

        assert sequence is not None
        assert feature_names is not None
        assert sequence.shape[0] == 15
        assert len(feature_names) > 0

    def test_normalize_sequence(self):
        db = Mock(spec=Session)
        engineer = SequentialFeatureEngineer(db)
        sequence = np.random.rand(10, 15) * 100
        feature_names = [f"feature_{i}" for i in range(15)]
        normalized = engineer._normalize_sequence(athlete_id=1, sequence=sequence, feature_names=feature_names)
        assert normalized.shape == sequence.shape
        assert np.abs(np.mean(normalized)) < 1.0

    def test_prepare_sequential_dataset_insufficient_data(self):
        db = Mock(spec=Session)
        engineer = SequentialFeatureEngineer(db)
        history = Mock(athlete_id=1, performance_trends=[], recovery_history=[])
        X, y, feature_names, target_names = engineer.prepare_sequential_dataset(history, min_sessions=20)
        assert X is None
        assert y is None
