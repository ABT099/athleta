"""
ML Model Management API endpoints.

Endpoints for training, managing, and monitoring ML models.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict, Optional
from datetime import datetime

from app.database import get_db
from app.models import Athlete, WorkoutSession
from app.ml.model_selector import ModelSelector
from app.ml.model_manager import ModelManager

# Import ML services with graceful degradation
try:
    from app.ml.workout_predictor import WorkoutPredictorService
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    WorkoutPredictorService = None


router = APIRouter()


@router.post("/ml/train/{athlete_id}")
def train_athlete_model(
    athlete_id: int,
    db: Session = Depends(get_db)
):
    """
    Train ML model for specific athlete.
    
    Uses tiered model selection:
    - 10-19 sessions: LightGBM ensemble (5 models)
    - 20+ sessions: LightGBM ensemble (10 models)
    
    Returns training metrics and model information.
    """
    if not ML_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ML services not available. Install lightgbm and tensorflow."
        )
    
    # Validate athlete exists
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    if not athlete:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Athlete {athlete_id} not found"
        )
    
    # Get session count
    session_count = db.query(WorkoutSession).filter(
        WorkoutSession.athlete_id == athlete_id
    ).count()
    
    if session_count < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient sessions for ML training. Need at least 10 sessions, have {session_count}"
        )
    
    # Train model
    predictor_service = WorkoutPredictorService(db)
    success, metrics, error = predictor_service.train_athlete_model(athlete_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error or "Failed to train model"
        )
    
    return {
        "athlete_id": athlete_id,
        "status": "success",
        "session_count": session_count,
        "training_metrics": metrics,
        "trained_at": datetime.utcnow().isoformat()
    }


@router.get("/ml/status/{athlete_id}")
def get_model_status(
    athlete_id: int,
    db: Session = Depends(get_db)
):
    """
    Get ML model status and information for an athlete.
    
    Returns:
    - Model availability and training status
    - Session count and model tier
    - Model metrics if trained
    - Feature importance if available
    """
    if not ML_AVAILABLE:
        return {
            "ml_available": False,
            "message": "ML services not available"
        }
    
    # Validate athlete exists
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    if not athlete:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Athlete {athlete_id} not found"
        )
    
    # Get session count
    session_count = db.query(WorkoutSession).filter(
        WorkoutSession.athlete_id == athlete_id
    ).count()
    
    # Get model selector config
    model_selector = ModelSelector(db)
    config = model_selector.get_model_config(athlete_id)
    
    # Get model metadata
    model_manager = ModelManager()
    metadata = model_manager.get_model_metadata("workout_predictor", athlete_id=athlete_id)
    
    # Try to get predictions for feature importance
    predictor_service = WorkoutPredictorService(db)
    predictions, source = predictor_service.predict_workout_parameters(
        athlete_id, fallback_to_rules=False
    )
    
    result = {
        "athlete_id": athlete_id,
        "ml_available": True,
        "session_count": session_count,
        "model_config": config,
        "model_trained": metadata is not None,
        "can_train": config["model_type"] != "rules_only"
    }
    
    if metadata:
        result["model_metadata"] = {
            "training_date": metadata.get("training_date"),
            "training_samples": metadata.get("training_samples"),
            "model_type": metadata.get("model_type", "lightgbm"),
            "version": metadata.get("version")
        }
    
    if predictions:
        result["current_predictions"] = {
            "volume_multiplier": predictions.get("volume_multiplier"),
            "intensity_multiplier": predictions.get("intensity_multiplier"),
            "confidence": predictions.get("confidence"),
            "uncertainty": predictions.get("uncertainty"),
            "model_type": predictions.get("model_type")
        }
        
        if predictions.get("feature_importance"):
            result["feature_importance"] = predictions["feature_importance"]
    
    return result


@router.post("/ml/retrain/{athlete_id}")
def retrain_athlete_model(
    athlete_id: int,
    force: bool = False,
    db: Session = Depends(get_db)
):
    """
    Force retrain ML model for athlete.
    
    Args:
        athlete_id: Athlete ID
        force: If True, retrain even if model is recent
    
    Returns training metrics.
    """
    if not ML_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ML services not available"
        )
    
    # Validate athlete exists
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    if not athlete:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Athlete {athlete_id} not found"
        )
    
    # Check if retraining is needed
    predictor_service = WorkoutPredictorService(db)
    
    if not force:
        should_retrain = predictor_service.should_retrain(athlete_id)
        if not should_retrain:
            return {
                "athlete_id": athlete_id,
                "status": "skipped",
                "message": "Model is up to date. Use force=true to retrain anyway."
            }
    
    # Train model
    success, metrics, error = predictor_service.train_athlete_model(athlete_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error or "Failed to retrain model"
        )
    
    return {
        "athlete_id": athlete_id,
        "status": "success",
        "message": "Model retrained successfully",
        "training_metrics": metrics,
        "retrained_at": datetime.utcnow().isoformat()
    }


@router.get("/ml/predictions/{athlete_id}")
def get_predictions_breakdown(
    athlete_id: int,
    db: Session = Depends(get_db)
):
    """
    Get detailed prediction breakdown with uncertainty.
    
    Returns:
    - ML predictions (volume/intensity multipliers)
    - Confidence and uncertainty scores
    - Feature importance
    - Model type and tier
    - Comparison with rule-based predictions
    """
    if not ML_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ML services not available"
        )
    
    # Validate athlete exists
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    if not athlete:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Athlete {athlete_id} not found"
        )
    
    # Get ML predictions
    predictor_service = WorkoutPredictorService(db)
    ml_predictions, ml_source = predictor_service.predict_workout_parameters(
        athlete_id, fallback_to_rules=False
    )
    
    # Get rule-based predictions for comparison
    from app.services.progressive_overload_engine import ProgressiveOverloadEngine
    engine = ProgressiveOverloadEngine(db)
    
    plan_context = engine.analyze_plan_context(athlete_id)
    performance = {"total_volume": 0, "average_intensity": 0}  # Simplified
    recovery = {"readiness_score": 0.7}  # Simplified
    injury_risk = {"risk_level": "low"}
    
    rule_adjustments = engine.calculate_next_workout_parameters(
        athlete, plan_context, performance, recovery, injury_risk
    )
    
    result = {
        "athlete_id": athlete_id,
        "ml_predictions": ml_predictions,
        "ml_source": ml_source,
        "rule_based_predictions": {
            "volume_multiplier": rule_adjustments.get("volume_multiplier"),
            "intensity_multiplier": rule_adjustments.get("intensity_multiplier"),
            "reasoning": rule_adjustments.get("reasoning")
        }
    }
    
    # Add comparison if both available
    if ml_predictions and rule_adjustments:
        result["comparison"] = {
            "volume_difference": ml_predictions["volume_multiplier"] - rule_adjustments.get("volume_multiplier", 1.0),
            "intensity_difference": ml_predictions["intensity_multiplier"] - rule_adjustments.get("intensity_multiplier", 1.0)
        }
    
    return result


@router.get("/ml/models")
def list_all_models(
    athlete_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    List all trained models.
    
    Args:
        athlete_id: Optional filter by athlete ID
    
    Returns list of model metadata.
    """
    if not ML_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ML services not available"
        )
    
    model_manager = ModelManager()
    models = model_manager.list_models(athlete_id=athlete_id)
    
    return {
        "models": models,
        "count": len(models)
    }


