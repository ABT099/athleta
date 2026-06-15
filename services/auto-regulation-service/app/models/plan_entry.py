"""
Weekly plan entry (auto-regulation-owned, algo state).

Tracks the AI's weekly volume/intensity adjustments and per-week performance
summary for a plan. workout_plan_id is a soft integer reference to the api-owned
workout_plans row.
"""
from sqlalchemy import Column, Integer, Float, DateTime, Enum, Text, JSON
from datetime import datetime, timezone

from app.database import AutoregBase, get_schema_table_args
from app.utils.constants import TrainingPhase


class PlanEntry(AutoregBase):
    """
    Weekly plan entry — weekly adjustments and progression, updated by the AI
    engine based on athlete performance.
    """
    __tablename__ = "plan_entries"
    __table_args__ = get_schema_table_args("ai_analysis")

    id = Column(Integer, primary_key=True, index=True)
    workout_plan_id = Column(Integer, nullable=False, index=True)  # soft ref → api workout_plans.id

    # Week tracking
    week_number = Column(Integer, nullable=False)  # week within the mesocycle
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)

    # Phase information (can change week to week in undulating periodization)
    training_phase = Column(Enum(TrainingPhase), nullable=False)

    # Volume and intensity targets for this week (relative to baseline)
    target_volume_multiplier = Column(Float, default=1.0, nullable=False)
    target_intensity_multiplier = Column(Float, default=1.0, nullable=False)

    # Deload flag (1 = deload, 0 = normal)
    is_deload_week = Column(Integer, default=0, nullable=False)

    # AI adjustments (JSON field storing modifications)
    ai_adjustments = Column(JSON, nullable=True)

    # Performance summary for the week
    completed_workouts = Column(Integer, default=0, nullable=False)
    average_rpe = Column(Float, nullable=True)
    average_recovery_score = Column(Float, nullable=True)
    total_volume = Column(Float, nullable=True)  # kg lifted

    notes = Column(Text, nullable=True)

    def __repr__(self):
        return f"<PlanEntry(id={self.id}, week={self.week_number}, phase={self.training_phase})>"
