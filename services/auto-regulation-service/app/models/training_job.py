"""
ML Training Job tracking model.
"""
from sqlalchemy import Column, Integer, String, Enum, DateTime, ForeignKey, Text, Index, JSON
from datetime import datetime, timezone
import enum

from autoregulation.database import Base, get_table_args_with_constraints, get_fk_reference


class MLJobStatus(str, enum.Enum):
    """ML training job status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class MLTrainingJob(Base):
    """
    Tracks asynchronous ML model training jobs.
    
    Used to monitor background retraining tasks and avoid duplicate jobs.
    """
    __tablename__ = "ml_training_jobs"
    __table_args__ = get_table_args_with_constraints(
        Index("idx_ml_training_jobs_athlete_status", "athlete_id", "status"),
        Index("idx_ml_training_jobs_created_at", "created_at"),
        schema="ai_analysis"
    )
    
    id = Column(Integer, primary_key=True, index=True)
    celery_task_id = Column(String(255), nullable=True)
    athlete_id = Column(Integer, ForeignKey(get_fk_reference("athletes.id"), ondelete="CASCADE"), nullable=False)
    
    # Why was retraining triggered
    trigger_reason = Column(String(100), nullable=False)  # 'mesocycle_complete', 'staleness', 'session_threshold', 'manual'
    
    # Job status
    status = Column(Enum(MLJobStatus), nullable=False, default=MLJobStatus.PENDING)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Results
    training_metrics = Column(JSON, nullable=True)  # Store training metrics as JSON
    error_message = Column(Text, nullable=True)
    
    def __repr__(self):
        return f"<MLTrainingJob(id={self.id}, athlete_id={self.athlete_id}, status={self.status})>"

