"""
RPE calibration tracking model (auto-regulation-owned, algo state).

athlete_id / exercise_id are soft integer references.
"""
from sqlalchemy import Column, Integer, Float, DateTime
from datetime import datetime, timezone

from app.database import AutoregBase, get_schema_table_args


class AthleteRPECalibration(AutoregBase):
    """
    Track RPE accuracy and calibration for each athlete-exercise combination.
    """
    __tablename__ = "athlete_rpe_calibration"
    __table_args__ = get_schema_table_args("ai_analysis")

    id = Column(Integer, primary_key=True, index=True)
    athlete_id = Column(Integer, nullable=False, index=True)  # soft ref → api athletes.id
    exercise_id = Column(Integer, nullable=False)  # soft ref → exercise-service

    # RPE data
    reported_rpe = Column(Float, nullable=False)
    predicted_rir = Column(Float, nullable=False)
    actual_rir = Column(Float, nullable=True)

    # Performance data
    weight_used = Column(Float, nullable=False)
    reps_completed = Column(Integer, nullable=False)
    session_date = Column(DateTime, nullable=False)

    # Calibration metrics
    calibration_accuracy = Column(Float, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    def __repr__(self):
        return f"<AthleteRPECalibration(athlete_id={self.athlete_id}, exercise_id={self.exercise_id}, rpe={self.reported_rpe})>"
