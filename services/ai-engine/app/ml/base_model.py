"""
Base ML model abstract class.

Provides common interface for all ML models in the system.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
import numpy as np
from datetime import datetime


class BaseMLModel(ABC):
    """
    Abstract base class for ML models.
    
    All ML models should inherit from this class and implement
    the required methods.
    """
    
    def __init__(self, model_name: str):
        """
        Initialize base model.
        
        Args:
            model_name: Unique name for this model
        """
        self.model_name = model_name
        self.model = None
        self.is_trained = False
        self.training_date = None
        self.training_samples = 0
        self.feature_names = []
        self.target_names = []
    
    @abstractmethod
    def train(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: List[str],
        target_names: List[str]
    ) -> Dict[str, Any]:
        """
        Train the model.
        
        Args:
            X: Feature matrix (n_samples, n_features)
            y: Target matrix (n_samples, n_targets)
            feature_names: Names of features
            target_names: Names of targets
            
        Returns:
            Dict with training metrics
        """
        pass
    
    @abstractmethod
    def predict(
        self,
        X: np.ndarray
    ) -> np.ndarray:
        """
        Make predictions.
        
        Args:
            X: Feature matrix (n_samples, n_features)
            
        Returns:
            Predictions (n_samples, n_targets)
        """
        pass
    
    @abstractmethod
    def get_feature_importance(self) -> Dict[str, float]:
        """
        Get feature importance scores.
        
        Returns:
            Dict mapping feature names to importance scores
        """
        pass
    
    def get_confidence_score(
        self,
        X: np.ndarray
    ) -> float:
        """
        Calculate confidence score for predictions.
        
        Default implementation based on training sample size.
        Override for model-specific confidence metrics.
        
        Args:
            X: Feature matrix
            
        Returns:
            Confidence score (0.0 - 1.0)
        """
        if not self.is_trained:
            return 0.0
        
        # Base confidence on training sample size
        if self.training_samples < 20:
            return 0.0
        elif self.training_samples < 50:
            return 0.5
        elif self.training_samples < 100:
            return 0.7
        else:
            return 0.9
    
    def get_model_info(self) -> Dict:
        """
        Get model metadata.
        
        Returns:
            Dict with model information
        """
        return {
            "model_name": self.model_name,
            "is_trained": self.is_trained,
            "training_date": self.training_date.isoformat() if self.training_date else None,
            "training_samples": self.training_samples,
            "feature_count": len(self.feature_names),
            "target_count": len(self.target_names),
            "feature_names": self.feature_names,
            "target_names": self.target_names
        }
    
    def requires_retraining(
        self,
        new_samples_count: int,
        retrain_threshold: int = 50
    ) -> bool:
        """
        Determine if model needs retraining.
        
        Args:
            new_samples_count: Number of new samples since last training
            retrain_threshold: Retrain after this many new samples
            
        Returns:
            True if retraining recommended
        """
        if not self.is_trained:
            return True
        
        if new_samples_count >= retrain_threshold:
            return True
        
        # Check if model is old (>90 days)
        if self.training_date:
            days_since_training = (datetime.utcnow() - self.training_date).days
            if days_since_training > 90:
                return True
        
        return False

