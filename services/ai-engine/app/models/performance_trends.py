"""
Performance trends tracking models.
"""
from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database import Base, get_schema_table_args, get_fk_reference


class PerformanceTrend(Base):
    """
    Track performance trends for autoregulated deloads.
    """
    __tablename__ = "performance_trends"
    __table_args__ = get_schema_table_args("ai_analysis")
    
    id = Column(Integer, primary_key=True, index=True)
    athlete_id = Column(Integer, ForeignKey(get_fk_reference("athletes.id"), ondelete="CASCADE"), nullable=False, index=True)
    workout_session_id = Column(Integer, ForeignKey(get_fk_reference("workout_sessions.id", "ai_analysis"), ondelete="CASCADE"), nullable=False)
    session_date = Column(DateTime, nullable=False, index=True)
    
    # Performance metrics
    total_volume = Column(Float, nullable=False)
    average_intensity = Column(Float, nullable=False)
    average_rpe = Column(Float, nullable=False)
    readiness_score = Column(Float, nullable=False)
    performance_score = Column(Float, nullable=False)
    fatigue_index = Column(Float, nullable=False)
    volume_load = Column(Float, nullable=False)
    
    # Training load metrics
    training_monotony = Column(Float, nullable=True)
    training_strain = Column(Float, nullable=True)
    acute_load = Column(Float, nullable=True)
    chronic_load = Column(Float, nullable=True)
    acwr = Column(Float, nullable=True)
    
    # Deload tracking
    deload_triggered = Column(Boolean, nullable=False, default=False)
    deload_reason = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    athlete = relationship("Athlete", back_populates="performance_trends")
    workout_session = relationship("WorkoutSession", back_populates="performance_trend")
    
    def __repr__(self):
        return f"<PerformanceTrend(athlete_id={self.athlete_id}, date={self.session_date}, performance={self.performance_score})>"

