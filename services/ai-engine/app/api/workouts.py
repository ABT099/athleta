"""
Workouts API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, undefer
from datetime import datetime, timedelta, timezone
import json

from app.database import get_db
from app.models import (
    Athlete, WorkoutDay, WorkoutSession, ExerciseSet, 
    RecoveryMetrics
)
from app.utils.helpers import get_athlete_or_404
from app.schemas.workout import (
    WorkoutCompletionRequest,
    WorkoutCompletionResponse,
    WorkoutSessionResponse,
    RecoveryMetricsResponse,
    NextWorkoutResponse
)
from app.services.progressive_overload_engine import ProgressiveOverloadEngine
from app.services.plan_updater import PlanUpdaterService
from app.services.rpe_calibration import RPECalibrationService
from app.services.pr_tracker import PRTrackerService
from app.services.workout_scheduler import WorkoutScheduler

# Import ML services with graceful degradation
try:
    from app.ml.workout_predictor import WorkoutPredictorService
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    WorkoutPredictorService = None


router = APIRouter()

from app.auth import get_current_user


@router.post("/workouts/complete", response_model=WorkoutCompletionResponse)
def complete_workout(
    request: WorkoutCompletionRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Main endpoint: Submit completed workout and receive next workout adjustments.
    
    This is the core API that processes workout data and returns AI-generated
    progressive overload recommendations.
    """
    try:
        # Validate athlete exists - cache for reuse
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
                set_type_used=set_data.set_type_used,
                rep_style_used=set_data.rep_style_used,
                technique_details=set_data.technique_details,
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
        
        # Step 1: Analyze plan context (needed for recovery assessment)
        plan_context = engine.analyze_plan_context(request.athlete_id)
        
        # Step 2: Analyze workout performance (needed for PerformanceTrend)
        # Use cached athlete object instead of re-querying
        performance_analysis = engine.analyze_workout_performance(
            athlete, request.workout_day_id, session_data, plan_context
        )
        
        # Step 3: Assess recovery status (needed for PerformanceTrend and ML)
        recovery_status = engine.assess_recovery_status(
            request.athlete_id, recovery_data, plan_context
        )
        
        # Step 4: Create PerformanceTrend BEFORE ML prediction
        # This ensures the new session is included in ML feature extraction
        performance_trend = engine.create_performance_trend_for_session(
            workout_session=workout_session,
            recovery_status=recovery_status,
            performance_analysis=performance_analysis,
            athlete_id=request.athlete_id
        )
        db.flush()  # Make PerformanceTrend available for ML queries
        
        # Step 5: Process workout and get AI recommendations (now includes current session)
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
        
        # Track form quality for this session
        from app.services.form_quality_service import FormQualityService
        form_service = FormQualityService(db)
        session_metrics = form_service.track_session_form_quality(workout_session.id)
        
        # Save form quality trends for each exercise
        for exercise_id, metrics in session_metrics.items():
            form_service.save_form_quality_trend(
                athlete_id=request.athlete_id,
                exercise_id=exercise_id,
                date=workout_session.session_date,
                average_form_score=metrics["average_form_score"],
                sets_analyzed=metrics["sets_analyzed"],
                degradation_rate=metrics["degradation_rate"],
                high_rpe_poor_form_count=metrics["high_rpe_poor_form_count"]
            )
        
        # === MULTI-STEP WORKOUT UPDATES ===
        
        # Step 1: Update plan entry with new multipliers (existing code)
        plan_context = ai_result["plan_context"]
        if plan_context.get("plan_entry_id"):
            plan_updater = PlanUpdaterService(db)
            plan_updater.update_plan_entry_after_workout(
                plan_entry_id=plan_context["plan_entry_id"],
                workout_session=workout_session,
                recovery_metrics=recovery_metrics,
                ai_adjustments=ai_result["adjustments"],
                commit=False  # Defer commit to parent transaction
            )
        
        # Step 2: Generate current workout with updated parameters (FOR RETURN)
        # This returns the SAME workout (e.g., Upper) with adjustments for next week
        plan_updater = PlanUpdaterService(db)
        current_workout_updated = plan_updater.generate_next_workout(
            athlete_id=request.athlete_id,
            workout_day_id=request.workout_day_id,  # SAME workout
            ai_adjustments=ai_result["adjustments"],
            injury_warnings=ai_result["injury_risk"]["warnings"],
            recovery_recommendations=ai_result["recovery_status"]["recommendations"]
        )
        
        # Step 3: Pre-calculate and store next workout in rotation WITH RECOVERY ADJUSTMENT
        scheduler = WorkoutScheduler(db)
        next_workout_day_id = scheduler.get_next_workout_in_rotation(
            athlete_id=request.athlete_id,
            completed_workout_day_id=request.workout_day_id,
            plan_id=plan_context["plan_id"]
        )
        
        if next_workout_day_id:
            # Extract readiness score from current workout
            current_readiness = recovery_metrics.readiness_score
            
            # Adjust multipliers for next workout based on current recovery
            # If readiness is low, reduce volume/intensity for next workout
            from app.utils.constants import (
                LOW_READINESS_THRESHOLD,
                EXCELLENT_READINESS_THRESHOLD,
                POOR_RECOVERY_VOLUME_REDUCTION,
                POOR_RECOVERY_INTENSITY_REDUCTION,
                EXCELLENT_RECOVERY_VOLUME_INCREASE
            )
            
            next_workout_adjustments = ai_result["adjustments"].copy()
            if current_readiness and current_readiness < LOW_READINESS_THRESHOLD:
                next_workout_adjustments["volume_multiplier"] *= POOR_RECOVERY_VOLUME_REDUCTION
                next_workout_adjustments["intensity_multiplier"] *= POOR_RECOVERY_INTENSITY_REDUCTION
                adjustment_note = f"Reduced due to low readiness ({current_readiness:.2f})"
            elif current_readiness and current_readiness > EXCELLENT_READINESS_THRESHOLD:
                next_workout_adjustments["volume_multiplier"] *= EXCELLENT_RECOVERY_VOLUME_INCREASE
                adjustment_note = f"Increased due to high readiness ({current_readiness:.2f})"
            else:
                adjustment_note = "Standard progression"
            
            # Generate next workout parameters with recovery-adjusted multipliers
            next_workout_params = plan_updater.generate_next_workout(
                athlete_id=request.athlete_id,
                workout_day_id=next_workout_day_id,  # NEXT in rotation (e.g., Lower)
                ai_adjustments=next_workout_adjustments,  # Recovery-adjusted
                injury_warnings=[],
                recovery_recommendations=[]
            )
            
            # Store prescription history for each exercise in next workout
            from app.models.workout_prescription_history import WorkoutPrescriptionHistory
            
            for exercise in next_workout_params["workout_day"].exercises:
                prescription = WorkoutPrescriptionHistory(
                    athlete_id=request.athlete_id,
                    workout_day_id=next_workout_day_id,
                    exercise_id=exercise.exercise_id,
                    prescribed_date=datetime.now(timezone.utc),
                    
                    # Prescribed parameters
                    prescribed_weight=exercise.adjusted_weight,
                    prescribed_sets=exercise.adjusted_sets,
                    prescribed_reps_min=exercise.adjusted_reps_min,
                    prescribed_reps_max=exercise.adjusted_reps_max,
                    prescribed_rpe=exercise.target_rpe,
                    prescribed_rir=exercise.target_rir,
                    rest_period_seconds=exercise.rest_period_seconds,
                    
                    # Intensity techniques
                    set_type=exercise.set_type,
                    rep_style=exercise.rep_style,
                    set_type_params=exercise.set_type_params,
                    rep_style_params=exercise.rep_style_params,
                    
                    # AI context
                    volume_multiplier=next_workout_adjustments["volume_multiplier"],
                    intensity_multiplier=next_workout_adjustments["intensity_multiplier"],
                    adjustment_reason=f"{adjustment_note}. {exercise.adjustment_reason or ''}",
                    
                    # Context
                    week_number=plan_context.get("week_number"),
                    readiness_score=current_readiness,
                    training_phase=plan_context.get("current_phase")
                )
                db.add(prescription)
        
        # === PR DETECTION ===
        # Detect and update personal records
        pr_tracker = PRTrackerService(db)
        pr_updates = pr_tracker.detect_and_update_prs(workout_session.id, commit=False)  # Defer commit to parent transaction
        
        # Add PR achievements to AI insights
        if pr_updates.get("achievements"):
            ai_result["ai_insights"].extend(pr_updates["achievements"])
        
        # Single commit for all changes - ensures atomicity
        db.commit()
        
        # Undefer deferred fields for response
        db.refresh(workout_session)
        db.refresh(recovery_metrics)
        
        # Undefer notes and created_at for response
        workout_session = db.query(WorkoutSession).options(
            undefer(WorkoutSession.notes),
            undefer(WorkoutSession.created_at)
        ).filter(WorkoutSession.id == workout_session.id).first()
        
        recovery_metrics = db.query(RecoveryMetrics).options(
            undefer(RecoveryMetrics.notes),
            undefer(RecoveryMetrics.created_at)
        ).filter(RecoveryMetrics.id == recovery_metrics.id).first()
        
        # Build response
        return WorkoutCompletionResponse(
            workout_session=WorkoutSessionResponse.model_validate(workout_session),
            recovery_metrics=RecoveryMetricsResponse.model_validate(recovery_metrics),
            next_workout=NextWorkoutResponse(**current_workout_updated),  # Same workout, updated
            performance_analysis=ai_result["performance_analysis"],
            ai_insights=ai_result["ai_insights"]
        )
    
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Rollback on any error
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to complete workout: {str(e)}"
        )


@router.get("/athletes/{athlete_id}/next-workout")
def get_next_workout(
    athlete_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get next scheduled workout with current parameters (without completing a workout).
    """
    athlete = get_athlete_or_404(db, athlete_id)
    
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

@router.get("/athletes/{athlete_id}/rpe-calibration")
def get_rpe_calibration_status(
    athlete_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get RPE calibration status for an athlete.
    
    Returns calibration accuracy, total records, and ML model status.
    """
    athlete = get_athlete_or_404(db, athlete_id)
    
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
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Train ML model for RPE calibration.
    
    Requires at least 30 calibration samples with actual RIR data.
    """
    athlete = get_athlete_or_404(db, athlete_id)
    
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
    current_user: dict = Depends(get_current_user),
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
    
    athlete = get_athlete_or_404(db, athlete_id)
    
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
    current_user: dict = Depends(get_current_user),
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
    
    athlete = get_athlete_or_404(db, athlete_id)
    
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
    current_user: dict = Depends(get_current_user),
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
    
    athlete = get_athlete_or_404(db, athlete_id)
    
    # Get performance trends
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
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

