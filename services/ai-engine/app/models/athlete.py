"""
Athlete model and related data.

Optimized for AI engine - only contains fields used by AI calculations.
CRUD fields (name, email, injury_history, timestamps) are handled by NestJS API.
"""
from sqlalchemy import Column, Integer, Enum, Float
from sqlalchemy.orm import relationship

from app.database import Base
from app.utils.constants import TrainingExperience, Gender


class Athlete(Base):
    """
    Athlete profile optimized for AI engine performance.
    
    Only contains fields used by AI calculations:
    - id, age, gender, training_experience, rpe_calibration_factor
    
    CRUD fields (name, email, injury_history, timestamps) are managed by NestJS API.
    """
    __tablename__ = "athletes"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Core AI fields - used in AI calculations
    age = Column(Integer, nullable=False)
    gender = Column(Enum(Gender), nullable=False)
    training_experience = Column(Enum(TrainingExperience), nullable=False)
    rpe_calibration_factor = Column(Float, nullable=False, default=1.0)
    
    # Relationships - explicitly lazy to avoid accidental loads
    workout_plans = relationship("WorkoutPlan", back_populates="athlete", cascade="all, delete-orphan", lazy="noload")
    workout_sessions = relationship("WorkoutSession", back_populates="athlete", cascade="all, delete-orphan", lazy="noload")
    recovery_metrics = relationship("RecoveryMetrics", back_populates="athlete", cascade="all, delete-orphan", lazy="noload")
    rpe_calibrations = relationship("AthleteRPECalibration", back_populates="athlete", cascade="all, delete-orphan", lazy="noload")
    performance_trends = relationship("PerformanceTrend", back_populates="athlete", cascade="all, delete-orphan", lazy="noload")
    exercise_progressions = relationship("ExerciseProgressionTracking", back_populates="athlete", cascade="all, delete-orphan", lazy="noload")
    
    def __repr__(self):
        return f"<Athlete(id={self.id}, experience={self.training_experience})>"


