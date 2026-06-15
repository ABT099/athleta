"""
Per-session per-joint stress log (auto-regulation-owned, algo state).

Denormalises each completed session's weighted joint-stress scores (volume-load x
RPE-factor x injury-risk-factor, distributed across each exercise's stressed
joints) at analyse time, so the weighted-joint-stress profile reads locally
instead of re-aggregating api-owned sets. This also backs the api-facing
joint-stress-profile endpoint. athlete_id / workout_session_id are soft refs.
"""
from sqlalchemy import Column, Integer, Float, String, DateTime, Index
from datetime import datetime, timezone

from app.database import AutoregBase, get_schema_table_args


class JointStressLog(AutoregBase):
    __tablename__ = "joint_stress_log"
    __table_args__ = (
        Index('idx_joint_stress_athlete_joint_date', 'athlete_id', 'joint_name', 'session_date'),
        get_schema_table_args("ai_analysis"),
    )

    id = Column(Integer, primary_key=True, index=True)
    athlete_id = Column(Integer, nullable=False, index=True)  # soft ref → api athletes.id
    workout_session_id = Column(Integer, nullable=False)  # soft ref → api workout_sessions.id
    session_date = Column(DateTime, nullable=False, index=True)

    joint_name = Column(String(50), nullable=False)
    stress_score = Column(Float, nullable=False, default=0.0)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    def __repr__(self):
        return f"<JointStressLog(athlete_id={self.athlete_id}, joint={self.joint_name}, score={self.stress_score})>"
