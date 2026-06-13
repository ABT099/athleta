"""
Helper utilities for common database operations.
"""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from autoregulation.models import Athlete


def get_athlete_or_404(db: Session, athlete_id: int) -> Athlete:
    """
    Get athlete by ID or raise 404 HTTPException.
    
    Args:
        db: Database session
        athlete_id: Athlete ID
        
    Returns:
        Athlete model
        
    Raises:
        HTTPException: 404 if athlete not found
    """
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    if not athlete:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Athlete {athlete_id} not found"
        )
    return athlete

