"""
Workout parameter prediction using Machine Learning.

Predicts optimal volume and intensity multipliers based on athlete history.
"""
from typing import Dict, Optional, Tuple
import numpy as np
from datetime import datetime, timezone
from sqlalchemy.orm import Session

try:
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import mean_squared_error, r2_score
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

try:
    from lightgbm import LGBMRegressor
    LIGHTGBM_AVAILABLE = True
except ImportError:
    LIGHTGBM_AVAILABLE = False
    LGBMRegressor = None

from app.ml.base_model import BaseMLModel
from app.ml.feature_engineering import FeatureEngineer
from app.ml.model_manager import ModelManager
from app.ml.bayesian_ensemble import BayesianEnsemble
from app.ml.model_selector import ModelSelector
from app.ml.sequential_features import SequentialFeatureEngineer


class WorkoutPredictor(BaseMLModel):
    """
    ML model for predicting optimal workout parameters.
    
    Uses LightGBM with Bayesian ensemble to predict:
    - volume_multiplier (0.7 - 1.3)
    - intensity_multiplier (0.8 - 1.15)
    """
    
    def __init__(self, use_ensemble: bool = True, n_ensemble_models: int = 5):
        """
        Initialize workout predictor.
        
        Args:
            use_ensemble: Whether to use Bayesian ensemble
            n_ensemble_models: Number of models in ensemble (5 for <30 sessions, 10 for 30+)
        """
        super().__init__("workout_predictor")
        
        if not LIGHTGBM_AVAILABLE:
            raise ImportError("lightgbm is required for WorkoutPredictor. Install with: uv sync --extra ml")
        
        self.use_ensemble = use_ensemble
        self.n_ensemble_models = n_ensemble_models
        
        if use_ensemble:
            # Create Bayesian ensemble wrapper
            self.ensemble = BayesianEnsemble(
                base_model_class=LGBMRegressor,
                n_models=n_ensemble_models,
                model_kwargs={
                    'n_estimators': 100,
                    'learning_rate': 0.05,
                    'max_depth': 6,
                    'num_leaves': 31,
                    'min_child_samples': 5,
                    'subsample': 0.8,
                    'colsample_bytree': 0.8,
                    'n_jobs': -1
                }
            )
            self.model = None  # Ensemble handles models
        else:
            # Single model (for backward compatibility)
            self.model = LGBMRegressor(
                n_estimators=100,
                learning_rate=0.05,
                max_depth=6,
                num_leaves=31,
                min_child_samples=5,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=42,
                n_jobs=-1
            )
            self.ensemble = None
    
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
        
        if self.use_ensemble:
            # Train ensemble
            ensemble_metrics = self.ensemble.train(X_train, y_train, feature_names, target_names)
            
            # Evaluate on test set
            y_pred, _ = self.ensemble.predict_with_uncertainty(X_test)
            
            mse = mean_squared_error(y_test, y_pred)
            r2 = r2_score(y_test, y_pred)
            
            # Per-target metrics
            mse_volume = mean_squared_error(y_test[:, 0], y_pred[:, 0])
            mse_intensity = mean_squared_error(y_test[:, 1], y_pred[:, 1])
            r2_volume = r2_score(y_test[:, 0], y_pred[:, 0])
            r2_intensity = r2_score(y_test[:, 1], y_pred[:, 1])
            
            # Update model state
            self.is_trained = True
            self.training_date = datetime.now(timezone.utc)
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
                "test_samples": X_test.shape[0],
                "ensemble_size": self.n_ensemble_models
            }
        else:
            # Train single model
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
            self.training_date = datetime.now(timezone.utc)
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
        
        if self.use_ensemble:
            predictions = self.ensemble.predict(X)
        else:
            predictions = self.model.predict(X)
        
        # Ensure 2D array
        if predictions.ndim == 1:
            predictions = predictions.reshape(-1, 1)
        
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
        """
        if not self.is_trained:
            raise ValueError("Model must be trained before prediction")
        
        if self.use_ensemble:
            return self.ensemble.predict_with_uncertainty(X)
        else:
            # Single model - return predictions with zero uncertainty
            predictions = self.predict(X)
            std = np.zeros_like(predictions)
            return predictions, std
    
    def get_feature_importance(self) -> Dict[str, float]:
        """
        Get feature importance scores.
        
        Returns:
            Dict mapping feature names to importance scores
        """
        if not self.is_trained:
            return {}
        
        if self.use_ensemble:
            return self.ensemble.get_feature_importance()
        else:
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
        
        if self.use_ensemble:
            # Use ensemble's confidence calculation
            ensemble_confidence = self.ensemble.get_confidence_score(X)
            # Combine with base confidence
            final_confidence = (base_confidence + ensemble_confidence) / 2
            return round(float(final_confidence), 3)
        else:
            # Single model - use base confidence
            return base_confidence


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
        self.sequential_feature_engineer = SequentialFeatureEngineer(db)
        self.model_manager = ModelManager()
        self.model_selector = ModelSelector(db)
    
    def train_athlete_model(
        self,
        athlete_id: int,
        min_sessions: Optional[int] = None
    ) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        Train ML model for specific athlete using tiered selection.
        
        Args:
            athlete_id: Athlete ID
            min_sessions: Minimum sessions required (auto-determined if None)
            
        Returns:
            Tuple of (success, metrics, error_message)
        """
        if not LIGHTGBM_AVAILABLE:
            return False, None, "lightgbm not available"
        
        # Get model configuration based on session count
        config = self.model_selector.get_model_config(athlete_id)
        model_type = config["model_type"]
        n_ensemble_models = config["n_ensemble_models"]
        
        if model_type == "rules_only":
            return False, None, "Insufficient sessions for ML model. Need at least 10 sessions."
        
        # Determine minimum sessions
        if min_sessions is None:
            min_sessions = config.get("min_sessions", 10)
        
        # Train sequential model if selected
        if model_type == "sequential":
            try:
                from app.ml.sequential_predictor import SequentialPredictor
                
                # Prepare sequential training data
                X, y, feature_names, target_names = self.sequential_feature_engineer.prepare_sequential_dataset(
                    athlete_id, min_sessions, sequence_length=config.get("sequence_length", 15)
                )
                
                if X is None:
                    # Fallback to LightGBM if sequential data insufficient
                    # Preserve n_ensemble_models from model_selector config
                    model_type = "lightgbm"
                    X, y, feature_names, target_names = self.feature_engineer.prepare_training_dataset(
                        athlete_id, min_sessions
                    )
                else:
                    # Train sequential model
                    predictor = SequentialPredictor()
                    metrics = predictor.train(X, y, feature_names, target_names)
                    
                    # Attach scaler from feature engineer to model for persistence
                    scaler = self.sequential_feature_engineer.get_scaler(athlete_id)
                    if scaler:
                        predictor.scaler = scaler
                    
                    # Save model
                    model_path = self.model_manager.save_model(predictor, athlete_id=athlete_id)
                    
                    metrics["model_path"] = model_path
                    metrics["model_type"] = "sequential"
                    metrics["sequence_length"] = config.get("sequence_length", 15)
                    
                    return True, metrics, None
            except Exception as e:
                # Fallback to LightGBM on error
                # Preserve n_ensemble_models from model_selector config
                model_type = "lightgbm"
        
        # Train LightGBM model (default or fallback)
        if model_type == "lightgbm":
            # Prepare training data
            X, y, feature_names, target_names = self.feature_engineer.prepare_training_dataset(
                athlete_id, min_sessions
            )
            
            if X is None:
                return False, None, f"Insufficient data. Need at least {min_sessions} sessions."
            
            # Train model
            try:
                predictor = WorkoutPredictor(
                    use_ensemble=True,
                    n_ensemble_models=n_ensemble_models
                )
                metrics = predictor.train(X, y, feature_names, target_names)
                
                # Save model
                model_path = self.model_manager.save_model(predictor, athlete_id=athlete_id)
                
                metrics["model_path"] = model_path
                metrics["model_type"] = model_type
                metrics["n_ensemble_models"] = n_ensemble_models
                
                return True, metrics, None
                
            except Exception as e:
                return False, None, str(e)
        
        return False, None, f"Unknown model type: {model_type}"
    
    def predict_workout_parameters(
        self,
        athlete_id: int,
        fallback_to_rules: bool = True
    ) -> Tuple[Optional[Dict], str]:
        """
        Predict optimal workout parameters using ML model with tiered selection.
        
        Args:
            athlete_id: Athlete ID
            fallback_to_rules: If True, returns None on ML failure (caller should use rules)
            
        Returns:
            Tuple of (predictions_dict, source)
            - predictions_dict: {"volume_multiplier": float, "intensity_multiplier": float, "confidence": float, "uncertainty": float}
            - source: "ml", "insufficient_data", "model_not_trained"
        """
        if not LIGHTGBM_AVAILABLE:
            return None, "lightgbm_unavailable"
        
        # Check if athlete has enough sessions
        config = self.model_selector.get_model_config(athlete_id)
        if config["model_type"] == "rules_only":
            return None, "insufficient_sessions"
        
        # Load model
        model = self.model_manager.load_model("workout_predictor", athlete_id=athlete_id)
        
        if model is None or not model.is_trained:
            return None, "model_not_trained"
        
        # Check model type and extract appropriate features
        model_metadata = self.model_manager.get_model_metadata("workout_predictor", athlete_id=athlete_id)
        actual_model_type = model_metadata.get("model_type", "lightgbm") if model_metadata else config["model_type"]
        
        # Extract features based on model type
        if actual_model_type == "sequential":
            # Restore scaler to feature engineer if model has one
            if hasattr(model, 'scaler') and model.scaler is not None:
                self.sequential_feature_engineer.set_scaler(athlete_id, model.scaler)
            
            # Extract sequential features
            sequence, feature_names = self.sequential_feature_engineer.extract_sequence_features(
                athlete_id, sequence_length=config.get("sequence_length", 15)
            )
            
            if sequence is None:
                return None, "insufficient_data"
            
            X = sequence.reshape(1, sequence.shape[0], sequence.shape[1])
        else:
            # Extract standard features
            features, feature_names = self.feature_engineer.extract_workout_features(athlete_id)
            
            if features is None:
                return None, "insufficient_data"
            
            X = features.reshape(1, -1)
        
        # Predict
        try:
            # Get predictions with uncertainty if available
            if hasattr(model, 'predict_with_uncertainty'):
                predictions, uncertainty = model.predict_with_uncertainty(X)
                if predictions.ndim > 1:
                    predictions = predictions[0]
                avg_uncertainty = float(np.mean(uncertainty[0])) if uncertainty.ndim > 1 else float(uncertainty[0])
            else:
                predictions = model.predict(X)
                if predictions.ndim > 1:
                    predictions = predictions[0]
                avg_uncertainty = 0.0
            
            confidence = model.get_confidence_score(X)
            
            result = {
                "volume_multiplier": round(float(predictions[0]), 3),
                "intensity_multiplier": round(float(predictions[1]), 3),
                "confidence": confidence,
                "uncertainty": avg_uncertainty,
                "feature_importance": model.get_feature_importance(),
                "model_type": actual_model_type
            }
            
            return result, "ml"
        
        except Exception as e:
            print(f"ML prediction error: {e}")
            return None, "prediction_error"
    
    def should_retrain(
        self,
        athlete_id: int,
        new_sessions_threshold: int = 20
    ) -> bool:
        """
        Check if model should be retrained.
        
        Args:
            athlete_id: Athlete ID
            new_sessions_threshold: Retrain after this many new sessions (default: 20 ~= 1 mesocycle)
            
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
        
        # Check if model is old (>60 days) - catches breaks before severe detraining
        days_since_training = (datetime.now(timezone.utc) - training_date).days
        if days_since_training > 60:
            return True
        
        return False
    
    def check_mesocycle_complete(
        self,
        athlete_id: int,
        current_phase: str,
        previous_phase: Optional[str] = None
    ) -> bool:
        """
        Check if a mesocycle has been completed based on phase transition.
        
        A mesocycle is complete when transitioning from Realization to Accumulation.
        
        Args:
            athlete_id: Athlete ID
            current_phase: Current training phase
            previous_phase: Previous training phase (optional)
            
        Returns:
            True if mesocycle just completed
        """
        # Import here to avoid circular dependency
        from app.utils.constants import TrainingPhase
        
        # Mesocycle complete when transitioning from Realization to Accumulation
        if (previous_phase == TrainingPhase.REALIZATION.value and 
            current_phase == TrainingPhase.ACCUMULATION.value):
            return True
        
        return False

