"""
Pydantic schemas for workout-related requests and responses.
"""
from pydantic import BaseModel, Field, model_validator, ConfigDict
from datetime import datetime
from typing import List, Optional, Dict

from app.utils.constants import (
    TrainingType, 
    TrainingExperience,
    PeriodizationModel,
    SleepQuality,
    SetType,
    RepStyle
)


# ============ Exercise Set Schemas ============

class ExerciseSetData(BaseModel):
    """Schema for individual set data in workout completion."""
    exercise_id: int
    set_number: int
    weight: float = Field(..., ge=0)
    reps: int = Field(..., ge=0)
    rpe: Optional[float] = Field(None, ge=1, le=10)
    rir: Optional[int] = Field(None, ge=0, le=10)
    form_quality: Optional[str] = None  # "excellent", "good", "fair", "poor"
    set_type_used: Optional[SetType] = None  # Intensity technique actually performed
    rep_style_used: Optional[RepStyle] = None
    technique_details: Optional[Dict] = None  # Execution details for ML analytics
    notes: Optional[str] = None


# ============ Recovery Schemas ============

class RecoveryMetricsData(BaseModel):
    """Schema for recovery metrics in workout completion."""
    sleep_quality: SleepQuality
    sleep_hours: Optional[float] = Field(None, ge=0, le=24)
    overall_soreness: Optional[int] = Field(None, ge=1, le=10)
    muscle_soreness: Optional[Dict[str, int]] = None
    stress_level: Optional[int] = Field(None, ge=1, le=10)
    energy_level: Optional[int] = Field(None, ge=1, le=10)
    nutrition_adherence: Optional[str] = None
    hydration_level: Optional[str] = None
    notes: Optional[str] = None


class RecoveryMetricsResponse(BaseModel):
    """Schema for recovery metrics response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    athlete_id: int
    date: datetime
    sleep_quality: SleepQuality
    sleep_hours: Optional[float]
    overall_soreness: Optional[int]
    stress_level: Optional[int]
    energy_level: Optional[int]
    readiness_score: Optional[float]
    nutrition_adherence: Optional[str]
    hydration_level: Optional[str]


# ============ Workout Session Schemas ============

class WorkoutCompletionRequest(BaseModel):
    """Schema for completing a workout session."""
    athlete_id: int
    workout_day_id: int
    session_date: datetime
    duration_minutes: Optional[int] = Field(None, ge=0)
    exercise_sets: List[ExerciseSetData]
    recovery_metrics: RecoveryMetricsData
    overall_rpe: Optional[float] = Field(None, ge=1, le=10)
    overall_feeling: Optional[str] = None
    notes: Optional[str] = None


class WorkoutSessionResponse(BaseModel):
    """Schema for workout session response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    athlete_id: int
    workout_day_id: int
    session_date: datetime
    duration_minutes: Optional[int]
    overall_rpe: Optional[float]
    overall_feeling: Optional[str]
    total_volume: Optional[float]
    estimated_fatigue: Optional[float]
    notes: Optional[str]
    created_at: datetime


# ============ Warm-up Set Schemas ============

class WarmupSetSchema(BaseModel):
    """Schema for a warm-up set."""
    set_number: int = Field(..., ge=1)
    weight_percentage: float = Field(..., ge=0, le=1)
    weight: Optional[float] = Field(None, ge=0)  # Calculated weight in kg
    reps_min: int = Field(..., ge=1)
    reps_max: int = Field(..., ge=1)
    is_warmup: bool = True


# ============ Workout Day Exercise Schemas ============

