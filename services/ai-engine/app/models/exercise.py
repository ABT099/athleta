"""
Exercise library models.
"""
from sqlalchemy import Column, Integer, String, Enum, Float, Text, ARRAY
from sqlalchemy.orm import relationship, deferred

from app.database import Base
from app.utils.constants import MuscleGroup


class Exercise(Base):
    """
    Exercise library with muscle groups and characteristics.
    """
    __tablename__ = "exercises"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True, index=True)  # Eagerly loaded (used in AI error messages)
    
    # Deferred fields - only loaded when explicitly needed (CRUD operations)
    description = deferred(Column(Text, nullable=True))
    equipment = deferred(Column(String(100), nullable=True))
    
    # Muscle groups (stored as array of enums) - eagerly loaded (used by AI)
    # Primary muscles targeted
    primary_muscles = Column(ARRAY(String), nullable=False)
    
    # Secondary muscles involved
    secondary_muscles = Column(ARRAY(String), nullable=True)
    
    # Injury risk assessment
    injury_risk_level = Column(Float, default=1.0, nullable=False)  # 1.0 = low, 2.0 = medium, 3.0 = high
    
    # Joint stress areas (for injury prevention monitoring)
    joint_stress_areas = Column(ARRAY(String), nullable=True)  # e.g., ["shoulder", "elbow", "lower_back"]
    
    # Exercise categorization
    movement_pattern = Column(String(100), nullable=True)  # squat, hinge, push, pull, carry, etc.
    exercise_type = Column(String(50), nullable=False, default='compound')  # compound, isolation
    complexity_score = Column(Float, nullable=False, default=1.0)  # 0.0-1.0, affects familiarity progression
    
    # Relationships
    workout_day_exercises = relationship("WorkoutDayExercise", back_populates="exercise")
    rpe_calibrations = relationship("AthleteRPECalibration", back_populates="exercise", cascade="all, delete-orphan")
    progression_tracking = relationship("ExerciseProgressionTracking", back_populates="exercise", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Exercise(id={self.id}, name={self.name})>"


