"""
Periodization API endpoints.
"""
from fastapi import APIRouter

from app.schemas.workout import PeriodizationRequest, PeriodizationResponse
from app.services.periodization import PeriodizationService


router = APIRouter()


@router.post("/periodization/recommend", response_model=PeriodizationResponse)
def recommend_periodization(request: PeriodizationRequest):
    """
    Recommend optimal periodization model based on athlete characteristics.
    
    This endpoint uses the calculate_optimal_periodization function to determine
    the best periodization approach (linear, undulating, or block) based on:
    - Training type (hypertrophy, strength, hybrid)
    - Training experience (beginner, intermediate, advanced)
    - Training frequency (workouts per week)
    """
    periodization_model = PeriodizationService.calculate_optimal_periodization(
        training_type=request.training_type,
        experience=request.experience,
        training_frequency=request.training_frequency
    )
    
    return PeriodizationResponse(
        periodization_model=periodization_model
    )

