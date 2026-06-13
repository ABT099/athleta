"""
Tests for Bayesian Ensemble wrapper.
"""
import pytest
import numpy as np
from unittest.mock import Mock

try:
    from lightgbm import LGBMRegressor
    LIGHTGBM_AVAILABLE = True
except ImportError:
    LIGHTGBM_AVAILABLE = False
    LGBMRegressor = None

from autoregulation.ml.bayesian_ensemble import BayesianEnsemble


@pytest.mark.skipif(not LIGHTGBM_AVAILABLE, reason="LightGBM not available")
@pytest.mark.slow
@pytest.mark.ml
class TestBayesianEnsemble:
    """Test Bayesian ensemble functionality."""
    
    def test_ensemble_initialization(self):
        """Test ensemble can be initialized."""
        ensemble = BayesianEnsemble(
            base_model_class=LGBMRegressor,
            n_models=3,  # Reduced for faster tests
            model_kwargs={'n_estimators': 10, 'random_state': 42}
        )
        
        assert ensemble.n_models == 3
        assert ensemble.base_model_class == LGBMRegressor
        assert not ensemble.is_trained
    
    def test_ensemble_training(self):
        """Test ensemble training."""
        # Generate synthetic data
        np.random.seed(42)
        n_samples = 50
        n_features = 10
        
        X = np.random.rand(n_samples, n_features)
        y = np.random.rand(n_samples, 2)  # 2 targets
        
        feature_names = [f"feature_{i}" for i in range(n_features)]
        target_names = ["target_1", "target_2"]
        
        ensemble = BayesianEnsemble(
            base_model_class=LGBMRegressor,
            n_models=3,  # Reduced for faster tests
            model_kwargs={
                'n_estimators': 10,
                'random_state': 42,
                'verbose': -1
            }
        )
        
        metrics = ensemble.train(X, y, feature_names, target_names)
        
        assert ensemble.is_trained
        assert len(ensemble.models) == 3
        assert "ensemble_size" in metrics
        assert metrics["ensemble_size"] == 3
        assert "mse" in metrics
        assert "r2" in metrics
    
    def test_ensemble_prediction(self):
        """Test ensemble prediction."""
        # Generate synthetic data
        np.random.seed(42)
        n_samples = 50
        n_features = 10
        
        X_train = np.random.rand(n_samples, n_features)
        y_train = np.random.rand(n_samples, 2)
        X_test = np.random.rand(10, n_features)
        
        feature_names = [f"feature_{i}" for i in range(n_features)]
        target_names = ["target_1", "target_2"]
        
        ensemble = BayesianEnsemble(
            base_model_class=LGBMRegressor,
            n_models=3,  # Reduced for faster tests
            model_kwargs={
                'n_estimators': 10,
                'random_state': 42,
                'verbose': -1
            }
        )
        
        ensemble.train(X_train, y_train, feature_names, target_names)
        
        # Test mean prediction
        predictions = ensemble.predict(X_test)
        assert predictions.shape == (10, 2)
        
        # Test prediction with uncertainty
        mean_pred, std_pred = ensemble.predict_with_uncertainty(X_test)
        assert mean_pred.shape == (10, 2)
        assert std_pred.shape == (10, 2)
        assert np.all(std_pred >= 0)  # Uncertainty should be non-negative
    
    def test_confidence_score(self):
        """Test confidence score calculation."""
        np.random.seed(42)
        n_samples = 50
        n_features = 10
        
        X_train = np.random.rand(n_samples, n_features)
        y_train = np.random.rand(n_samples, 2)
        X_test = np.random.rand(5, n_features)
        
        feature_names = [f"feature_{i}" for i in range(n_features)]
        target_names = ["target_1", "target_2"]
        
        ensemble = BayesianEnsemble(
            base_model_class=LGBMRegressor,
            n_models=3,  # Reduced for faster tests
            model_kwargs={
                'n_estimators': 10,
                'random_state': 42,
                'verbose': -1
            }
        )
        
        ensemble.train(X_train, y_train, feature_names, target_names)
        
        confidence = ensemble.get_confidence_score(X_test)
        assert 0.0 <= confidence <= 1.0
    
    def test_feature_importance(self):
        """Test feature importance extraction."""
        np.random.seed(42)
        n_samples = 50
        n_features = 5
        
        X_train = np.random.rand(n_samples, n_features)
        y_train = np.random.rand(n_samples, 2)
        
        feature_names = [f"feature_{i}" for i in range(n_features)]
        target_names = ["target_1", "target_2"]
        
        ensemble = BayesianEnsemble(
            base_model_class=LGBMRegressor,
            n_models=3,
            model_kwargs={
                'n_estimators': 10,
                'random_state': 42,
                'verbose': -1
            }
        )
        
        ensemble.train(X_train, y_train, feature_names, target_names)
        
        importance = ensemble.get_feature_importance()
        assert len(importance) == n_features
        assert all(name in importance for name in feature_names)
        assert all(0 <= val <= 1 for val in importance.values())
    
    def test_adaptive_ensemble_size(self):
        """Test that ensemble size can be adjusted."""
        ensemble_3 = BayesianEnsemble(
            base_model_class=LGBMRegressor,
            n_models=3
        )
        assert ensemble_3.n_models == 3
        
        ensemble_5 = BayesianEnsemble(
            base_model_class=LGBMRegressor,
            n_models=5
        )
        assert ensemble_5.n_models == 5

