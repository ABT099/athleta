"""
POST endpoint for plan analysis.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.plan_analyzer import PlanAnalyzerService
from app.schemas.plan_analyzer import PlanDraftAnalysisRequest, PlanAnalysisResponse


router = APIRouter()


@router.post("/plan-analyzer", response_model=PlanAnalysisResponse)
def analyze_plan(
    request: PlanDraftAnalysisRequest,
    db: Session = Depends(get_db)
):
    """
    Analyze a plan draft and return comprehensive feedback.
    
    This endpoint accepts a complete plan (not yet saved to DB) and returns
    analysis results including warnings, suggestions, and quality scores.
    
    Args:
        request: Plan draft analysis request containing plan_data and optional athlete_id
        db: Database session
        
    Returns:
        PlanAnalysisResponse with comprehensive analysis results
        
    Raises:
        HTTPException: 400 for validation errors, 500 for server errors
    """
    try:
        # Perform analysis
        analyzer = PlanAnalyzerService(db)
        result = analyzer.analyze_plan_draft(
            plan_data=request.plan_data,
            athlete_id=request.athlete_id
        )
        
        # Convert to response format and return
        return PlanAnalysisResponse(**result)
        
    except ValueError as e:
        # Validation errors
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Server errors
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

