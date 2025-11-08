"""
Exercise progression tracking models.
"""
from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey, String, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database import Base


class ExerciseProgressionTracking(Base):
    """
    Track exercise-specific progression for double progression logic.
    """
    __tablename__ = "exercise_progression_tracking"
    
    id = Column(Integer, primary_key=True, index=True)
    athlete_id = Column(Integer, ForeignKey("athletes.id", ondelete="CASCADE"), nullable=False, index=True)
    exercise_id = Column(Integer, ForeignKey("exercises.id", ondelete="CASCADE"), nullable=False, index=True)
    workout_session_id = Column(Integer, ForeignKey("workout_sessions.id", ondelete="CASCADE"), nullable=False)
    session_date = Column(DateTime, nullable=False)
    
    # Performance data
    weight_used = Column(Float, nullable=False)
    total_reps = Column(Integer, nullable=False)
    total_sets = Column(Integer, nullable=False)
    average_rpe = Column(Float, nullable=False)
    estimated_1rm = Column(Float, nullable=False)
    volume_load = Column(Float, nullable=False)
    
    # Progression tracking
    progression_state = Column(String(50), nullable=False)  # "rep_progression", "weight_progression", "maintaining"
    weeks_at_weight = Column(Integer, nullable=False, default=0)
    sessions_at_weight = Column(Integer, nullable=False, default=0)
    rep_progression_target = Column(Integer, nullable=True)
    weight_progression_ready = Column(Boolean, nullable=False, default=False)
    familiarity_score = Column(Float, nullable=False, default=0.0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    athlete = relationship("Athlete", back_populates="exercise_progressions")
    exercise = relationship("Exercise", back_populates="progression_tracking")
    workout_session = relationship("WorkoutSession", back_populates="exercise_progressions")
    
    def __repr__(self):
        return f"<ExerciseProgressionTracking(athlete_id={self.athlete_id}, exercise_id={self.exercise_id}, weight={self.weight_used})>"

