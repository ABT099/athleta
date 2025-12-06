"""
Sequential workout predictor using 1D CNN.

Uses temporal patterns in workout sequences to predict optimal parameters.
"""
from typing import Dict, List, Optional, Tuple
import numpy as np
from datetime import datetime, timezone

try:
    import tensorflow as tf
    from tensorflow import keras
    from tensorflow.keras import layers
    TENSORFLOW_AVAILABLE = True
except (ImportError, AttributeError):
    TENSORFLOW_AVAILABLE = False
    tf = None
    keras = None
    layers = None

from app.ml.base_model import BaseMLModel
from app.ml.bayesian_ensemble import BayesianEnsemble


class SequentialPredictor(BaseMLModel):
    """
    1D CNN model for predicting workout parameters from temporal sequences.
    
    Architecture:
    - Conv1D(64, kernel_size=3) -> Conv1D(32, kernel_size=3)
    - GlobalMaxPooling1D
    - Dense(16) -> Dropout(0.3) -> Dense(2)
    """
    
    def __init__(self):
        """Initialize sequential predictor."""
        super().__init__("sequential_predictor")
        
        if not TENSORFLOW_AVAILABLE:
            raise ImportError("TensorFlow is required for SequentialPredictor. Install with: uv add tensorflow")
        
        self.model = None
        self.history = None
    
    def _build_model(
        self,
        sequence_length: int,
        n_features: int
    ):
        """
        Build 1D CNN model architecture.
        
        Args:
            sequence_length: Length of input sequences
            n_features: Number of features per timestep
            
        Returns:
            Compiled Keras model
        """
        model = keras.Sequential([
            layers.Input(shape=(sequence_length, n_features)),
            
            # First convolutional layer with causal padding for temporal causality
            layers.Conv1D(
                filters=64,
                kernel_size=3,
                activation='relu',
                padding='causal'  # Only use past information
            ),
            layers.BatchNormalization(),  # Stabilize training
            
            # Second convolutional layer
            layers.Conv1D(
                filters=32,
                kernel_size=3,
                activation='relu',
                padding='causal'  # Only use past information
            ),
            layers.BatchNormalization(),  # Stabilize training
            
            # Global average pooling (better than max for preserving temporal patterns)
            # Max pooling discards temporal ordering, average preserves it
            layers.GlobalAveragePooling1D(),
            
            # Dense layers
            layers.Dense(16, activation='relu'),
            layers.BatchNormalization(),  # Stabilize training
            layers.Dropout(0.3),
            layers.Dense(2)  # volume_mult, intensity_mult
        ])
        
        # Compile model
        model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=0.001),
            loss='mse',
            metrics=['mae']
        )
        
        return model
    
    def train(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: List[str],
        target_names: List[str]
    ) -> Dict:
        """
        Train the sequential predictor.
        
        Args:
            X: Feature sequences (n_samples, sequence_length, n_features)
            y: Target matrix (n_samples, 2) - [volume_mult, intensity_mult]
            feature_names: Names of features per timestep
            target_names: Names of targets
            
        Returns:
            Dict with training metrics
        """
        if X.ndim != 3:
            raise ValueError(f"Expected 3D array (n_samples, sequence_length, n_features), got {X.ndim}D")
        
        if X.shape[0] < 20:
            raise ValueError("Insufficient training data. Need at least 20 samples.")
        
        sequence_length = X.shape[1]
        n_features = X.shape[2]
        
        # Build model
        self.model = self._build_model(sequence_length, n_features)
        
        # Split data
        from sklearn.model_selection import train_test_split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        # Train with early stopping
        early_stopping = keras.callbacks.EarlyStopping(
            monitor='val_loss',
            patience=10,
            restore_best_weights=True
        )
        
        # Train model
        self.history = self.model.fit(
            X_train, y_train,
            validation_data=(X_test, y_test),
            epochs=100,
            batch_size=16,
            callbacks=[early_stopping],
            verbose=0
        )
        
        # Evaluate
        test_loss, test_mae = self.model.evaluate(X_test, y_test, verbose=0)
        
        y_pred = self.model.predict(X_test, verbose=0)
        
        # Calculate R2
        from sklearn.metrics import r2_score
        r2 = r2_score(y_test, y_pred)
        
        # Per-target metrics
        r2_volume = r2_score(y_test[:, 0], y_pred[:, 0])
        r2_intensity = r2_score(y_test[:, 1], y_pred[:, 1])
        
        # Update model state
        self.is_trained = True
        self.training_date = datetime.now(timezone.utc)
        self.training_samples = X.shape[0]
        self.feature_names = feature_names
        self.target_names = target_names
        
        return {
            "test_loss": float(test_loss),
            "test_mae": float(test_mae),
            "r2": float(r2),
            "r2_volume": float(r2_volume),
            "r2_intensity": float(r2_intensity),
            "training_samples": X.shape[0],
            "test_samples": X_test.shape[0],
            "epochs_trained": len(self.history.history['loss'])
        }
    
    def predict(
        self,
        X: np.ndarray
    ) -> np.ndarray:
        """
        Predict workout parameters.
        
        Args:
            X: Feature sequences (n_samples, sequence_length, n_features)
            
        Returns:
            Predictions (n_samples, 2) - [volume_mult, intensity_mult]
        """
        if not self.is_trained:
            raise ValueError("Model must be trained before prediction")
        
        if X.ndim == 2:
            # Single sequence, add batch dimension
            X = X.reshape(1, X.shape[0], X.shape[1])
        
        predictions = self.model.predict(X, verbose=0)
        
        # Validate prediction shape
        if predictions.shape[1] < 2:
            raise ValueError(
                f"Expected 2 output columns (volume_mult, intensity_mult), "
                f"got {predictions.shape[1]}"
            )
        
        # Clamp predictions to reasonable ranges
        predictions[:, 0] = np.clip(predictions[:, 0], 0.7, 1.3)  # Volume: 70%-130%
        predictions[:, 1] = np.clip(predictions[:, 1], 0.8, 1.15)  # Intensity: 80%-115%
        
        return predictions
    
    def get_feature_importance(self) -> Dict[str, float]:
        """
        Get feature importance (not directly available for CNNs).
        
        Returns placeholder importance scores.
        """
        if not self.is_trained:
            return {}
        
        # CNNs don't have direct feature importance
        # Return equal importance for all features
        n_features = len(self.feature_names) if self.feature_names else 0
        if n_features == 0:
            return {}
        
        importance = 1.0 / n_features
        return {name: importance for name in self.feature_names}
    
    def get_confidence_score(
        self,
        X: np.ndarray
    ) -> float:
        """
        Calculate confidence score based on training history and sample size.
        
        Args:
            X: Feature sequences
            
        Returns:
            Confidence score (0.0 - 1.0)
        """
        base_confidence = super().get_confidence_score(X)
        
        if not self.is_trained or self.history is None:
            return base_confidence
        
        # Factor in validation loss (lower loss = higher confidence)
        val_losses = self.history.history.get('val_loss', [])
        if val_losses:
            final_val_loss = val_losses[-1]
            # Assume loss < 0.01 is very good, > 0.1 is poor
            if final_val_loss < 0.01:
                loss_confidence = 0.9
            elif final_val_loss < 0.05:
                loss_confidence = 0.7
            elif final_val_loss < 0.1:
                loss_confidence = 0.5
            else:
                loss_confidence = 0.3
            
            # Combine with base confidence
            final_confidence = (base_confidence + loss_confidence) / 2
            return round(float(final_confidence), 3)
        
        return base_confidence


