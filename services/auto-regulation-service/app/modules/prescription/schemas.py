"""
Prescription generation schemas.
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from app.utils.constants import ExerciseIntensityCategory, TrainingType


class PrescriptionRequest(BaseModel):
    """Request schema for generating a single prescription."""
    intensity_category: ExerciseIntensityCategory = Field(
        ...,
        description="Exercise intensity category from database"
    )
    training_type: TrainingType = Field(
        ...,
        description="Training goal (strength/hypertrophy/hybrid)"
    )
    training_phase: str = Field(
        ...,
        description="Current training phase (accumulation/intensification/realization/deload)"
    )
    week_in_phase: int = Field(
        ...,
        ge=1,
        le=12,
        description="Week number within the phase (typically 1-4)"
    )
    is_primary: bool = Field(
        True,
        description="Whether this is a primary exercise (affects rest period)"
    )


class PrescriptionResponse(BaseModel):
    """Response schema for prescription generation."""
    target_rpe: float = Field(
        ...,
        ge=5.0,
        le=10.0,
        description="Target Rate of Perceived Exertion (5.0-10.0)"
    )
    target_rir: int = Field(
        ...,
        ge=0,
        le=5,
        description="Target Reps in Reserve (0-5)"
    )
    rest_period_seconds: int = Field(
        ...,
        ge=60,
        le=300,
        description="Rest period between sets in seconds"
    )


class BatchPrescriptionRequest(BaseModel):
    """Request schema for generating multiple prescriptions at once."""
    prescriptions: List[PrescriptionRequest] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="List of prescription requests"
    )


class BatchPrescriptionResponse(BaseModel):
    """Response schema for batch prescription generation."""
    prescriptions: List[PrescriptionResponse] = Field(
        ...,
        description="List of generated prescriptions"
    )


