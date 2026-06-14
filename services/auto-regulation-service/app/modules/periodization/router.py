"""
Workout plan configuration API endpoints.
"""
from fastapi import APIRouter

from app.schemas.workout import PlanConfigRequest, PlanConfigResponse
from app.modules.periodization.service import PeriodizationService
from app.utils.constants import PeriodizationModel


router = APIRouter()


@router.post("/plan/recommend-config", response_model=PlanConfigResponse)
def recommend_plan_config(request: PlanConfigRequest):
    """
    Recommend workout plan configuration including periodization model and duration.
    
    This endpoint provides a unified recommendation for:
    - Periodization model (linear, undulating, or block)
    - Recommended duration in weeks
    
    Training age is estimated from experience level internally.
    
    Based on scientific research:
    - Schoenfeld et al. (2017): Volume landmarks and mesocycle length
    - Issurin (2010): Block periodization for sports training
    - Kiely (2012): Periodization theory
    """
    # Calculate optimal periodization model (training age estimated internally from experience)
    periodization_model = PeriodizationService.calculate_optimal_periodization(
        training_type=request.training_type,
        experience=request.experience,
        training_frequency=request.training_frequency,
        training_age_years=None  # Will be estimated from experience
    )
    
    # Calculate duration range based on all factors
    min_weeks, max_weeks = PeriodizationService.recommend_plan_duration(
        training_type=request.training_type,
        experience=request.experience,
        periodization_model=periodization_model,
        frequency=request.training_frequency
    )
    
    # Calculate recommended duration (middle of range, rounded)
    recommended_weeks = round((min_weeks + max_weeks) / 2)
    
    # Generate reasoning
    reasoning_parts = []
   
    reasoning_parts.append(f"Recommended duration: {recommended_weeks} weeks")
    reasoning_parts.append(f"based on {request.experience.value} experience level")
    reasoning_parts.append(f"{request.training_type.value} training goals")
    reasoning_parts.append(f"and {request.training_frequency} workouts per week")
    
    reasoning = ". ".join(reasoning_parts) + "."
    
    return PlanConfigResponse(
        periodization_model=periodization_model,
        duration_weeks_recommended=recommended_weeks,
        reasoning=reasoning
    )

