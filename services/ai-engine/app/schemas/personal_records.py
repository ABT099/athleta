"""
Pydantic schemas for Personal Record (PR) tracking.
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional, Dict


class PRRecord(BaseModel):
    """Schema for a single PR record."""
    exercise_id: int
    rep_max: int = Field(..., description="Rep range: 1, 3, 5, 8, 10, or 12")
    weight: float
    date: datetime


class PRUpdate(BaseModel):
    """Schema for PR update notification."""
    exercise_id: int
    exercise_name: Optional[str] = None
    pr_type: str = Field(..., description="Type: '1RM', '5RM', 'volume', 'total_reps'")
    old_value: Optional[float] = None
    new_value: float
    improvement: float = Field(..., description="Improvement in kg or reps")
    reps: Optional[int] = None
    is_new_pr: bool = True


class PRSummaryResponse(BaseModel):
    """Schema for PR summary response."""
    exercise_id: int
    exercise_name: str
    all_time_records: Dict[str, Optional[PRRecord]] = Field(
        default_factory=dict,
        description="All PRs: '1RM', '3RM', '5RM', '8RM', '10RM', '12RM'"
    )
    recent_prs: List[PRUpdate] = Field(default_factory=list)
    weeks_since_last_pr: Optional[float] = None
    is_plateaued: bool = False
    total_pr_count: int = 0


class PRComparisonResponse(BaseModel):
    """Schema for PR comparison in performance analysis."""
    is_pr: bool = False
    diff_kg: Optional[float] = None
    weeks_since: Optional[float] = None
    pr_trend: str = Field(..., description="'improving', 'maintaining', 'slight_regression', 'regressing', 'unknown'")
    pr_weight: Optional[float] = None
    pr_reps: Optional[int] = None

