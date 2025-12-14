"""
Form quality tracking models.

Tracks form quality trends per exercise per athlete to enable
data-driven form degradation detection and progressive overload gating.
"""
from sqlalchemy import Column, Integer, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database import Base, get_schema_table_args, get_fk_reference


class FormQualityTrend(Base):
    """
    Track form quality trends per exercise per athlete.
    
    Used to:
    - Detect form degradation within sessions (set 1 vs final sets)
    - Identify chronic form issues across multiple sessions
    - Gate progressive overload decisions based on form quality
    - Generate form quality alerts and recommendations
    """
    __tablename__ = "form_quality_trends"
    __table_args__ = get_schema_table_args("ai_analysis")
    
    id = Column(Integer, primary_key=True, index=True)
    athlete_id = Column(Integer, ForeignKey(get_fk_reference("athletes.id")), nullable=False)
    exercise_id = Column(Integer, ForeignKey(get_fk_reference("exercises.id")), nullable=False)
    date = Column(DateTime, nullable=False, index=True)
    
    # Average form score for this exercise on this date
    # 1.0 = excellent, 0.75 = good, 0.5 = fair, 0.25 = poor
    average_form_score = Column(Float, nullable=False)
    
    # Number of sets analyzed
    sets_analyzed = Column(Integer, nullable=False)
    
    # Form degradation rate within the session
    # Positive = form degraded (first sets better than last sets)
    # Negative = form improved (first sets worse than last sets)
    # 0.0 = no degradation
    degradation_rate = Column(Float, nullable=True)
    
    # Count of sets with high RPE (9+) and poor form
    # This combination significantly increases injury risk
    high_rpe_poor_form_count = Column(Integer, nullable=False, default=0)
    
    # Relationships
    athlete = relationship("Athlete")
    exercise = relationship("Exercise")
    
    def __repr__(self):
        return f"<FormQualityTrend(id={self.id}, athlete_id={self.athlete_id}, exercise_id={self.exercise_id}, score={self.average_form_score})>"



