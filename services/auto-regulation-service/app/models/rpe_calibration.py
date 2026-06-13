"""
RPE calibration tracking models.
"""
from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from autoregulation.database import Base, get_schema_table_args, get_fk_reference


class AthleteRPECalibration(Base):
    """
    Track RPE accuracy and calibration for each athlete-exercise combination.
    """
    __tablename__ = "athlete_rpe_calibration"
    __table_args__ = get_schema_table_args("ai_analysis")
    
    id = Column(Integer, primary_key=True, index=True)
    athlete_id = Column(Integer, ForeignKey(get_fk_reference("athletes.id"), ondelete="CASCADE"), nullable=False, index=True)
    exercise_id = Column(Integer, ForeignKey(get_fk_reference("exercises.id"), ondelete="CASCADE"), nullable=False)
    
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
    
    # Relationships
    athlete = relationship("Athlete", back_populates="rpe_calibrations")
    exercise = relationship("Exercise", back_populates="rpe_calibrations")
    
    def __repr__(self):
        return f"<AthleteRPECalibration(athlete_id={self.athlete_id}, exercise_id={self.exercise_id}, rpe={self.reported_rpe})>"

