"""
Celery application configuration for async ML training tasks.
"""
from celery import Celery
from app.config import settings

# Create Celery instance
celery_app = Celery(
    "athleta_ml_tasks",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.ml_training"]
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # Task execution settings
    task_track_started=True,
    task_time_limit=settings.CELERY_TASK_TIMEOUT,
    task_soft_time_limit=settings.CELERY_TASK_TIMEOUT - 60,
    
    # Result backend settings
    result_expires=86400,  # Results expire after 24 hours
    result_extended=True,
    
    # Worker settings
    worker_prefetch_multiplier=1,  # One task at a time
    worker_max_tasks_per_child=50,  # Restart worker after 50 tasks
    
    # Task routing
    task_routes={
        "app.tasks.ml_training.retrain_athlete_model": {"queue": "ml_training"},
        "app.tasks.ml_training.check_and_queue_retraining": {"queue": "ml_training"},
    },
    
    # Retry settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)

