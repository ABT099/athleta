"""
Bayesian Ensemble wrapper for uncertainty estimation.

Trains multiple models with different random seeds and provides
mean predictions with uncertainty estimates.
"""
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
from abc import ABC, abstractmethod
from sklearn.multioutput import MultiOutputRegressor


class BayesianEnsemble:
    """
    Wrapper that trains multiple models and provides uncertainty estimates.
    
    Uses ensemble variance as a proxy for prediction uncertainty.
    """
    
    def __init__(
        self,
        base_model_class,
        n_models: int = 5,
        model_kwargs: Optional[Dict] = None
    ):
        """
        Initialize Bayesian ensemble.
        
        Args:
            base_model_class: Class of the base model to ensemble
            n_models: Number of models in ensemble (5 for <30 sessions, 10 for 30+)
            model_kwargs: Keyword arguments to pass to each model
        """
        self.base_model_class = base_model_class
        self.n_models = n_models
        self.model_kwargs = model_kwargs or {}
        self.models: List[Any] = []
        self.is_trained = False
        self.feature_names: List[str] = []
        self.target_names: List[str] = []
    
    def train(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: List[str],
        target_names: List[str]
    ) -> Dict[str, Any]:
        """
        Train ensemble of models.
        
        Args:
            X: Feature matrix (n_samples, n_features)
            y: Target matrix (n_samples, n_targets)
            feature_names: Names of features
            target_names: Names of targets
            
        Returns:
            Dict with training metrics
        """
        self.feature_names = feature_names
        self.target_names = target_names
        self.models = []
        
        # Detect if multi-output regression is needed
        is_multi_output = y.ndim == 2 and y.shape[1] > 1
        
        # Train each model with different random seed
        for i in range(self.n_models):
            # Create model with unique random state
            model_kwargs = self.model_kwargs.copy()
            model_kwargs['random_state'] = 42 + i
            
            base_model = self.base_model_class(**model_kwargs)
            
            # Wrap with MultiOutputRegressor if needed
            if is_multi_output and hasattr(base_model, 'fit'):
                model = MultiOutputRegressor(base_model)
            else:
                model = base_model
            
            # Train model
            if hasattr(model, 'fit'):
                # Direct sklearn-style fit
                model.fit(X, y)
            elif hasattr(model, 'train'):
                # Custom train method
                model.train(X, y, feature_names, target_names)
            else:
                raise ValueError(f"Model {self.base_model_class} must have 'fit' or 'train' method")
            
            self.models.append(model)
        
        self.is_trained = True
        
        # Calculate ensemble metrics
        predictions = self._predict_all(X)
        mean_pred = np.mean(predictions, axis=0)
        
        # Calculate MSE on training data
        mse = np.mean((y - mean_pred) ** 2)
        
        # Calculate R2
        ss_res = np.sum((y - mean_pred) ** 2)
        ss_tot = np.sum((y - np.mean(y, axis=0)) ** 2)
        r2 = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
        
        return {
            "ensemble_size": self.n_models,
            "mse": float(mse),
            "r2": float(r2),
            "training_samples": X.shape[0]
        }
    
    def predict(
        self,
        X: np.ndarray
    ) -> np.ndarray:
        """
        Predict using ensemble mean.
        
        Args:
            X: Feature matrix (n_samples, n_features)
            
        Returns:
            Mean predictions (n_samples, n_targets)
        """
        if not self.is_trained:
            raise ValueError("Ensemble must be trained before prediction")
        
        predictions = self._predict_all(X)
        return np.mean(predictions, axis=0)
    
    def predict_with_uncertainty(
        self,
        X: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Predict with uncertainty estimates.
        
        Args:
            X: Feature matrix (n_samples, n_features)
            
        Returns:
            Tuple of (mean_predictions, std_predictions)
            - mean_predictions: (n_samples, n_targets)
            - std_predictions: (n_samples, n_targets)
        """
        if not self.is_trained:
            raise ValueError("Ensemble must be trained before prediction")
        
        predictions = self._predict_all(X)
        mean_pred = np.mean(predictions, axis=0)
        std_pred = np.std(predictions, axis=0)
        
        return mean_pred, std_pred
    
    def get_confidence_score(
        self,
        X: np.ndarray
    ) -> float:
        """
        Calculate confidence score based on prediction variance.
        
        Lower variance = higher confidence.
        
        Args:
            X: Feature matrix
            
        Returns:
            Confidence score (0.0 - 1.0)
        """
        if not self.is_trained:
            return 0.0
        
        _, std_pred = self.predict_with_uncertainty(X)
        
        # Average std across all predictions
        avg_std = np.mean(std_pred)
        
        # Convert std to confidence
        # Lower std = higher confidence
        # Assume std of 0.05 is very confident, std of 0.2 is low confidence
        if avg_std < 0.05:
            confidence = 0.9
        elif avg_std < 0.1:
            confidence = 0.7
        elif avg_std < 0.15:
            confidence = 0.5
        else:
            confidence = 0.3
        
        return round(float(confidence), 3)
    
    def get_feature_importance(self) -> Dict[str, float]:
        """
        Get average feature importance across ensemble.
        
        Returns:
            Dict mapping feature names to average importance scores
        """
        if not self.is_trained or not self.models:
            return {}
        
        # Get importance from each model
        importances_list = []
        for model in self.models:
            # Handle MultiOutputRegressor wrapper
            actual_model = model.estimators_[0] if hasattr(model, 'estimators_') else model
            
            if hasattr(actual_model, 'feature_importances_'):
                importances_list.append(actual_model.feature_importances_)
            elif hasattr(actual_model, 'get_feature_importance'):
                imp_dict = actual_model.get_feature_importance()
                importances_list.append([imp_dict.get(name, 0.0) for name in self.feature_names])
        
        if not importances_list:
            return {}
        
        # Average across models
        avg_importances = np.mean(importances_list, axis=0)
        
        # Normalize to [0, 1] range
        total_importance = np.sum(avg_importances)
        if total_importance > 0:
            avg_importances = avg_importances / total_importance
        
        return {
            name: float(importance)
            for name, importance in zip(self.feature_names, avg_importances)
        }
    
    def _predict_all(
        self,
        X: np.ndarray
    ) -> np.ndarray:
        """
        Get predictions from all models in ensemble.
        
        Args:
            X: Feature matrix (n_samples, n_features)
            
        Returns:
            Predictions array (n_models, n_samples, n_targets)
        """
        predictions = []
        for model in self.models:
            if hasattr(model, 'predict'):
                pred = model.predict(X)
            else:
                raise ValueError(f"Model {type(model)} must have 'predict' method")
            
            # Ensure 2D array
            if pred.ndim == 1:
                pred = pred.reshape(-1, 1)
            
            predictions.append(pred)
        
        return np.array(predictions)

