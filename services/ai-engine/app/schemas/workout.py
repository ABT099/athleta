"""
Pydantic schemas for workout-related requests and responses.
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional, Dict

from app.utils.constants import (
    TrainingType, 
    PeriodizationModel, 
    TrainingPhase,
    SleepQuality
)


# ============ Exercise Schemas ============

class ExerciseBase(BaseModel):
    """Base exercise schema."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    equipment: Optional[str] = None
    difficulty: Optional[str] = None
    primary_muscles: List[str]
    secondary_muscles: Optional[List[str]] = None
    injury_risk_level: float = Field(default=1.0, ge=1.0, le=3.0)
    joint_stress_areas: Optional[List[str]] = None
    movement_pattern: Optional[str] = None
    is_compound: bool = True


class ExerciseCreate(ExerciseBase):
    """Schema for creating a new exercise."""
    pass


class ExerciseResponse(ExerciseBase):
    """Schema for exercise response."""
    id: int
    
    class Config:
        from_attributes = True


# ============ Workout Plan Schemas ============

class WorkoutPlanBase(BaseModel):
    """Base workout plan schema."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    training_type: TrainingType
    periodization_model: PeriodizationModel
    frequency: int = Field(..., ge=1, le=7)
    duration_weeks: int = Field(..., ge=1, le=52)
    split_type: Optional[str] = None


class WorkoutPlanCreate(WorkoutPlanBase):
    """Schema for creating a workout plan."""
    athlete_id: int
    start_date: datetime


class WorkoutPlanResponse(WorkoutPlanBase):
    """Schema for workout plan response."""
    id: int
    athlete_id: int
    start_date: datetime
    end_date: Optional[datetime]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# ============ Plan Entry Schemas ============

class PlanEntryResponse(BaseModel):
    """Schema for plan entry response."""
    id: int
    workout_plan_id: int
    week_number: int
    start_date: datetime
    end_date: datetime
    training_phase: TrainingPhase
    target_volume_multiplier: float
    target_intensity_multiplier: float
    is_deload_week: bool
    ai_adjustments: Optional[Dict] = None
    completed_workouts: int
    average_rpe: Optional[float]
    average_recovery_score: Optional[float]
    total_volume: Optional[float]
    notes: Optional[str]
    
    class Config:
        from_attributes = True


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
    tempo_adherence: Optional[str] = None
    notes: Optional[str] = None


class ExerciseSetResponse(BaseModel):
    """Schema for exercise set response."""
    id: int
    exercise_id: int
    set_number: int
    weight: float
    reps: int
    rpe: Optional[float]
    rir: Optional[int]
    form_quality: Optional[str]
    tempo_adherence: Optional[str]
    notes: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


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
    
    class Config:
        from_attributes = True


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
    
    class Config:
        from_attributes = True


# ============ Workout Day Exercise Schemas ============

class WorkoutDayExerciseBase(BaseModel):
    """Base schema for workout day exercise."""
    exercise_id: int
    order_in_workout: int
    target_sets: int = Field(..., ge=1, le=20)
    target_reps_min: int = Field(..., ge=1)
    target_reps_max: int = Field(..., ge=1)
    target_rpe: Optional[float] = Field(None, ge=1, le=10)
    target_rir: Optional[int] = Field(None, ge=0, le=10)
    rest_period_seconds: Optional[int] = Field(None, ge=0)
    tempo: Optional[str] = None
    notes: Optional[str] = None
    is_primary: bool = True
    progression_scheme: Optional[str] = None


class WorkoutDayExerciseCreate(WorkoutDayExerciseBase):
    """Schema for creating workout day exercise."""
    pass


class WorkoutDayExerciseResponse(WorkoutDayExerciseBase):
    """Schema for workout day exercise response with adjusted parameters."""
    id: int
    workout_day_id: int
    
    # AI-adjusted parameters (returned from next workout endpoint)
    adjusted_weight: Optional[float] = None
    adjusted_sets: Optional[int] = None
    adjusted_reps_min: Optional[int] = None
    adjusted_reps_max: Optional[int] = None
    adjustment_reason: Optional[str] = None
    
    class Config:
        from_attributes = True


# ============ Workout Day Schemas ============

class WorkoutDayBase(BaseModel):
    """Base workout day schema."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    day_of_week: Optional[int] = Field(None, ge=0, le=6)
    order_in_week: int = Field(..., ge=1, le=7)
    target_muscle_groups: List[str]


class WorkoutDayCreate(WorkoutDayBase):
    """Schema for creating workout day."""
    workout_plan_id: int
    exercises: List[WorkoutDayExerciseCreate]


class WorkoutDayResponse(WorkoutDayBase):
    """Schema for workout day response."""
    id: int
    workout_plan_id: int
    exercises: List[WorkoutDayExerciseResponse]
    created_at: datetime
    
    class Config:
        from_attributes = True


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

