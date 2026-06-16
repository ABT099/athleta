"""
Analysis (workout-completion) API endpoints.

api persists the logged session/sets/recovery and then calls this endpoint with
the data pushed in the request body (the Analysis Context). Auto-regulation
computes over that context + its own local history, writes only its own algo
tables, and returns the adjustments plus the write-backs (new PRs, updated RPE
calibration factor) for api to persist. The endpoint is idempotent by session id.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta

from app.database import get_autoreg_db
from app.models import (
    PerformanceTrend,
    ExerciseProgressionTracking,
    MuscleVolumeLog,
    JointStressLog,
    FormQualityTrend,
    WorkoutPrescriptionHistory,
)
from app.utils.helpers import get_athlete_or_404
from app.modules.analysis import AnalysisRequest, build_analysis_context
from app.modules.progression.progressive_overload_engine import ProgressiveOverloadEngine
from app.modules.progression.plan_updater import PlanUpdaterService
from app.modules.progression.pr_tracker import PRTrackerService
from app.modules.progression.workout_scheduler import WorkoutScheduler
from app.modules.rpe import RPECalibrationService

# Import ML services with graceful degradation
try:
    from app.modules.ml.workout_predictor import WorkoutPredictorService
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    WorkoutPredictorService = None


router = APIRouter()


def _clear_session_algo_rows(db: Session, session_id: int, athlete_id: int, session_date) -> None:
    """Idempotency: drop any algo rows previously written for this session."""
    for model in (PerformanceTrend, ExerciseProgressionTracking, MuscleVolumeLog, JointStressLog):
        db.query(model).filter(model.workout_session_id == session_id).delete(synchronize_session=False)
    # Form trends are keyed by (athlete, exercise, date); clear this session's date.
    db.query(FormQualityTrend).filter(
        FormQualityTrend.athlete_id == athlete_id,
        FormQualityTrend.date == session_date,
    ).delete(synchronize_session=False)


def _maybe_queue_retraining(db: Session, athlete_id: int) -> None:
    """Queue ML retraining if due (CPU-bound work stays on Celery)."""
    if not ML_AVAILABLE:
        return
    try:
        from app.models import MLTrainingJob, MLJobStatus
        predictor = WorkoutPredictorService(db)
        if not predictor.should_retrain(athlete_id):
            return
        existing = db.query(MLTrainingJob).filter(
            MLTrainingJob.athlete_id == athlete_id,
            MLTrainingJob.status.in_([MLJobStatus.PENDING, MLJobStatus.RUNNING]),
        ).first()
        if existing:
            return
        job = MLTrainingJob(athlete_id=athlete_id, trigger_reason="session_threshold", status=MLJobStatus.PENDING)
        db.add(job)
        db.flush()
        from app.modules.ml.tasks import retrain_athlete_model
        retrain_athlete_model.delay(athlete_id, job.id, "session_threshold")
    except Exception as e:
        # Retraining is non-critical; never fail the analysis for it.
        print(f"Warning: ML retraining trigger failed: {e}")


@router.post("/analysis/sessions")
def analyze_session(request: AnalysisRequest, db: Session = Depends(get_autoreg_db)):
    """
    Analyse a completed workout (pushed in the request) and return adjustments +
    write-backs. Writes only auto-regulation's own algo tables. Idempotent by
    ``session.id``.
    """
    ctx = build_analysis_context(request, db)
    athlete_id = ctx.athlete_id
    session = ctx.session

    try:
        # Idempotency: clear any algo rows from a previous analysis of this session.
        _clear_session_algo_rows(db, session.id, athlete_id, session.session_date)
        db.flush()

        # Run the engine (records this session's denormalised signals internally,
        # then computes adjustments over the local history).
        engine = ProgressiveOverloadEngine(db)
        ai_result = engine.analyze(ctx)

        adjustments = ai_result["adjustments"]
        recovery_status = ai_result["recovery_status"]
        performance_analysis = ai_result["performance_analysis"]
        plan_context = ai_result["plan_context"]

        # PR detection -> write-back for api to persist.
        pr_updates = PRTrackerService().detect_prs(ctx)

        # RPE calibration factor (auto-regulation-owned) -> write-back for api.
        calibration_factor = RPECalibrationService(db).compute_calibration_factor(athlete_id)

        plan_updater = PlanUpdaterService(db)

        # Update the current week's plan entry.
        if plan_context.get("plan_entry_id"):
            plan_updater.update_plan_entry_after_workout(
                plan_entry_id=plan_context["plan_entry_id"],
                overall_rpe=session.overall_rpe,
                total_volume=performance_analysis.get("total_volume"),
                readiness_score=recovery_status.get("readiness_score"),
                ai_adjustments=adjustments,
                commit=False,
            )

        # The same workout, updated for next time (returned to the client).
        next_workout = plan_updater.generate_next_workout(
            ctx=ctx,
            workout_day_id=session.workout_day_id,
            ai_adjustments=adjustments,
            injury_warnings=ai_result["injury_risk"]["warnings"],
            recovery_recommendations=recovery_status["recommendations"],
        )

        # Pre-store the next workout in rotation as prescription history (local).
        next_day_id = WorkoutScheduler.get_next_workout_in_rotation(session.workout_day_id, ctx.plan)
        if next_day_id:
            next_params = plan_updater.generate_next_workout(
                ctx=ctx,
                workout_day_id=next_day_id,
                ai_adjustments=adjustments,
                injury_warnings=[],
                recovery_recommendations=[],
            )
            for exercise in next_params["workout_day"].exercises:
                db.add(WorkoutPrescriptionHistory(
                    athlete_id=athlete_id,
                    workout_day_id=next_day_id,
                    exercise_id=exercise.exercise_id,
                    prescribed_date=datetime.now(timezone.utc),
                    prescribed_weight=exercise.adjusted_weight,
                    prescribed_sets=exercise.adjusted_sets,
                    prescribed_reps_min=exercise.adjusted_reps_min,
                    prescribed_reps_max=exercise.adjusted_reps_max,
                    prescribed_rpe=exercise.target_rpe,
                    prescribed_rir=exercise.target_rir,
                    rest_period_seconds=exercise.rest_period_seconds,
                    set_type=exercise.set_type,
                    rep_style=exercise.rep_style,
                    set_type_params=exercise.set_type_params,
                    rep_style_params=exercise.rep_style_params,
                    volume_multiplier=adjustments.get("volume_multiplier", 1.0),
                    intensity_multiplier=adjustments.get("intensity_multiplier", 1.0),
                    adjustment_reason=exercise.adjustment_reason,
                    week_number=plan_context.get("week_number"),
                    readiness_score=recovery_status.get("readiness_score"),
                    training_phase=str(plan_context.get("current_phase")),
                ))

        # ML retraining is CPU-bound -> Celery (after commit).
        _maybe_queue_retraining(db, athlete_id)

        db.commit()

        return {
            "session_id": session.id,
            "adjustments": adjustments,
            "next_workout": next_workout,
            "performance_analysis": performance_analysis,
            "ai_insights": ai_result["ai_insights"],
            # write-backs for api to persist:
            "pr_updates": pr_updates,
            "calibration_factor": calibration_factor,
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to analyze session: {str(e)}")


@router.get("/athletes/{athlete_id}/analytics")
def get_athlete_analytics(
    athlete_id: int,
    days: int = 30,
    db: Session = Depends(get_autoreg_db),
):
    """Athlete analytics from the local performance_trends (ACWR, readiness, deloads)."""
    get_athlete_or_404(athlete_id)  # validates existence via api

    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    trends = (
        db.query(PerformanceTrend)
        .filter(
            PerformanceTrend.athlete_id == athlete_id,
            PerformanceTrend.session_date >= cutoff_date,
        )
        .order_by(PerformanceTrend.session_date.desc())
        .all()
    )

    if not trends:
        return {"athlete_id": athlete_id, "message": "No performance data available", "trends": []}

    avg_performance = sum(t.performance_score for t in trends) / len(trends)
    avg_readiness = sum(t.readiness_score for t in trends) / len(trends)
    avg_volume = sum(t.total_volume for t in trends) / len(trends)
    avg_rpe = sum(t.average_rpe for t in trends) / len(trends)
    deload_count = sum(1 for t in trends if t.deload_triggered)
    recent_acwr = trends[0].acwr if trends and trends[0].acwr else None

    return {
        "athlete_id": athlete_id,
        "period_days": days,
        "session_count": len(trends),
        "averages": {
            "performance_score": round(avg_performance, 3),
            "readiness_score": round(avg_readiness, 3),
            "volume": round(avg_volume, 1),
            "rpe": round(avg_rpe, 1),
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
                "deload_triggered": t.deload_triggered,
            }
            for t in trends
        ],
    }
