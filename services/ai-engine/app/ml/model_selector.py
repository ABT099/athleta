"""
Model selector for tiered model selection.

Selects appropriate model based on athlete's session count and data availability.
"""
from typing import Dict, Optional, Tuple
from sqlalchemy.orm import Session

from app.models import WorkoutSession


class ModelSelector:
    """
    Selects appropriate ML model based on athlete's data availability.
    
    Tiered approach:
    - 0-9 sessions: Rules only
    - 10-19 sessions: LightGBM ensemble (5 models)
    - 20+ sessions: Sequential CNN or LightGBM ensemble (10 models)
    """
    
    def __init__(self, db: Session):
        """
        Initialize model selector.
        
        Args:
            db: Database session
        """
        self.db = db
    
    def get_session_count(self, athlete_id: int) -> int:
        """
        Get number of completed sessions for athlete.
        
        Args:
            athlete_id: Athlete ID
            
        Returns:
            Number of completed sessions
        """
        count = self.db.query(WorkoutSession).filter(
            WorkoutSession.athlete_id == athlete_id
        ).count()
        
        return count
    
    def select_model_type(
        self,
        athlete_id: int
    ) -> Tuple[str, int, Dict]:
        """
        Select appropriate model type for athlete.
        
        Args:
            athlete_id: Athlete ID
            
        Returns:
            Tuple of (model_type, n_ensemble_models, config)
            - model_type: "rules_only", "lightgbm", "sequential"
            - n_ensemble_models: Number of models in ensemble (5 or 10)
            - config: Additional configuration dict
        """
        session_count = self.get_session_count(athlete_id)
        
        if session_count < 10:
            return "rules_only", 0, {}
        elif session_count < 30:
            # LightGBM with 5-model ensemble (<30 sessions)
            # Try sequential first for 20+ sessions, fallback to LightGBM
            try:
                from app.ml.sequential_predictor import SequentialPredictor
                from app.ml.sequential_features import SequentialFeatureEngineer
                SEQUENTIAL_AVAILABLE = True
            except ImportError:
                SEQUENTIAL_AVAILABLE = False
            
            if SEQUENTIAL_AVAILABLE and session_count >= 20:
                # Try sequential model with 5-model ensemble
                return "sequential", 5, {
                    "min_sessions": 20,
                    "use_ensemble": True,
                    "sequence_length": 15
                }
            else:
                # Fallback to LightGBM with 5-model ensemble
                # Use appropriate min_sessions: 20 for 20-29 sessions, 11 for 10-19 sessions
                # Note: min_sessions=11 (not 10) because shifted targets require 6 overhead
                # (5 history + 1 target), so 11 sessions produce 5 samples (11-6=5)
                fallback_min_sessions = 20 if session_count >= 20 else 11
                return "lightgbm", 5, {
                    "min_sessions": fallback_min_sessions,
                    "use_ensemble": True
                }
        else:
            # 30+ sessions: Use 10-model ensemble
            # Try sequential first, fallback to LightGBM
            try:
                from app.ml.sequential_predictor import SequentialPredictor
                from app.ml.sequential_features import SequentialFeatureEngineer
                SEQUENTIAL_AVAILABLE = True
            except ImportError:
                SEQUENTIAL_AVAILABLE = False
            
            if SEQUENTIAL_AVAILABLE:
                # Sequential model with 10-model ensemble
                return "sequential", 10, {
                    "min_sessions": 30,
                    "use_ensemble": True,
                    "sequence_length": 15
                }
            else:
                # Fallback to LightGBM with 10-model ensemble
                return "lightgbm", 10, {
                    "min_sessions": 30,
                    "use_ensemble": True
                }
    
    def should_use_sequential(
        self,
        athlete_id: int
    ) -> bool:
        """
        Determine if sequential model should be used.
        
        Args:
            athlete_id: Athlete ID
            
        Returns:
            True if sequential model should be used
        """
        model_type, _, _ = self.select_model_type(athlete_id)
        return model_type == "sequential"
    
    def get_model_config(
        self,
        athlete_id: int
    ) -> Dict:
        """
        Get complete model configuration for athlete.
        
        Args:
            athlete_id: Athlete ID
            
        Returns:
            Dict with model configuration
        """
        model_type, n_models, config = self.select_model_type(athlete_id)
        
        return {
            "model_type": model_type,
            "n_ensemble_models": n_models,
            "session_count": self.get_session_count(athlete_id),
            **config
        }

