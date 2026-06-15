"""
Per-session per-muscle volume log (auto-regulation-owned, algo state).

Denormalises each completed session's effective sets and volume load per muscle
(weighted by muscle-activation role) at analyse time, so weekly volume-landmark
math (MEV/MAV/MRV) reads locally instead of re-aggregating api-owned sets across
sessions. athlete_id / workout_session_id are soft integer references.
"""
from sqlalchemy import Column, Integer, Float, String, DateTime, Index
from datetime import datetime, timezone

from app.database import AutoregBase, get_schema_table_args


class MuscleVolumeLog(AutoregBase):
    __tablename__ = "muscle_volume_log"
    __table_args__ = (
        Index('idx_muscle_volume_athlete_muscle_date', 'athlete_id', 'muscle_name', 'session_date'),
        get_schema_table_args("ai_analysis"),
    )

    id = Column(Integer, primary_key=True, index=True)
    athlete_id = Column(Integer, nullable=False, index=True)  # soft ref → api athletes.id
    workout_session_id = Column(Integer, nullable=False)  # soft ref → api workout_sessions.id
    session_date = Column(DateTime, nullable=False, index=True)

    muscle_name = Column(String(50), nullable=False)
    effective_sets = Column(Float, nullable=False, default=0.0)
    volume_load = Column(Float, nullable=False, default=0.0)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    def __repr__(self):
        return f"<MuscleVolumeLog(athlete_id={self.athlete_id}, muscle={self.muscle_name}, sets={self.effective_sets})>"