class WorkoutDayExerciseBase(BaseModel):
    """Base schema for workout day exercise."""
    exercise_id: int
    order_in_workout: int
    target_sets_min: int = Field(..., ge=1, le=20)
    target_sets_max: int = Field(..., ge=1, le=20)
    target_reps_min: int = Field(..., ge=1)
    target_reps_max: int = Field(..., ge=1)
    target_rpe: Optional[float] = Field(None, ge=1, le=10)
    target_rir: Optional[int] = Field(None, ge=0, le=10)
    rest_period_seconds: Optional[int] = Field(None, ge=0)
    tempo: Optional[str] = None
    notes: Optional[str] = None
    is_primary: bool = True
    progression_scheme: Optional[str] = None
    warm_up_sets: int = Field(0, ge=0, le=4)  # Number of warm-up sets (0-4)
    set_type: Optional[SetType] = SetType.STRAIGHT  # Intensity technique set type
    rep_style: Optional[RepStyle] = RepStyle.NORMAL  # Intensity technique rep style
    set_type_params: Optional[Dict] = None  # Technique-specific parameters
    rep_style_params: Optional[Dict] = None  # Rep style-specific parameters
    
    @model_validator(mode='after')
    def validate_set_range(self):
        """Ensure target_sets_max >= target_sets_min."""
        if self.target_sets_max < self.target_sets_min:
            raise ValueError(f"target_sets_max ({self.target_sets_max}) must be >= target_sets_min ({self.target_sets_min})")
        return self


class WorkoutDayExerciseCreate(WorkoutDayExerciseBase):
    """Schema for creating workout day exercise."""
    pass


class WorkoutDayExerciseResponse(WorkoutDayExerciseBase):
    """Schema for workout day exercise response with adjusted parameters."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    workout_day_id: int
    
    # AI-adjusted parameters (returned from next workout endpoint)
    adjusted_weight: Optional[float] = None
    adjusted_sets: Optional[int] = None
    adjusted_reps_min: Optional[int] = None
    adjusted_reps_max: Optional[int] = None
    adjustment_reason: Optional[str] = None
    
    # Warm-up sets (always generated when adjusted_weight is available)
    warmup_sets: Optional[List[WarmupSetSchema]] = None


# ============ Workout Day Schemas ============

class WorkoutDayBase(BaseModel):
    """Base workout day schema."""
    name: str = Field(..., min_length=1, max_length=255)
    day_of_week: Optional[int] = Field(None, ge=0, le=6)
    order_in_week: int = Field(..., ge=1, le=7)


class WorkoutDayResponse(WorkoutDayBase):
    """Schema for workout day response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    workout_plan_id: int
    exercises: List[WorkoutDayExerciseResponse]
    created_at: datetime


# ============ AI Response Schemas ============

class NextWorkoutResponse(BaseModel):
    """Response with next workout parameters adjusted by AI."""
    workout_day: WorkoutDayResponse
    adjustments_summary: Dict
    injury_warnings: List[str]
    recovery_recommendations: List[str]
    weekly_progress: Dict


class WorkoutCompletionResponse(BaseModel):
    """Response after completing a workout."""
    workout_session: WorkoutSessionResponse
    recovery_metrics: RecoveryMetricsResponse
    next_workout: NextWorkoutResponse
    performance_analysis: Dict
    ai_insights: List[str]


# ============ Periodization Schemas ============

class PeriodizationRequest(BaseModel):
    """Schema for periodization recommendation request."""
    training_type: TrainingType
    experience: TrainingExperience
    training_frequency: int = Field(..., ge=1, le=7, description="Workouts per week")


class PeriodizationResponse(BaseModel):
    """Schema for periodization recommendation response."""
    periodization_model: PeriodizationModel


# ============ Plan Configuration Schemas ============

class PlanConfigRequest(BaseModel):
    """Schema for workout plan configuration recommendation request."""
    training_type: TrainingType
    experience: TrainingExperience
    training_frequency: int = Field(..., ge=1, le=7, description="Workouts per week")


class PlanConfigResponse(BaseModel):
    """Schema for workout plan configuration recommendation response."""
    periodization_model: PeriodizationModel
    duration_weeks_recommended: int = Field(..., ge=1, le=52, description="Recommended duration in weeks")
    reasoning: str = Field(..., description="Explanation of the recommendations")

