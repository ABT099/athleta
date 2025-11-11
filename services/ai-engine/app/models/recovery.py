"""
Recovery and readiness tracking models.
"""
from sqlalchemy import Column, Integer, String, Enum, DateTime, Float, ForeignKey, Text
from sqlalchemy.orm import relationship, deferred
from datetime import datetime

from app.database import Base
from app.utils.constants import SleepQuality


class RecoveryMetrics(Base):
    """
    Daily recovery and readiness metrics.
    """
    __tablename__ = "recovery_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    athlete_id = Column(Integer, ForeignKey("athletes.id"), nullable=False)
    
    # Date of measurement
    date = Column(DateTime, nullable=False, index=True)
    
    # Sleep data
    sleep_quality = Column(Enum(SleepQuality), nullable=False)
    sleep_hours = Column(Float, nullable=True)
    
    # Soreness levels (1-10 scale)
    overall_soreness = Column(Integer, nullable=True)
    
    # Muscle-specific soreness (JSON field)
    # Format: {"chest": 3, "legs": 7, "back": 2}
    muscle_soreness = Column(Text, nullable=True)
    
    # Stress and wellness
    stress_level = Column(Integer, nullable=True)  # 1-10 scale
    energy_level = Column(Integer, nullable=True)  # 1-10 scale
    
    # Calculated readiness score (by AI engine)
    readiness_score = Column(Float, nullable=True)  # 0.0-1.0
    
    # Nutrition adherence
    nutrition_adherence = Column(String(50), nullable=True)  # "excellent", "good", "fair", "poor"
    hydration_level = Column(String(50), nullable=True)  # "well_hydrated", "adequate", "dehydrated"
    
    # Deferred fields - only loaded when explicitly needed (CRUD operations)
    notes = deferred(Column(Text, nullable=True))
    created_at = deferred(Column(DateTime, default=datetime.utcnow, nullable=False))
    
    # Relationships
    athlete = relationship("Athlete", back_populates="recovery_metrics")
    
    def __repr__(self):
        return f"<RecoveryMetrics(id={self.id}, athlete_id={self.athlete_id}, date={self.date}, sleep={self.sleep_quality})>"

