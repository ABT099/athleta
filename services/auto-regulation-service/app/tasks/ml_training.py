"""
Celery tasks for ML model retraining.
"""
from celery import Task
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session

from autoregulation.celery_app import celery_app
from autoregulation.database import SessionLocal
from autoregulation.models import MLTrainingJob, MLJobStatus
from autoregulation.ml.workout_predictor import WorkoutPredictorService


class DatabaseTask(Task):
    """Base task with database session management."""
    _db: Optional[Session] = None
    
    def after_return(self, *args, **kwargs):
        """Close database session after task completion."""
        if self._db is not None:
            self._db.close()
            self._db = None


@celery_app.task(bind=True, base=DatabaseTask, name="autoregulation.tasks.ml_training.retrain_athlete_model")
def retrain_athlete_model(self, athlete_id: int, job_id: int, trigger_reason: str):
    """
    Train ML model for a specific athlete.
    
    Args:
        athlete_id: Athlete ID to train model for
        job_id: MLTrainingJob ID for tracking
        trigger_reason: Why retraining was triggered
        
    Returns:
        Dict with success status and metrics
    """
    db = SessionLocal()
    self._db = db
    
    try:
        # Get job record
        job = db.query(MLTrainingJob).filter(MLTrainingJob.id == job_id).first()
        if not job:
            return {"success": False, "error": f"Job {job_id} not found"}
        
        # Update job status to running
        job.status = MLJobStatus.RUNNING
        job.started_at = datetime.now(timezone.utc)
        job.celery_task_id = self.request.id
        db.commit()
        
        # Train the model
        predictor_service = WorkoutPredictorService(db)
        success, metrics, error = predictor_service.train_athlete_model(athlete_id)
        
        if success:
            # Update job with success
            job.status = MLJobStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc)
            job.training_metrics = metrics
            db.commit()
            
            return {
                "success": True,
                "athlete_id": athlete_id,
                "trigger_reason": trigger_reason,
                "metrics": metrics
            }
        else:
            # Update job with failure
            job.status = MLJobStatus.FAILED
            job.completed_at = datetime.now(timezone.utc)
            job.error_message = error or "Training failed"
            db.commit()
            
            return {
                "success": False,
                "athlete_id": athlete_id,
                "error": error
            }
    
    except Exception as e:
        # Handle unexpected errors
        try:
            job = db.query(MLTrainingJob).filter(MLTrainingJob.id == job_id).first()
            if job:
                job.status = MLJobStatus.FAILED
                job.completed_at = datetime.now(timezone.utc)
                job.error_message = str(e)
                db.commit()
        except Exception:
            pass
        
        return {
            "success": False,
            "athlete_id": athlete_id,
            "error": str(e)
        }
    finally:
        db.close()


@celery_app.task(name="autoregulation.tasks.ml_training.check_and_queue_retraining")
def check_and_queue_retraining(athlete_id: int, trigger_reason: str = "scheduled"):
    """
    Check if retraining is needed and queue a job if so.
    
    This can be called manually or on a schedule to check retraining needs.
    
    Args:
        athlete_id: Athlete ID to check
        trigger_reason: Why this check was triggered
        
    Returns:
        Dict with status information
    """
    db = SessionLocal()
    
    try:
        # Check for existing pending/running jobs
        existing_job = db.query(MLTrainingJob).filter(
            MLTrainingJob.athlete_id == athlete_id,
            MLTrainingJob.status.in_([MLJobStatus.PENDING, MLJobStatus.RUNNING])
        ).first()
        
        if existing_job:
            return {
                "queued": False,
                "reason": "Job already pending or running",
                "existing_job_id": existing_job.id
            }
        
        # Check if retraining is needed
        predictor_service = WorkoutPredictorService(db)
        should_retrain = predictor_service.should_retrain(athlete_id)
        
        if not should_retrain:
            return {
                "queued": False,
                "reason": "Retraining not needed"
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
        retrain_athlete_model.delay(athlete_id, job.id, trigger_reason)
        
        return {
            "queued": True,
            "job_id": job.id,
            "athlete_id": athlete_id,
            "trigger_reason": trigger_reason
        }
    
    except Exception as e:
        return {
            "queued": False,
            "error": str(e)
        }
    finally:
        db.close()

