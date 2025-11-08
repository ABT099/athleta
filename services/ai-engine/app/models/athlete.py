"""
Athlete model and related data.
"""
from sqlalchemy import Column, Integer, String, Enum, DateTime, Text, Float
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database import Base
from app.utils.constants import TrainingExperience, Gender


class Athlete(Base):
    """
    Athlete profile with demographic and training information.
    """
    __tablename__ = "athletes"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    
    # Demographics
    age = Column(Integer, nullable=False)
    gender = Column(Enum(Gender), nullable=False)
    
    # Training background
    training_experience = Column(Enum(TrainingExperience), nullable=False)
    
    # RPE calibration
    rpe_calibration_factor = Column(Float, nullable=False, default=1.0)
    
    # Injury history (JSON-like text field for flexibility)
    injury_history = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    workout_plans = relationship("WorkoutPlan", back_populates="athlete", cascade="all, delete-orphan")
    workout_sessions = relationship("WorkoutSession", back_populates="athlete", cascade="all, delete-orphan")
    recovery_metrics = relationship("RecoveryMetrics", back_populates="athlete", cascade="all, delete-orphan")
    rpe_calibrations = relationship("AthleteRPECalibration", back_populates="athlete", cascade="all, delete-orphan")
    performance_trends = relationship("PerformanceTrend", back_populates="athlete", cascade="all, delete-orphan")
    exercise_progressions = relationship("ExerciseProgressionTracking", back_populates="athlete", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Athlete(id={self.id}, name={self.name}, experience={self.training_experience})>"


