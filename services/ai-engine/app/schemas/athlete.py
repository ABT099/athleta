"""
Pydantic schemas for athlete-related requests and responses.
"""
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional

from app.utils.constants import TrainingExperience, Gender


class AthleteBase(BaseModel):
    """Base athlete schema."""
    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    age: int = Field(..., ge=13, le=100)
    gender: Gender
    training_experience: TrainingExperience


class AthleteCreate(AthleteBase):
    """Schema for creating a new athlete."""
    injury_history: Optional[str] = None


class AthleteUpdate(BaseModel):
    """Schema for updating athlete information."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    age: Optional[int] = Field(None, ge=13, le=100)
    training_experience: Optional[TrainingExperience] = None
    injury_history: Optional[str] = None


class AthleteResponse(AthleteBase):
    """Schema for athlete response."""
    id: int
    injury_history: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class AthleteProgressSummary(BaseModel):
    """Summary of athlete's training progress."""
    athlete_id: int
    total_workouts: int
    total_volume_lifted: float
    average_rpe: float
    current_week: int
    current_phase: str
    strength_improvements: dict
    volume_progression: dict


