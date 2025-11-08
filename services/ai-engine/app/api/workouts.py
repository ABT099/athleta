"""
Workouts API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime
import json

from app.database import get_db
from app.models import (
    Athlete, WorkoutDay, WorkoutSession, ExerciseSet, 
    RecoveryMetrics, PlanEntry
)
from app.schemas.workout import (
    WorkoutCompletionRequest,
    WorkoutCompletionResponse,
    WorkoutSessionResponse,
    RecoveryMetricsResponse,
    NextWorkoutResponse,
    ExerciseSetResponse
)
from app.services.progressive_overload_engine import ProgressiveOverloadEngine
from app.services.plan_updater import PlanUpdaterService
from app.services.rpe_calibration import RPECalibrationService

# Import ML services with graceful degradation
try:
    from app.ml.workout_predictor import WorkoutPredictorService
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    WorkoutPredictorService = None


router = APIRouter()


@router.post("/workouts/complete", response_model=WorkoutCompletionResponse)
def complete_workout(
    request: WorkoutCompletionRequest,
    db: Session = Depends(get_db)
):
    """
    Main endpoint: Submit completed workout and receive next workout adjustments.
    
    This is the core API that processes workout data and returns AI-generated
    progressive overload recommendations.
    """
    # Validate athlete exists
    athlete = db.query(Athlete).filter(Athlete.id == request.athlete_id).first()
    if not athlete:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Athlete {request.athlete_id} not found"
        )
    
    # Validate workout day exists
    workout_day = db.query(WorkoutDay).filter(
        WorkoutDay.id == request.workout_day_id
    ).first()
    if not workout_day:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workout day {request.workout_day_id} not found"
        )
    
    # Create workout session
    workout_session = WorkoutSession(
        athlete_id=request.athlete_id,
        workout_day_id=request.workout_day_id,
        session_date=request.session_date,
        duration_minutes=request.duration_minutes,
        overall_rpe=request.overall_rpe,
        overall_feeling=request.overall_feeling,
        notes=request.notes
    )
    
    db.add(workout_session)
    db.flush()  # Get session ID
    
    # Create exercise sets
    total_volume = 0
    for set_data in request.exercise_sets:
        exercise_set = ExerciseSet(
            workout_session_id=workout_session.id,
            exercise_id=set_data.exercise_id,
            set_number=set_data.set_number,
            weight=set_data.weight,
            reps=set_data.reps,
            rpe=set_data.rpe,
            rir=set_data.rir,
            form_quality=set_data.form_quality,
            tempo_adherence=set_data.tempo_adherence,
            notes=set_data.notes
        )
        db.add(exercise_set)
        total_volume += set_data.weight * set_data.reps
    
    workout_session.total_volume = total_volume
    
    # Create recovery metrics
    recovery_metrics = RecoveryMetrics(
        athlete_id=request.athlete_id,
        date=request.session_date,
        sleep_quality=request.recovery_metrics.sleep_quality,
        sleep_hours=request.recovery_metrics.sleep_hours,
        overall_soreness=request.recovery_metrics.overall_soreness,
        muscle_soreness=json.dumps(request.recovery_metrics.muscle_soreness) if request.recovery_metrics.muscle_soreness else None,
        stress_level=request.recovery_metrics.stress_level,
        energy_level=request.recovery_metrics.energy_level,
        nutrition_adherence=request.recovery_metrics.nutrition_adherence,
        hydration_level=request.recovery_metrics.hydration_level,
        notes=request.recovery_metrics.notes
    )
    
    db.add(recovery_metrics)
    db.flush()
    
    # === AI PROCESSING ===
    # Initialize AI engine
    engine = ProgressiveOverloadEngine(db)
    
    # Prepare data for AI engine
    session_data = {
        "exercise_sets": [
            {
                "exercise_id": s.exercise_id,
                "set_number": s.set_number,
                "weight": s.weight,
                "reps": s.reps,
                "rpe": s.rpe,
                "rir": s.rir,
                "form_quality": s.form_quality
            }
            for s in request.exercise_sets
        ]
    }
    
    recovery_data = {
        "sleep_quality": request.recovery_metrics.sleep_quality,
        "sleep_hours": request.recovery_metrics.sleep_hours,
        "overall_soreness": request.recovery_metrics.overall_soreness,
        "stress_level": request.recovery_metrics.stress_level,
        "energy_level": request.recovery_metrics.energy_level,
        "muscle_soreness": request.recovery_metrics.muscle_soreness
    }
    
    # Process workout and get AI recommendations
    ai_result = engine.process_workout_completion(
        athlete_id=request.athlete_id,
        workout_day_id=request.workout_day_id,
        session_data=session_data,
        recovery_data=recovery_data
    )
    
    # Update recovery metrics with calculated readiness score
    recovery_metrics.readiness_score = ai_result["recovery_status"]["readiness_score"]
    
    # Update workout session with estimated fatigue
    workout_session.estimated_fatigue = ai_result["recovery_status"]["fatigue_status"]["fatigue_score"]
    
    # Commit all changes
    db.commit()
    db.refresh(workout_session)
    db.refresh(recovery_metrics)
    
    # Update plan entry if exists
    plan_context = ai_result["plan_context"]
    if plan_context.get("plan_entry_id"):
        plan_updater = PlanUpdaterService(db)
        plan_updater.update_plan_entry_after_workout(
            plan_entry_id=plan_context["plan_entry_id"],
            workout_session=workout_session,
            recovery_metrics=recovery_metrics,
            ai_adjustments=ai_result["adjustments"]
        )
    
    # Generate next workout
    plan_updater = PlanUpdaterService(db)
    next_workout = plan_updater.generate_next_workout(
        athlete_id=request.athlete_id,
        workout_day_id=request.workout_day_id,  # Could be next in rotation
        ai_adjustments=ai_result["adjustments"],
        injury_warnings=ai_result["injury_risk"]["warnings"],
        recovery_recommendations=ai_result["recovery_status"]["recommendations"]
    )
    
    # Build response
    return WorkoutCompletionResponse(
        workout_session=WorkoutSessionResponse.model_validate(workout_session),
        recovery_metrics=RecoveryMetricsResponse.model_validate(recovery_metrics),
        next_workout=NextWorkoutResponse(**next_workout),
        performance_analysis=ai_result["performance_analysis"],
        ai_insights=ai_result["ai_insights"]
    )


@router.get("/athletes/{athlete_id}/next-workout")
def get_next_workout(
    athlete_id: int,
    db: Session = Depends(get_db)
):
    """
    Get next scheduled workout with current parameters (without completing a workout).
    """
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    if not athlete:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Athlete {athlete_id} not found"
        )
    
    # Get plan context
    engine = ProgressiveOverloadEngine(db)
    plan_context = engine.analyze_plan_context(athlete_id)
    
    if not plan_context.get("has_plan"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active training plan found for this athlete"
        )
    
    # Get next workout day (simplified - take first workout day)
    from app.models import WorkoutPlan
    plan = db.query(WorkoutPlan).filter(
        WorkoutPlan.id == plan_context["plan_id"]
    ).first()
    
    if not plan or not plan.workout_days:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No workout days found in plan"
        )
    
    # Get the next workout day (simplified logic - in production would track which day is next)
    next_workout_day = plan.workout_days[0]
    
    # Use current multipliers from plan entry
    adjustments = {
        "volume_multiplier": plan_context.get("target_volume_multiplier", 1.0),
        "intensity_multiplier": plan_context.get("target_intensity_multiplier", 1.0),
        "reasoning": "Current plan parameters",
        "exercise_adjustments": plan_context.get("planned_adjustments", {})
    }
    
    # Generate workout with current parameters
    plan_updater = PlanUpdaterService(db)
    next_workout = plan_updater.generate_next_workout(
        athlete_id=athlete_id,
        workout_day_id=next_workout_day.id,
        ai_adjustments=adjustments,
        injury_warnings=[],
        recovery_recommendations=[]
    )
    
    return next_workout


@router.get("/workouts/sessions/{session_id}", response_model=dict)
def get_workout_session(
    session_id: int,
    db: Session = Depends(get_db)
):
    """
    Get details of a specific workout session.
    """
    session = db.query(WorkoutSession).filter(
        WorkoutSession.id == session_id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workout session {session_id} not found"
        )
    
    # Get exercise sets
    sets = [ExerciseSetResponse.model_validate(s) for s in session.exercise_sets]
    
    return {
        "session": WorkoutSessionResponse.model_validate(session),
        "exercise_sets": sets
    }


# =========================================
# NEW API ENDPOINTS FOR ADVANCED FEATURES
# =========================================

@router.get("/athletes/{athlete_id}/rpe-calibration")
def get_rpe_calibration_status(
    athlete_id: int,
    db: Session = Depends(get_db)
):
    """
    Get RPE calibration status for an athlete.
    
    Returns calibration accuracy, total records, and ML model status.
    """
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    if not athlete:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Athlete {athlete_id} not found"
        )
    
    rpe_service = RPECalibrationService(db)
    calibration_status = rpe_service.get_calibration_status(athlete_id)
    ml_status = rpe_service.get_ml_model_status(athlete_id)
    
    return {
        "athlete_id": athlete_id,
        "calibration": calibration_status,
        "ml_model": ml_status
    }


@router.post("/athletes/{athlete_id}/rpe-calibration/train-ml")
def train_rpe_ml_model(
    athlete_id: int,
    db: Session = Depends(get_db)
):
    """
    Train ML model for RPE calibration.
    
    Requires at least 30 calibration samples with actual RIR data.
    """
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    if not athlete:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Athlete {athlete_id} not found"
        )
    
    rpe_service = RPECalibrationService(db)
    success, error = rpe_service.train_ml_model(athlete_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error
        )
    
    return {
        "athlete_id": athlete_id,
        "status": "success",
        "message": "RPE ML model trained successfully"
    }


@router.get("/athletes/{athlete_id}/ml-models")
def get_ml_model_status(
    athlete_id: int,
    db: Session = Depends(get_db)
):
    """
    Get ML model status for workout predictions.
    
    Returns model training status, sample counts, and confidence metrics.
    """
    if not ML_AVAILABLE:
        return {
            "athlete_id": athlete_id,
            "ml_available": False,
            "message": "ML features not available (scikit-learn not installed)"
        }
    
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    if not athlete:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Athlete {athlete_id} not found"
        )
    
    ml_service = WorkoutPredictorService(db)
    
    # Check if model exists and if retraining needed
    from app.ml.model_manager import ModelManager
    model_manager = ModelManager()
    metadata = model_manager.get_model_metadata("workout_predictor", athlete_id)
    should_retrain = ml_service.should_retrain(athlete_id)
    
    return {
        "athlete_id": athlete_id,
        "ml_available": True,
        "model_trained": metadata is not None,
        "model_metadata": metadata,
        "should_retrain": should_retrain,
        "min_sessions_needed": 20
    }


@router.post("/athletes/{athlete_id}/ml-models/train")
def train_workout_ml_model(
    athlete_id: int,
    db: Session = Depends(get_db)
):
    """
    Train ML model for workout parameter prediction.
    
    Requires at least 20 completed workout sessions.
    """
    if not ML_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ML features not available (scikit-learn not installed)"
        )
    
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    if not athlete:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Athlete {athlete_id} not found"
        )
    
    ml_service = WorkoutPredictorService(db)
    success, metrics, error = ml_service.train_athlete_model(athlete_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error
        )
    
    return {
        "athlete_id": athlete_id,
        "status": "success",
        "metrics": metrics,
        "message": "Workout prediction ML model trained successfully"
    }


@router.get("/athletes/{athlete_id}/analytics")
def get_athlete_analytics(
    athlete_id: int,
    days: int = 30,
    db: Session = Depends(get_db)
):
    """
    Get comprehensive athlete analytics.
    
    Includes:
    - Performance trends
    - Recovery patterns
    - Volume/intensity progression
    - Injury risk indicators
    """
    from app.models import PerformanceTrend
    from datetime import timedelta
    from sqlalchemy import desc
    
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    if not athlete:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Athlete {athlete_id} not found"
        )
    
    # Get performance trends
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    trends = db.query(PerformanceTrend).filter(
        PerformanceTrend.athlete_id == athlete_id,
        PerformanceTrend.session_date >= cutoff_date
    ).order_by(desc(PerformanceTrend.session_date)).all()
    
    if not trends:
        return {
            "athlete_id": athlete_id,
            "message": "No performance data available",
            "trends": []
        }
    
    # Calculate analytics
    avg_performance = sum(t.performance_score for t in trends) / len(trends)
    avg_readiness = sum(t.readiness_score for t in trends) / len(trends)
    avg_volume = sum(t.total_volume for t in trends) / len(trends)
    avg_rpe = sum(t.average_rpe for t in trends) / len(trends)
    
    deload_count = sum(1 for t in trends if t.deload_triggered)
    
    # Recent ACWR (injury risk indicator)
    recent_acwr = trends[0].acwr if trends and trends[0].acwr else None
    
    return {
        "athlete_id": athlete_id,
        "period_days": days,
        "session_count": len(trends),
        "averages": {
            "performance_score": round(avg_performance, 3),
            "readiness_score": round(avg_readiness, 3),
            "volume": round(avg_volume, 1),
            "rpe": round(avg_rpe, 1)
        },
        "deload_count": deload_count,
        "current_acwr": recent_acwr,
        "injury_risk_status": (
            "low" if recent_acwr and 0.8 <= recent_acwr <= 1.3 else
            "moderate" if recent_acwr and (0.7 <= recent_acwr < 0.8 or 1.3 < recent_acwr <= 1.5) else
            "high" if recent_acwr else
            "unknown"
        ),
        "trends": [
            {
                "date": t.session_date.isoformat(),
                "performance_score": t.performance_score,
                "readiness_score": t.readiness_score,
                "total_volume": t.total_volume,
                "average_rpe": t.average_rpe,
                "acwr": t.acwr,
                "deload_triggered": t.deload_triggered
            }
            for t in trends
        ]
    }

