"""
Pydantic schemas for request/response validation.
"""
from app.schemas.athlete import (
    AthleteCreate,
    AthleteUpdate,
    AthleteResponse,
    AthleteProgressSummary,
)
from app.schemas.workout import (
    ExerciseCreate,
    ExerciseResponse,
    WorkoutPlanCreate,
    WorkoutPlanResponse,
    PlanEntryResponse,
    ExerciseSetData,
    ExerciseSetResponse,
    RecoveryMetricsData,
    RecoveryMetricsResponse,
    WorkoutCompletionRequest,
    WorkoutSessionResponse,
    WorkoutDayExerciseCreate,
    WorkoutDayExerciseResponse,
    WorkoutDayCreate,
    WorkoutDayResponse,
    NextWorkoutResponse,
    WorkoutCompletionResponse,
)
from app.schemas.responses import (
    ErrorResponse,
    SuccessResponse,
    HealthResponse,
)

__all__ = [
    "AthleteCreate",
    "AthleteUpdate",
    "AthleteResponse",
    "AthleteProgressSummary",
    "ExerciseCreate",
    "ExerciseResponse",
    "WorkoutPlanCreate",
    "WorkoutPlanResponse",
    "PlanEntryResponse",
    "ExerciseSetData",
    "ExerciseSetResponse",
    "RecoveryMetricsData",
    "RecoveryMetricsResponse",
    "WorkoutCompletionRequest",
    "WorkoutSessionResponse",
    "WorkoutDayExerciseCreate",
    "WorkoutDayExerciseResponse",
    "WorkoutDayCreate",
    "WorkoutDayResponse",
    "NextWorkoutResponse",
    "WorkoutCompletionResponse",
    "ErrorResponse",
    "SuccessResponse",
    "HealthResponse",
]


