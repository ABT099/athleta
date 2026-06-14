"""
Personal Record (PR) tracking models.
"""
from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from app.database import Base, get_table_args_with_constraints, get_fk_reference


class ExercisePersonalRecord(Base):
    """
    Track personal records for each exercise-athlete combination.
    
    Stores rep-max PRs (1RM, 3RM, 5RM, etc.) and volume PRs.
    """
    __tablename__ = "exercise_personal_records"
    
    id = Column(Integer, primary_key=True, index=True)
    athlete_id = Column(Integer, ForeignKey(get_fk_reference("athletes.id"), ondelete="CASCADE"), nullable=False, index=True)
    exercise_id = Column(Integer, nullable=False, index=True)
    
    # Rep-max PRs
    one_rep_max = Column(Float, nullable=True)
    one_rm_date = Column(DateTime, nullable=True)
    
    three_rep_max = Column(Float, nullable=True)
    three_rm_date = Column(DateTime, nullable=True)
    
    five_rep_max = Column(Float, nullable=True)
    five_rm_date = Column(DateTime, nullable=True)
    
    eight_rep_max = Column(Float, nullable=True)
    eight_rm_date = Column(DateTime, nullable=True)
    
    ten_rep_max = Column(Float, nullable=True)
    ten_rm_date = Column(DateTime, nullable=True)
    
    twelve_rep_max = Column(Float, nullable=True)
    twelve_rm_date = Column(DateTime, nullable=True)
    
    # Volume PRs
    max_volume_session = Column(Float, nullable=True)  # Total weight×reps in one session
    max_volume_date = Column(DateTime, nullable=True)
    
    max_total_reps = Column(Integer, nullable=True)  # Most reps across all sets in one session
    max_reps_date = Column(DateTime, nullable=True)
    
    # Metadata
    total_pr_count = Column(Integer, default=0, nullable=False)
    last_pr_date = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Unique constraint: one record per athlete-exercise combination
    __table_args__ = get_table_args_with_constraints(
        UniqueConstraint('athlete_id', 'exercise_id', name='uq_athlete_exercise_pr'),
        schema="ai_analysis"
    )
    
    # Relationships
    athlete = relationship("Athlete", back_populates="personal_records")
    
    def __repr__(self):
        return f"<ExercisePersonalRecord(athlete_id={self.athlete_id}, exercise_id={self.exercise_id}, pr_count={self.total_pr_count})>"

