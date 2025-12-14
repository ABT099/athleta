"""
Pydantic schemas for plan analyzer API.
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class PlanDraftAnalysisRequest(BaseModel):
    """Request schema for plan draft analysis."""
    plan_data: Dict[str, Any] = Field(..., description="Plan data dict with workout days, exercises, etc.")
    athlete_id: Optional[int] = Field(None, description="Optional athlete ID for personalized analysis")


class AnalysisWarning(BaseModel):
    """Critical issue that should be addressed."""
    severity: str = Field(..., description="Severity: critical, high, medium, low")
    category: str = Field(..., description="Category: volume, balance, order, recovery, prescription, duration, periodization")
    message: str = Field(..., description="Warning message")
    affected_items: List[str] = Field(default_factory=list, description="List of affected items (exercise names, muscle groups, etc.)")
    recommendation: str = Field(..., description="Recommended action")


class AnalysisSuggestion(BaseModel):
    """Optimization opportunity."""
    category: str = Field(..., description="Category: volume, balance, order, recovery, prescription, duration, periodization")
    message: str = Field(..., description="Suggestion message")
    impact: str = Field(..., description="Impact: high, medium, low")
    action: str = Field(..., description="Recommended action")


class PlanAnalysisDetails(BaseModel):
    """Detailed analysis breakdown."""
    volume_distribution: Dict[str, Any]
    muscle_group_balance: Dict[str, Any]
    exercise_order: Dict[str, Any]
    recovery_windows: Dict[str, Any]
    prescription_quality: Dict[str, Any]
    workout_duration: Dict[str, Any]


class MLRecommendation(BaseModel):
    """ML-based recommendation."""
    volume_multiplier: float = Field(..., description="Suggested volume multiplier")
    intensity_multiplier: float = Field(..., description="Suggested intensity multiplier")
    confidence: str = Field(..., description="Confidence level: high, medium, low")
    based_on_sessions: int = Field(..., description="Number of sessions used for prediction")
    recommendation: str = Field(..., description="Human-readable recommendation")


class PlanAnalysisResponse(BaseModel):
    """Response schema from plan analysis."""
    overall_score: float = Field(..., ge=0, le=100, description="Overall plan quality score (0-100)")
    warnings: List[AnalysisWarning] = Field(default_factory=list, description="Critical issues")
    suggestions: List[AnalysisSuggestion] = Field(default_factory=list, description="Optimization opportunities")
    strengths: List[str] = Field(default_factory=list, description="What's working well")
    analysis: PlanAnalysisDetails = Field(..., description="Detailed analysis breakdown")
    auto_suggestions: Dict[str, Any] = Field(default_factory=dict, description="Auto-generated prescription suggestions")
    ml_recommendations: Optional[MLRecommendation] = Field(None, description="ML-based recommendations (if available)")
    personalized_notes: List[str] = Field(default_factory=list, description="Personalized notes based on athlete history")
    periodization_validation: Dict[str, Any] = Field(..., description="Periodization validation results")
    total_workouts: int = Field(..., description="Total number of workout days")
    total_exercises: int = Field(..., description="Total number of exercises")
    estimated_weekly_volume: float = Field(..., description="Estimated weekly volume (sets)")
    estimated_workout_duration_minutes: float = Field(..., description="Average estimated workout duration in minutes")



