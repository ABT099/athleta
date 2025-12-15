"""
Exercise library models.
"""
from sqlalchemy import Column, Integer, String, Enum, Float, ARRAY
from sqlalchemy.orm import relationship, deferred

from app.database import Base


class Exercise(Base):
    """
    Exercise library with muscle groups and characteristics.
    
    Muscles are now linked via ExerciseMuscle junction table with activation percentages.
    """
    __tablename__ = "exercises"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True, index=True)  # Eagerly loaded (used in AI error messages)
    
    # Deferred fields - only loaded when explicitly needed (CRUD operations)
    equipment = deferred(Column(String(100), nullable=True))
    
    # Injury risk assessment
    injury_risk_level = Column(Float, default=1.0, nullable=False)  # 1.0 = low, 2.0 = medium, 3.0 = high
    
    # Joint stress areas (for injury prevention monitoring)
    joint_stress_areas = Column(ARRAY(String), nullable=True)  # e.g., ["shoulder", "elbow", "lower_back"]
    
    # Exercise categorization
    movement_pattern = Column(String(100), nullable=True)  # squat, hinge, push, pull, carry, etc.
    exercise_type = Column(String(50), nullable=False, default='compound')  # compound, isolation
    complexity_score = Column(Float, nullable=False, default=1.0)  # 0.0-1.0, affects familiarity progression
    intensity_category = Column(
        Enum("compound_heavy", "compound_moderate", "isolation", name="intensity_category_enum"),
        nullable=False,
        default="isolation"
    )  # CNS demand category for prescription generation
    
    # Relationships
    muscle_links = relationship("ExerciseMuscle", back_populates="exercise", cascade="all, delete-orphan")
    workout_day_exercises = relationship("WorkoutDayExercise", back_populates="exercise")
    rpe_calibrations = relationship("AthleteRPECalibration", back_populates="exercise", cascade="all, delete-orphan")
    progression_tracking = relationship("ExerciseProgressionTracking", back_populates="exercise", cascade="all, delete-orphan")
    personal_records = relationship("ExercisePersonalRecord", back_populates="exercise", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Exercise(id={self.id}, name={self.name})>"


