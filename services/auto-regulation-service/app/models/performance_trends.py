"""
Performance trends tracking model (auto-regulation-owned, algo state).

Denormalises the per-session signal the engine needs for history — total volume,
intensity, ACWR/load, readiness — so analysis reads it locally instead of
re-querying api-owned sessions/sets. References to api rows (athlete_id,
workout_session_id) are soft integer references; there are no cross-service FKs.
"""
from sqlalchemy import Column, Integer, Float, DateTime, Text, Boolean, Index
from datetime import datetime, timezone

from app.database import AutoregBase, get_schema_table_args


class PerformanceTrend(AutoregBase):
    """
    Track performance trends for autoregulated deloads.
    """
    __tablename__ = "performance_trends"
    __table_args__ = (
        Index('idx_performance_trend_athlete_date', 'athlete_id', 'session_date'),
        get_schema_table_args("ai_analysis")
    )

    id = Column(Integer, primary_key=True, index=True)
    athlete_id = Column(Integer, nullable=False, index=True)  # soft ref → api athletes.id
    workout_session_id = Column(Integer, nullable=False)  # soft ref → api workout_sessions.id
    session_date = Column(DateTime, nullable=False, index=True)

    # Performance metrics
    total_volume = Column(Float, nullable=False)
    average_intensity = Column(Float, nullable=False)
    average_rpe = Column(Float, nullable=False)
    readiness_score = Column(Float, nullable=False)
    performance_score = Column(Float, nullable=False)
    fatigue_index = Column(Float, nullable=False)
    volume_load = Column(Float, nullable=False)

    # Training load metrics
    training_monotony = Column(Float, nullable=True)
    training_strain = Column(Float, nullable=True)
    acute_load = Column(Float, nullable=True)
    chronic_load = Column(Float, nullable=True)
    acwr = Column(Float, nullable=True)

    # Denormalised per-session signal so history reads stay local (raw
    # sessions/sets are api-owned and no longer queryable from this service):
    #   cns_load          — systemic load computed from the session's sets
    #   duration_minutes  — session duration, for the sRPE (RPE x duration) check
    cns_load = Column(Float, nullable=True)
    duration_minutes = Column(Integer, nullable=True)

    # Deload tracking
    deload_triggered = Column(Boolean, nullable=False, default=False)
    deload_reason = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    def __repr__(self):
        return f"<PerformanceTrend(athlete_id={self.athlete_id}, date={self.session_date}, performance={self.performance_score})>"
