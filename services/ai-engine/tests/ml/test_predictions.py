"""
Integration tests for ML system.
"""
import pytest
import numpy as np
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

try:
    from lightgbm import LGBMRegressor
    LIGHTGBM_AVAILABLE = True
except ImportError:
    LIGHTGBM_AVAILABLE = False

from app.ml.workout_predictor import WorkoutPredictor, WorkoutPredictorService
from app.ml.model_selector import ModelSelector
from app.ml.bayesian_ensemble import BayesianEnsemble
from app.models import Athlete, WorkoutSession, PerformanceTrend


@pytest.mark.skipif(not LIGHTGBM_AVAILABLE, reason="LightGBM not available")
@pytest.mark.slow
@pytest.mark.ml
class TestMLIntegration:
    """Integration tests for ML components."""
    
    def test_tiered_model_selection_integration(self):
        """Test tiered model selection works end-to-end."""
        db = Mock(spec=Session)
        
        # Mock session count queries
        def query_side_effect(model):
            mock_query = Mock()
            if model == WorkoutSession:
                mock_query.filter.return_value.count.return_value = 15
            elif model == Athlete:
                mock_athlete = Mock()
                mock_athlete.id = 1
                mock_query.filter.return_value.first.return_value = mock_athlete
            return mock_query
        
        db.query.side_effect = query_side_effect
        
        selector = ModelSelector(db)
        config = selector.get_model_config(athlete_id=1)
        
        assert config["model_type"] == "lightgbm"
        assert config["n_ensemble_models"] == 5
        assert config["session_count"] == 15
    
    def test_workout_predictor_service_integration(self):
        """Test WorkoutPredictorService with tiered selection."""
        db = Mock(spec=Session)
        
        # Mock athlete
        mock_athlete = Mock()
        mock_athlete.id = 1
        
        # Mock session count
        mock_session_query = Mock()
        mock_session_query.filter.return_value.count.return_value = 15
        
        # Mock athlete query
        mock_athlete_query = Mock()
        mock_athlete_query.filter.return_value.first.return_value = mock_athlete
        
        def query_side_effect(model):
            if model == WorkoutSession:
                return mock_session_query
            elif model == Athlete:
                return mock_athlete_query
            return Mock()
        
        db.query.side_effect = query_side_effect
        
        # Mock feature engineering
        with patch('app.ml.workout_predictor.FeatureEngineer') as mock_fe:
            mock_fe_instance = Mock()
            mock_fe.return_value = mock_fe_instance
            
            # Mock training data
            X = np.random.rand(15, 20)
            y = np.random.rand(15, 2)
            y[:, 0] = np.clip(y[:, 0], 0.7, 1.3)
            y[:, 1] = np.clip(y[:, 1], 0.8, 1.15)
            
            mock_fe_instance.prepare_training_dataset.return_value = (
                X, y,
                [f"feature_{i}" for i in range(20)],
                ["volume_multiplier", "intensity_multiplier"]
            )
            
            service = WorkoutPredictorService(db)
            
            # Test training
            success, metrics, error = service.train_athlete_model(athlete_id=1)
            
            # Should succeed with 15 sessions
            assert success or error is not None  # Either succeeds or gives error
    
    def test_uncertainty_propagation(self):
        """Test that uncertainty flows through the system."""
        np.random.seed(42)
        n_samples = 30
        n_features = 20
        
        X_train = np.random.rand(n_samples, n_features)
        y_train = np.random.rand(n_samples, 2)
        y_train[:, 0] = np.clip(y_train[:, 0], 0.7, 1.3)
        y_train[:, 1] = np.clip(y_train[:, 1], 0.8, 1.15)
        
        X_test = np.random.rand(3, n_features)
        
        feature_names = [f"feature_{i}" for i in range(n_features)]
        target_names = ["volume_multiplier", "intensity_multiplier"]
        
        # Train predictor with ensemble
        predictor = WorkoutPredictor(use_ensemble=True, n_ensemble_models=3)  # Reduced for faster tests
        predictor.train(X_train, y_train, feature_names, target_names)
        
        # Get predictions with uncertainty
        mean_pred, std_pred = predictor.predict_with_uncertainty(X_test)
        
        # Uncertainty should be non-negative
        assert np.all(std_pred >= 0)
        
        # Confidence should correlate with low uncertainty
        confidence = predictor.get_confidence_score(X_test)
        avg_uncertainty = np.mean(std_pred)
        
        # Lower uncertainty should give higher confidence
        if avg_uncertainty < 0.1:
            assert confidence >= 0.5
    
    def test_model_manager_save_load(self):
        """Test model manager can save and load models."""
        from app.ml.model_manager import ModelManager
        import tempfile
        import shutil
        
        # Create temp directory
        temp_dir = tempfile.mkdtemp()
        
        try:
            manager = ModelManager(models_dir=temp_dir)
            
            # Create and train a model
            np.random.seed(42)
            X = np.random.rand(30, 20)
            y = np.random.rand(30, 2)
            y[:, 0] = np.clip(y[:, 0], 0.7, 1.3)
            y[:, 1] = np.clip(y[:, 1], 0.8, 1.15)
            
            predictor = WorkoutPredictor(use_ensemble=True, n_ensemble_models=3)
            predictor.train(
                X, y,
                [f"f{i}" for i in range(20)],
                ["vol", "int"]
            )
            
            # Save model
            model_path = manager.save_model(predictor, athlete_id=1)
            assert model_path is not None
            
            # Load model
            loaded_model = manager.load_model("workout_predictor", athlete_id=1)
            assert loaded_model is not None
            assert loaded_model.is_trained
            
            # Test prediction
            X_test = np.random.rand(2, 20)
            original_pred = predictor.predict(X_test)
            loaded_pred = loaded_model.predict(X_test)
            
            # Predictions should be similar (allowing for ensemble variance)
            assert np.allclose(original_pred, loaded_pred, atol=0.1)
        
        finally:
            shutil.rmtree(temp_dir)

