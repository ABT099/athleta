"""
Workout prescription history (auto-regulation-owned, algo state).

Records what the AI prescribed for each exercise over time (vs what the athlete
actually did, in ExerciseProgressionTracking). athlete_id / workout_day_id /
exercise_id are soft integer references.
"""
from sqlalchemy import Column, Integer, Float, DateTime, String, Text, JSON, Index
from datetime import datetime, timezone

from app.database import AutoregBase, get_schema_table_args


class WorkoutPrescriptionHistory(AutoregBase):
    """
    Track AI prescription changes over time.

    Complements ExerciseProgressionTracking:
    - ExerciseProgressionTracking: What the user ACTUALLY did
    - WorkoutPrescriptionHistory: What the AI RECOMMENDED they do
    """
    __tablename__ = "workout_prescription_history"
    __table_args__ = (
        Index(
            'idx_athlete_workout_exercise_date',
            'athlete_id', 'workout_day_id', 'exercise_id', 'prescribed_date'
        ),
        Index('idx_athlete_exercise', 'athlete_id', 'exercise_id'),
        get_schema_table_args("ai_analysis")
    )

    id = Column(Integer, primary_key=True, index=True)
    athlete_id = Column(Integer, nullable=False, index=True)  # soft ref → api athletes.id
    workout_day_id = Column(Integer, nullable=False, index=True)  # soft ref → api workout_days.id
    exercise_id = Column(Integer, nullable=False, index=True)  # soft ref → exercise-service
    prescribed_date = Column(DateTime, nullable=False, index=True)

    # What AI prescribed
    prescribed_weight = Column(Float, nullable=True)
    prescribed_sets = Column(Integer, nullable=True)
    prescribed_reps_min = Column(Integer, nullable=True)
    prescribed_reps_max = Column(Integer, nullable=True)
    prescribed_rpe = Column(Float, nullable=True)
    prescribed_rir = Column(Integer, nullable=True)
    rest_period_seconds = Column(Integer, nullable=True)

    # Intensity techniques
    set_type = Column(String(50), nullable=True)
    rep_style = Column(String(50), nullable=True)
    set_type_params = Column(JSON, nullable=True)
    rep_style_params = Column(JSON, nullable=True)

    # Why it was prescribed (AI context)
    volume_multiplier = Column(Float, nullable=False)
    intensity_multiplier = Column(Float, nullable=False)
    adjustment_reason = Column(Text, nullable=True)

    # Context when prescribed
    week_number = Column(Integer, nullable=True)
    readiness_score = Column(Float, nullable=True)
    training_phase = Column(String(50), nullable=True)

    # Metadata
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    def __repr__(self):
        return f"<WorkoutPrescriptionHistory(athlete_id={self.athlete_id}, exercise_id={self.exercise_id}, date={self.prescribed_date})>"
