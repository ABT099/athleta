"""
ML Model Management API endpoints.

Endpoints for training, managing, and monitoring ML models.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models import Athlete, WorkoutSession
from app.utils.helpers import get_athlete_or_404
from app.modules.ml.model_selector import ModelSelector
from app.modules.ml.model_manager import ModelManager

# Import ML services with graceful degradation
try:
    from app.modules.ml.workout_predictor import WorkoutPredictorService
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    WorkoutPredictorService = None


router = APIRouter()

@router.post("/ml/train/{athlete_id}")
def train_athlete_model_async(
    athlete_id: int,
    trigger_reason: str = "manual",
    db: Session = Depends(get_db)
):
    """
    Queue async ML model training for specific athlete.
    
    Creates a background job that won't block the API response.
    
    Args:
        athlete_id: Athlete ID
        trigger_reason: Reason for training (manual, mesocycle_complete, etc.)
    
    Returns job information.
    """
    if not ML_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ML services not available"
        )
    
    # Validate athlete exists
    athlete = get_athlete_or_404(db, athlete_id)
    
    # Check for existing pending/running jobs
    from app.models import MLTrainingJob, MLJobStatus
    existing_job = db.query(MLTrainingJob).filter(
        MLTrainingJob.athlete_id == athlete_id,
        MLTrainingJob.status.in_([MLJobStatus.PENDING, MLJobStatus.RUNNING])
    ).first()
    
    if existing_job:
        return {
            "athlete_id": athlete_id,
            "status": "already_queued",
            "job_id": existing_job.id,
            "message": f"Training job already {existing_job.status.value}"
        }
    
    # Create job record
    job = MLTrainingJob(
        athlete_id=athlete_id,
        trigger_reason=trigger_reason,
        status=MLJobStatus.PENDING
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    
    # Queue the training task
    try:
        from app.modules.ml.tasks import retrain_athlete_model
        retrain_athlete_model.delay(athlete_id, job.id, trigger_reason)
    except Exception as e:
        # If task queueing fails, mark job as failed
        job.status = MLJobStatus.FAILED
        job.error_message = f"Failed to queue task: {str(e)}"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue training task: {str(e)}"
        )
    
    return {
        "athlete_id": athlete_id,
        "status": "queued",
        "job_id": job.id,
        "trigger_reason": trigger_reason,
        "created_at": job.created_at.isoformat()
    }


@router.get("/ml/jobs/{job_id}")
def get_training_job_status(
    job_id: int,
    db: Session = Depends(get_db)
):
    """
    Get status of a specific ML training job.
    
    Args:
        job_id: Training job ID
    
    Returns job status and metrics.
    """
    from app.models import MLTrainingJob
    
    job = db.query(MLTrainingJob).filter(MLTrainingJob.id == job_id).first()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Training job {job_id} not found"
        )
    
    response = {
        "job_id": job.id,
        "athlete_id": job.athlete_id,
        "status": job.status.value,
        "trigger_reason": job.trigger_reason,
        "created_at": job.created_at.isoformat(),
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }
    
    if job.training_metrics:
        response["training_metrics"] = job.training_metrics
    
    if job.error_message:
        response["error_message"] = job.error_message
    
    if job.celery_task_id:
        response["celery_task_id"] = job.celery_task_id
    
    return response


@router.get("/ml/jobs")
def list_training_jobs(
    athlete_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    List ML training jobs with optional filters.
    
    Args:
        athlete_id: Filter by athlete ID
        status: Filter by status (pending, running, completed, failed)
        limit: Maximum number of jobs to return
    
    Returns list of training jobs.
    """
    from app.models import MLTrainingJob, MLJobStatus
    from sqlalchemy import desc
    
    query = db.query(MLTrainingJob)
    
    if athlete_id:
        query = query.filter(MLTrainingJob.athlete_id == athlete_id)
    
    if status:
        try:
            status_enum = MLJobStatus(status)
            query = query.filter(MLTrainingJob.status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status}. Must be one of: pending, running, completed, failed"
            )
    
    jobs = query.order_by(desc(MLTrainingJob.created_at)).limit(limit).all()
    
    return {
        "jobs": [
            {
                "job_id": job.id,
                "athlete_id": job.athlete_id,
                "status": job.status.value,
                "trigger_reason": job.trigger_reason,
                "created_at": job.created_at.isoformat(),
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                "has_metrics": job.training_metrics is not None,
                "error_message": job.error_message
            }
            for job in jobs
        ],
        "count": len(jobs)
    }