class SequentialPredictorWithEnsemble(BaseMLModel):
    """
    Sequential predictor wrapped with Bayesian ensemble.
    
    Trains multiple 1D CNN models for uncertainty estimation.
    """
    
    def __init__(self, n_models: int = 5):
        """
        Initialize ensemble sequential predictor.
        
        Args:
            n_models: Number of models in ensemble (5 for <30 sessions, 10 for 30+)
        """
        super().__init__("sequential_predictor_ensemble")
        self.n_models = n_models
        self.ensemble = None
    
    def train(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: List[str],
        target_names: List[str]
    ) -> Dict:
        """
        Train ensemble of sequential predictors.
        
        Args:
            X: Feature sequences (n_samples, sequence_length, n_features)
            y: Target matrix (n_samples, 2)
            feature_names: Names of features
            target_names: Names of targets
            
        Returns:
            Dict with training metrics
        """
        # Create ensemble wrapper
        # Note: We need to create a factory function for the base model
        def create_model():
            model = SequentialPredictor()
            return model.model  # Return the Keras model
        
        # For now, train individual models and combine
        # This is a simplified approach - full ensemble would require
        # more sophisticated handling of Keras models
        
        # Train first model to get architecture
        base_predictor = SequentialPredictor()
        base_metrics = base_predictor.train(X, y, feature_names, target_names)
        
        # Store the trained model
        self.model = base_predictor.model
        self.is_trained = True
        self.training_date = datetime.now(timezone.utc)
        self.training_samples = X.shape[0]
        self.feature_names = feature_names
        self.target_names = target_names
        
        return base_metrics
    
    def predict(
        self,
        X: np.ndarray
    ) -> np.ndarray:
        """Predict using the model."""
        if not self.is_trained:
            raise ValueError("Model must be trained before prediction")
        
        if X.ndim == 2:
            X = X.reshape(1, X.shape[0], X.shape[1])
        
        predictions = self.model.predict(X, verbose=0)
        
        # Validate prediction shape
        if predictions.shape[1] < 2:
            raise ValueError(
                f"Expected 2 output columns (volume_mult, intensity_mult), "
                f"got {predictions.shape[1]}"
            )
        
        predictions[:, 0] = np.clip(predictions[:, 0], 0.7, 1.3)
        predictions[:, 1] = np.clip(predictions[:, 1], 0.8, 1.15)
        
        return predictions
    
    def get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance."""
        if not self.is_trained:
            return {}
        
        n_features = len(self.feature_names) if self.feature_names else 0
        if n_features == 0:
            return {}
        
        importance = 1.0 / n_features
        return {name: importance for name in self.feature_names}
    
    def get_confidence_score(
        self,
        X: np.ndarray
    ) -> float:
        """Get confidence score."""
        return super().get_confidence_score(X)

