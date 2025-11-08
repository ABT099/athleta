"""
Workout parameter prediction using Machine Learning.

Predicts optimal volume and intensity multipliers based on athlete history.
"""
from typing import Dict, Optional, Tuple
import numpy as np
from datetime import datetime
from sqlalchemy.orm import Session

try:
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import mean_squared_error, r2_score
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    RandomForestRegressor = None

from app.ml.base_model import BaseMLModel
from app.ml.feature_engineering import FeatureEngineer
from app.ml.model_manager import ModelManager


class WorkoutPredictor(BaseMLModel):
    """
    ML model for predicting optimal workout parameters.
    
    Uses RandomForestRegressor to predict:
    - volume_multiplier (0.8 - 1.2)
    - intensity_multiplier (0.85 - 1.1)
    """
    
    def __init__(self):
        """Initialize workout predictor."""
        super().__init__("workout_predictor")
        
        if not SKLEARN_AVAILABLE:
            raise ImportError("scikit-learn is required for WorkoutPredictor. Install with: pip install scikit-learn")
        
        self.model = RandomForestRegressor(
            n_estimators=100,
            max_depth=10,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1
        )
    
    def train(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: list[str],
        target_names: list[str]
    ) -> Dict:
        """
        Train the workout predictor.
        
        Args:
            X: Feature matrix (n_samples, n_features)
            y: Target matrix (n_samples, 2) - [volume_mult, intensity_mult]
            feature_names: List of feature names
            target_names: List of target names
            
        Returns:
            Dict with training metrics
        """
        if X.shape[0] < 20:
            raise ValueError("Insufficient training data. Need at least 20 samples.")
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        # Train model
        self.model.fit(X_train, y_train)
        
        # Evaluate
        y_pred = self.model.predict(X_test)
        
        mse = mean_squared_error(y_test, y_pred)
        r2 = r2_score(y_test, y_pred)
        
        # Per-target metrics
        mse_volume = mean_squared_error(y_test[:, 0], y_pred[:, 0])
        mse_intensity = mean_squared_error(y_test[:, 1], y_pred[:, 1])
        r2_volume = r2_score(y_test[:, 0], y_pred[:, 0])
        r2_intensity = r2_score(y_test[:, 1], y_pred[:, 1])
        
        # Update model state
        self.is_trained = True
        self.training_date = datetime.utcnow()
        self.training_samples = X.shape[0]
        self.feature_names = feature_names
        self.target_names = target_names
        
        return {
            "overall_mse": float(mse),
            "overall_r2": float(r2),
            "volume_mse": float(mse_volume),
            "volume_r2": float(r2_volume),
            "intensity_mse": float(mse_intensity),
            "intensity_r2": float(r2_intensity),
            "training_samples": X.shape[0],
            "test_samples": X_test.shape[0]
        }
    
    def predict(
        self,
        X: np.ndarray
    ) -> np.ndarray:
        """
        Predict workout parameters.
        
        Args:
            X: Feature matrix (n_samples, n_features)
            
        Returns:
            Predictions (n_samples, 2) - [volume_mult, intensity_mult]
        """
        if not self.is_trained:
            raise ValueError("Model must be trained before prediction")
        
        predictions = self.model.predict(X)
        
        # Clamp predictions to reasonable ranges
        predictions[:, 0] = np.clip(predictions[:, 0], 0.7, 1.3)  # Volume: 70%-130%
        predictions[:, 1] = np.clip(predictions[:, 1], 0.8, 1.15)  # Intensity: 80%-115%
        
        return predictions
    
    def get_feature_importance(self) -> Dict[str, float]:
        """
        Get feature importance scores.
        
        Returns:
            Dict mapping feature names to importance scores
        """
        if not self.is_trained:
            return {}
        
        importances = self.model.feature_importances_
        
        return {
            name: float(importance)
            for name, importance in zip(self.feature_names, importances)
        }
    
    def get_confidence_score(
        self,
        X: np.ndarray
    ) -> float:
        """
        Calculate confidence score for predictions.
        
        Uses ensemble variance and training sample size.
        
        Args:
            X: Feature matrix
            
        Returns:
            Confidence score (0.0 - 1.0)
        """
        base_confidence = super().get_confidence_score(X)
        
        if not self.is_trained or base_confidence == 0.0:
            return 0.0
        
        # Get predictions from individual trees
        tree_predictions = np.array([tree.predict(X) for tree in self.model.estimators_])
        
        # Calculate variance across trees (lower variance = higher confidence)
        prediction_std = np.std(tree_predictions, axis=0)
        avg_std = np.mean(prediction_std)
        
        # Convert std to confidence (lower std = higher confidence)
        # Assume std of 0.1 is reasonable, anything above decreases confidence
        variance_confidence = np.exp(-avg_std / 0.1)
        
        # Combine with base confidence
        final_confidence = (base_confidence + variance_confidence) / 2
        
        return round(float(final_confidence), 3)


