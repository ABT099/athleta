"""
Workout planning and session models.
"""
from sqlalchemy import Column, Integer, String, Enum, DateTime, Float, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship, deferred
from datetime import datetime

from app.database import Base, get_schema_table_args, get_fk_reference
from app.utils.constants import TrainingType, PeriodizationModel, TrainingPhase


class WorkoutPlan(Base):
    """
    Workout plan blueprint - the master template for a training program.
    """
    __tablename__ = "workout_plans"
    
    id = Column(Integer, primary_key=True, index=True)
    athlete_id = Column(Integer, ForeignKey("athletes.id"), nullable=False)
    
    # Deferred fields - only loaded when explicitly needed (CRUD operations)
    name = deferred(Column(String(255), nullable=False))
    created_at = deferred(Column(DateTime, default=datetime.utcnow, nullable=False))
    
    # Plan characteristics - eagerly loaded (used by AI)
    training_type = Column(Enum(TrainingType), nullable=False)
    periodization_model = Column(Enum(PeriodizationModel), nullable=False)
    focus_areas = Column(JSON, nullable=True)  # e.g., ["chest", "arms", "legs"]
    
    # Schedule
    frequency = Column(Integer, nullable=False)  # workouts per week
    duration_weeks = Column(Integer, nullable=False)  # total program length
    
    # Timestamps
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=True)
    
    is_active = Column(Integer, default=1, nullable=False)  # 1 = active, 0 = inactive
    
    # Relationships
    athlete = relationship("Athlete", back_populates="workout_plans")
    plan_entries = relationship("PlanEntry", back_populates="workout_plan", cascade="all, delete-orphan")
    workout_days = relationship("WorkoutDay", back_populates="workout_plan", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<WorkoutPlan(id={self.id}, type={self.training_type})>"


class PlanEntry(Base):
    """
    Weekly plan entry - tracks weekly adjustments and progression.
    This is updated by the AI engine based on athlete performance.
    """
    __tablename__ = "plan_entries"
    __table_args__ = get_schema_table_args("ai_analysis")
    
    id = Column(Integer, primary_key=True, index=True)
    workout_plan_id = Column(Integer, ForeignKey(get_fk_reference("workout_plans.id")), nullable=False)
    
    # Week tracking
    week_number = Column(Integer, nullable=False)  # week within the mesocycle
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    
    # Phase information (can change week to week in undulating periodization)
    training_phase = Column(Enum(TrainingPhase), nullable=False)
    
    # Volume and intensity targets for this week
    target_volume_multiplier = Column(Float, default=1.0, nullable=False)  # relative to baseline
    target_intensity_multiplier = Column(Float, default=1.0, nullable=False)  # relative to baseline
    
    # Deload flag
    is_deload_week = Column(Integer, default=0, nullable=False)  # 1 = deload, 0 = normal
    
    # AI adjustments (JSON field storing modifications)
    ai_adjustments = Column(JSON, nullable=True)
    
    # Performance summary for the week
    completed_workouts = Column(Integer, default=0, nullable=False)
    average_rpe = Column(Float, nullable=True)
    average_recovery_score = Column(Float, nullable=True)
    total_volume = Column(Float, nullable=True)  # kg lifted
    
    # Notes
    notes = Column(Text, nullable=True)
     
    # Relationships
    workout_plan = relationship("WorkoutPlan", back_populates="plan_entries")
    
    def __repr__(self):
        return f"<PlanEntry(id={self.id}, week={self.week_number}, phase={self.training_phase})>"


class WorkoutDay(Base):
    """
    Scheduled workout day with prescribed exercises and parameters.
    """
    __tablename__ = "workout_days"
    
    id = Column(Integer, primary_key=True, index=True)
    workout_plan_id = Column(Integer, ForeignKey("workout_plans.id"), nullable=False)
    
    # Deferred fields - only loaded when explicitly needed (CRUD operations)
    name = deferred(Column(String(255), nullable=False))  # e.g., "Push Day A", "Lower Body"
    created_at = deferred(Column(DateTime, default=datetime.utcnow, nullable=False))
    
    # Day of week (0=Monday, 6=Sunday) - eagerly loaded (used by AI)
    day_of_week = Column(Integer, nullable=True)
    
    # Order in the weekly split
    order_in_week = Column(Integer, nullable=False)
    
    # Target muscle groups for this day
    target_muscle_groups = Column(JSON, nullable=False)
    
    # Relationships
    workout_plan = relationship("WorkoutPlan", back_populates="workout_days")
    exercises = relationship("WorkoutDayExercise", back_populates="workout_day", cascade="all, delete-orphan")
    workout_sessions = relationship("WorkoutSession", back_populates="workout_day")
    
    def __repr__(self):
        return f"<WorkoutDay(id={self.id})>"


class WorkoutDayExercise(Base):
    """
    Exercise prescription for a specific workout day.
    """
    __tablename__ = "workout_day_exercises"
    
    id = Column(Integer, primary_key=True, index=True)
    workout_day_id = Column(Integer, ForeignKey("workout_days.id"), nullable=False)
    exercise_id = Column(Integer, ForeignKey("exercises.id"), nullable=False)
    
    # Exercise order in the workout
    order_in_workout = Column(Integer, nullable=False)
    
    # Prescribed parameters (baseline - adjusted by AI)
    target_sets_min = Column(Integer, nullable=False)
    target_sets_max = Column(Integer, nullable=False)
    target_reps_min = Column(Integer, nullable=False)
    target_reps_max = Column(Integer, nullable=False)
    target_rpe = Column(Float, nullable=True)  # target RPE
    target_rir = Column(Integer, nullable=True)  # target RIR
    
    # Rest period in seconds
    rest_period_seconds = Column(Integer, nullable=True)
    
    # Tempo (e.g., "3-1-2-0" for eccentric-pause-concentric-pause)
    tempo = Column(String(20), nullable=True)
    
    # Exercise notes and cues
    notes = Column(Text, nullable=True)
    
    # Is this a primary or accessory exercise
    is_primary = Column(Integer, default=1, nullable=False)  # 1 = primary, 0 = accessory
    
    # Progression scheme (e.g., "linear", "double_progression", "wave")
    progression_scheme = Column(String(50), nullable=True)
    
    # Warm-up sets configuration
    warm_up_sets = Column(Integer, default=0, nullable=False)  # 0-4 warm-up sets
    auto_generate_warmups = Column(Integer, default=1, nullable=False)  # 1 = auto-generate, 0 = manual
    
    # Intensity techniques
    set_type = Column(Enum("straight", "drop_set", "rest_pause", "myo_reps", "cluster_set", "superset_antagonist", "pre_exhaust", name="set_type_enum"), default="straight", nullable=False)
    rep_style = Column(Enum("normal", "lengthened_partials", "tempo_eccentric", "tempo_paused", "eccentric_overload", name="rep_style_enum"), default="normal", nullable=False)
    set_type_params = Column(JSON, nullable=True)  # Technique-specific parameters
    rep_style_params = Column(JSON, nullable=True)  # Rep style-specific parameters
    
    # Relationships
    workout_day = relationship("WorkoutDay", back_populates="exercises")
    exercise = relationship("Exercise", back_populates="workout_day_exercises")
    
    def __repr__(self):
        return f"<WorkoutDayExercise(id={self.id}, exercise_id={self.exercise_id})>"


class WorkoutSession(Base):
    """
    Completed workout session with actual performance data.
    """
    __tablename__ = "workout_sessions"
    __table_args__ = get_schema_table_args("ai_analysis")
    
    id = Column(Integer, primary_key=True, index=True)
    athlete_id = Column(Integer, ForeignKey(get_fk_reference("athletes.id")), nullable=False)
    workout_day_id = Column(Integer, ForeignKey(get_fk_reference("workout_days.id")), nullable=False)
    
    # Session timing - eagerly loaded (used by AI)
    session_date = Column(DateTime, nullable=False)
    duration_minutes = Column(Integer, nullable=True)
    
    # Overall session metrics
    overall_rpe = Column(Float, nullable=True)
    overall_feeling = Column(String(50), nullable=True)  # "great", "good", "okay", "poor"
    
    # Calculated metrics (filled by AI engine)
    total_volume = Column(Float, nullable=True)  # total kg lifted
    estimated_fatigue = Column(Float, nullable=True)
    
    # Deferred fields - only loaded when explicitly needed (CRUD operations)
    notes = deferred(Column(Text, nullable=True))
    created_at = deferred(Column(DateTime, default=datetime.utcnow, nullable=False))
    
    # Relationships
    athlete = relationship("Athlete", back_populates="workout_sessions")
    workout_day = relationship("WorkoutDay", back_populates="workout_sessions")
    exercise_sets = relationship("ExerciseSet", back_populates="workout_session", cascade="all, delete-orphan")
    performance_trend = relationship("PerformanceTrend", back_populates="workout_session", uselist=False, cascade="all, delete-orphan")
    exercise_progressions = relationship("ExerciseProgressionTracking", back_populates="workout_session", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<WorkoutSession(id={self.id}, athlete_id={self.athlete_id}, date={self.session_date})>"


class ExerciseSet(Base):
    """
    Individual set data with performance metrics.
    """
    __tablename__ = "exercise_sets"
    __table_args__ = get_schema_table_args("ai_analysis")
    
    id = Column(Integer, primary_key=True, index=True)
    workout_session_id = Column(Integer, ForeignKey(get_fk_reference("workout_sessions.id", "ai_analysis")), nullable=False)
    exercise_id = Column(Integer, ForeignKey(get_fk_reference("exercises.id")), nullable=False)
    
    # Set information
    set_number = Column(Integer, nullable=False)
    
    # Performance data
    weight = Column(Float, nullable=False)  # in kg
    reps = Column(Integer, nullable=False)
    rpe = Column(Float, nullable=True)  # Rate of Perceived Exertion (6-10 scale)
    rir = Column(Integer, nullable=True)  # Reps in Reserve
    
    # Form and execution
    form_quality = Column(String(50), nullable=True)  # "excellent", "good", "fair", "poor"
    
    # Intensity technique tracking (what was actually performed)
    set_type_used = Column(Enum("straight", "drop_set", "rest_pause", "myo_reps", "cluster_set", "superset_antagonist", "pre_exhaust", name="set_type_enum"), nullable=True)
    rep_style_used = Column(Enum("normal", "lengthened_partials", "tempo_eccentric", "tempo_paused", "eccentric_overload", name="rep_style_enum"), nullable=True)
    technique_details = Column(JSON, nullable=True)  # Execution details for ML analytics
    
    # Deferred fields - only loaded when explicitly needed (CRUD operations)
    notes = deferred(Column(Text, nullable=True))
    created_at = deferred(Column(DateTime, default=datetime.utcnow, nullable=False))
    
    # Relationships
    workout_session = relationship("WorkoutSession", back_populates="exercise_sets")
    exercise = relationship("Exercise")
    
    def __repr__(self):
        return f"<ExerciseSet(id={self.id}, exercise_id={self.exercise_id}, weight={self.weight}, reps={self.reps})>"