@router.delete("/ml/models/{athlete_id}")
def delete_athlete_models(
    athlete_id: int,
    keep_latest: int = 1,
    db: Session = Depends(get_db)
):
    """
    Delete old model versions for an athlete.
    
    Args:
        athlete_id: Athlete ID
        keep_latest: Number of latest versions to keep
    
    Returns number of models deleted.
    """
    if not ML_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ML services not available"
        )
    
    # Validate athlete exists
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    if not athlete:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Athlete {athlete_id} not found"
        )
    
    model_manager = ModelManager()
    deleted = model_manager.delete_old_models(
        "workout_predictor",
        athlete_id=athlete_id,
        keep_latest=keep_latest
    )
    
    return {
        "athlete_id": athlete_id,
        "deleted_count": deleted,
        "kept_latest": keep_latest
    }


@router.post("/ml/generate-synthetic-data")
def generate_synthetic_data(
    n_athletes: int = 50,
    sessions_per_athlete: int = 50,
    db: Session = Depends(get_db)
):
    """
    Generate synthetic data for testing ML models.
    
    WARNING: This will create new athletes and sessions in the database.
    Use only in development/testing environments.
    
    Args:
        n_athletes: Number of athletes to generate
        sessions_per_athlete: Sessions per athlete
    
    Returns summary of generated data.
    """
    try:
        from app.ml.synthetic_data_generator import SyntheticDataGenerator
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Synthetic data generator not available"
        )
    
    generator = SyntheticDataGenerator(db)
    
    try:
        summary = generator.generate_complete_dataset(
            n_athletes=n_athletes,
            sessions_per_athlete=sessions_per_athlete
        )
        
        return {
            "status": "success",
            "summary": summary,
            "message": f"Generated {summary['athletes_created']} athletes with {summary['sessions_created']} total sessions"
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating synthetic data: {str(e)}"
        )