class WorkoutPredictorService:
    """
    Service for training and using workout prediction models.
    """
    
    def __init__(self, db: Session):
        """
        Initialize service.
        
        Args:
            db: Database session
        """
        self.db = db
        self.feature_engineer = FeatureEngineer(db)
        self.model_manager = ModelManager()
    
    def train_athlete_model(
        self,
        athlete_id: int,
        min_sessions: int = 20
    ) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        Train ML model for specific athlete.
        
        Args:
            athlete_id: Athlete ID
            min_sessions: Minimum sessions required
            
        Returns:
            Tuple of (success, metrics, error_message)
        """
        if not SKLEARN_AVAILABLE:
            return False, None, "scikit-learn not available"
        
        # Prepare training data
        X, y, feature_names, target_names = self.feature_engineer.prepare_training_dataset(
            athlete_id, min_sessions
        )
        
        if X is None:
            return False, None, f"Insufficient data. Need at least {min_sessions} sessions."
        
        # Train model
        try:
            predictor = WorkoutPredictor()
            metrics = predictor.train(X, y, feature_names, target_names)
            
            # Save model
            model_path = self.model_manager.save_model(predictor, athlete_id=athlete_id)
            
            metrics["model_path"] = model_path
            
            return True, metrics, None
        
        except Exception as e:
            return False, None, str(e)
    
    def predict_workout_parameters(
        self,
        athlete_id: int,
        fallback_to_rules: bool = True
    ) -> Tuple[Optional[Dict], str]:
        """
        Predict optimal workout parameters using ML model.
        
        Args:
            athlete_id: Athlete ID
            fallback_to_rules: If True, returns None on ML failure (caller should use rules)
            
        Returns:
            Tuple of (predictions_dict, source)
            - predictions_dict: {"volume_multiplier": float, "intensity_multiplier": float, "confidence": float}
            - source: "ml" or "insufficient_data"
        """
        if not SKLEARN_AVAILABLE:
            return None, "sklearn_unavailable"
        
        # Load model
        model = self.model_manager.load_model("workout_predictor", athlete_id=athlete_id)
        
        if model is None or not model.is_trained:
            return None, "model_not_trained"
        
        # Extract features
        features, feature_names = self.feature_engineer.extract_workout_features(athlete_id)
        
        if features is None:
            return None, "insufficient_data"
        
        # Predict
        try:
            X = features.reshape(1, -1)
            predictions = model.predict(X)[0]
            confidence = model.get_confidence_score(X)
            
            result = {
                "volume_multiplier": round(float(predictions[0]), 3),
                "intensity_multiplier": round(float(predictions[1]), 3),
                "confidence": confidence,
                "feature_importance": model.get_feature_importance()
            }
            
            return result, "ml"
        
        except Exception as e:
            print(f"ML prediction error: {e}")
            return None, "prediction_error"
    
    def should_retrain(
        self,
        athlete_id: int,
        new_sessions_threshold: int = 50
    ) -> bool:
        """
        Check if model should be retrained.
        
        Args:
            athlete_id: Athlete ID
            new_sessions_threshold: Retrain after this many new sessions
            
        Returns:
            True if retraining recommended
        """
        metadata = self.model_manager.get_model_metadata("workout_predictor", athlete_id)
        
        if not metadata:
            return True
        
        # Count sessions since last training
        training_date_str = metadata.get("training_date")
        if not training_date_str:
            return True
        
        training_date = datetime.fromisoformat(training_date_str)
        
        # Get session count since training date
        from app.models import WorkoutSession
        new_sessions = self.db.query(WorkoutSession).filter(
            WorkoutSession.athlete_id == athlete_id,
            WorkoutSession.session_date > training_date
        ).count()
        
        if new_sessions >= new_sessions_threshold:
            return True
        
        # Check if model is old (>90 days)
        days_since_training = (datetime.utcnow() - training_date).days
        if days_since_training > 90:
            return True
        
        return False

