"""
Feature scaler for normalization persistence.

Handles z-score normalization with persistent statistics for train/test consistency.
"""
from typing import Dict, List, Tuple, Optional
import numpy as np
import json


class FeatureScaler:
    """
    Z-score feature scaler with persistent statistics.
    
    Computes mean and std on training data, applies to test data.
    """
    
    def __init__(self, feature_names: Optional[List[str]] = None):
        """
        Initialize feature scaler.
        
        Args:
            feature_names: Optional list of feature names
        """
        self.feature_names = feature_names or []
        self.means: Dict[int, float] = {}  # feature_idx -> mean
        self.stds: Dict[int, float] = {}   # feature_idx -> std
        self.is_fitted = False
    
    def fit(self, X: np.ndarray, feature_names: Optional[List[str]] = None):
        """
        Fit scaler on training data.
        
        Computes mean and std for each feature.
        
        Args:
            X: Training data (n_samples, n_features) or (n_samples, seq_len, n_features)
            feature_names: Optional feature names
        """
        if feature_names:
            self.feature_names = feature_names
        
        # Handle 2D (standard) and 3D (sequential) arrays
        if X.ndim == 2:
            # Standard features: (n_samples, n_features)
            for feat_idx in range(X.shape[1]):
                values = X[:, feat_idx]
                if np.std(values) > 0:
                    self.means[feat_idx] = float(np.mean(values))
                    self.stds[feat_idx] = float(np.std(values))
                else:
                    self.means[feat_idx] = 0.0
                    self.stds[feat_idx] = 1.0
        elif X.ndim == 3:
            # Sequential features: (n_samples, sequence_length, n_features)
            for feat_idx in range(X.shape[2]):
                # Flatten across all samples and timesteps
                values = X[:, :, feat_idx].flatten()
                if np.std(values) > 0:
                    self.means[feat_idx] = float(np.mean(values))
                    self.stds[feat_idx] = float(np.std(values))
                else:
                    self.means[feat_idx] = 0.0
                    self.stds[feat_idx] = 1.0
        else:
            raise ValueError(f"Expected 2D or 3D array, got {X.ndim}D")
        
        self.is_fitted = True
    
    def transform(self, X: np.ndarray) -> np.ndarray:
        """
        Transform data using fitted statistics.
        
        Args:
            X: Data to transform (n_samples, n_features) or (n_samples, seq_len, n_features)
            
        Returns:
            Normalized data
        """
        if not self.is_fitted:
            raise ValueError("Scaler must be fitted before transform")
        
        normalized = X.copy()
        
        if X.ndim == 2:
            # Standard features
            for feat_idx in range(X.shape[1]):
                if feat_idx in self.means:
                    mean_val = self.means[feat_idx]
                    std_val = self.stds[feat_idx]
                    normalized[:, feat_idx] = (X[:, feat_idx] - mean_val) / (std_val + 1e-8)
        elif X.ndim == 3:
            # Sequential features
            for feat_idx in range(X.shape[2]):
                if feat_idx in self.means:
                    mean_val = self.means[feat_idx]
                    std_val = self.stds[feat_idx]
                    normalized[:, :, feat_idx] = (X[:, :, feat_idx] - mean_val) / (std_val + 1e-8)
        else:
            raise ValueError(f"Expected 2D or 3D array, got {X.ndim}D")
        
        return normalized
    
    def fit_transform(self, X: np.ndarray, feature_names: Optional[List[str]] = None) -> np.ndarray:
        """
        Fit scaler and transform data.
        
        Args:
            X: Training data
            feature_names: Optional feature names
            
        Returns:
            Normalized data
        """
        self.fit(X, feature_names)
        return self.transform(X)
    
    def to_dict(self) -> Dict:
        """
        Serialize scaler to dictionary.
        
        Returns:
            Dictionary with scaler state
        """
        return {
            "feature_names": self.feature_names,
            "means": self.means,
            "stds": self.stds,
            "is_fitted": self.is_fitted
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "FeatureScaler":
        """
        Deserialize scaler from dictionary.
        
        Args:
            data: Dictionary with scaler state
            
        Returns:
            FeatureScaler instance
        """
        scaler = cls(feature_names=data.get("feature_names", []))
        scaler.means = {int(k): float(v) for k, v in data.get("means", {}).items()}
        scaler.stds = {int(k): float(v) for k, v in data.get("stds", {}).items()}
        scaler.is_fitted = data.get("is_fitted", False)
        return scaler
    
    def save(self, filepath: str):
        """
        Save scaler to JSON file.
        
        Args:
            filepath: Path to save file
        """
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
    
    @classmethod
    def load(cls, filepath: str) -> "FeatureScaler":
        """
        Load scaler from JSON file.
        
        Args:
            filepath: Path to load file
            
        Returns:
            FeatureScaler instance
        """
        with open(filepath, 'r') as f:
            data = json.load(f)
        return cls.from_dict(data)

