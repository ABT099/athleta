"""
Athletes API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import Athlete, WorkoutPlan, WorkoutSession
from app.schemas.athlete import (
    AthleteCreate,
    AthleteUpdate,
    AthleteResponse,
    AthleteProgressSummary
)
from app.schemas.responses import SuccessResponse


router = APIRouter()


@router.post("/athletes", response_model=AthleteResponse, status_code=status.HTTP_201_CREATED)
def create_athlete(
    athlete_data: AthleteCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new athlete profile.
    """
    # Check if email already exists
    existing = db.query(Athlete).filter(Athlete.email == athlete_data.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Athlete with email {athlete_data.email} already exists"
        )
    
    # Create athlete
    athlete = Athlete(
        name=athlete_data.name,
        email=athlete_data.email,
        age=athlete_data.age,
        gender=athlete_data.gender,
        training_experience=athlete_data.training_experience,
        injury_history=athlete_data.injury_history
    )
    
    db.add(athlete)
    db.commit()
    db.refresh(athlete)
    
    return athlete


@router.get("/athletes/{athlete_id}", response_model=AthleteResponse)
def get_athlete(
    athlete_id: int,
    db: Session = Depends(get_db)
):
    """
    Get athlete by ID.
    """
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    
    if not athlete:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Athlete {athlete_id} not found"
        )
    
    return athlete


@router.get("/athletes", response_model=List[AthleteResponse])
def list_athletes(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    List all athletes.
    """
    athletes = db.query(Athlete).offset(skip).limit(limit).all()
    return athletes


@router.patch("/athletes/{athlete_id}", response_model=AthleteResponse)
def update_athlete(
    athlete_id: int,
    athlete_data: AthleteUpdate,
    db: Session = Depends(get_db)
):
    """
    Update athlete information.
    """
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    
    if not athlete:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Athlete {athlete_id} not found"
        )
    
    # Update fields
    update_data = athlete_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(athlete, field, value)
    
    db.commit()
    db.refresh(athlete)
    
    return athlete


@router.delete("/athletes/{athlete_id}", response_model=SuccessResponse)
def delete_athlete(
    athlete_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete athlete.
    """
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    
    if not athlete:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Athlete {athlete_id} not found"
        )
    
    db.delete(athlete)
    db.commit()
    
    return SuccessResponse(message=f"Athlete {athlete_id} deleted successfully")


@router.get("/athletes/{athlete_id}/current-plan", response_model=dict)
def get_current_plan(
    athlete_id: int,
    db: Session = Depends(get_db)
):
    """
    Get athlete's current active training plan.
    """
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    
    if not athlete:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Athlete {athlete_id} not found"
        )
    
    # Get active plan
    plan = db.query(WorkoutPlan).filter(
        WorkoutPlan.athlete_id == athlete_id,
        WorkoutPlan.is_active == 1
    ).first()
    
    if not plan:
        return {
            "has_plan": False,
            "message": "No active training plan found"
        }
    
    from app.schemas.workout import WorkoutPlanResponse
    from app.services.progressive_overload_engine import ProgressiveOverloadEngine
    
    engine = ProgressiveOverloadEngine(db)
    plan_context = engine.analyze_plan_context(athlete_id)
    
    return {
        "has_plan": True,
        "plan": WorkoutPlanResponse.model_validate(plan),
        "current_context": plan_context
    }


@router.get("/athletes/{athlete_id}/progress", response_model=dict)
def get_athlete_progress(
    athlete_id: int,
    days: int = 30,
    db: Session = Depends(get_db)
):
    """
    Get athlete's training progress and analytics.
    """
    from datetime import datetime, timedelta
    from sqlalchemy import func
    
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    
    if not athlete:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Athlete {athlete_id} not found"
        )
    
    # Get sessions from the period
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    sessions = db.query(WorkoutSession).filter(
        WorkoutSession.athlete_id == athlete_id,
        WorkoutSession.session_date >= cutoff_date
    ).all()
    
    if not sessions:
        return {
            "athlete_id": athlete_id,
            "period_days": days,
            "total_workouts": 0,
            "message": "No workout data available for this period"
        }
    
    # Calculate metrics
    total_workouts = len(sessions)
    total_volume = sum(s.total_volume or 0 for s in sessions)
    rpe_values = [s.overall_rpe for s in sessions if s.overall_rpe]
    avg_rpe = sum(rpe_values) / len(rpe_values) if rpe_values else None
    
    # Get weekly breakdown
    weeks_data = []
    for i in range(0, days, 7):
        week_start = cutoff_date + timedelta(days=i)
        week_end = week_start + timedelta(days=7)
        week_sessions = [
            s for s in sessions 
            if week_start <= s.session_date < week_end
        ]
        
        if week_sessions:
            week_volume = sum(s.total_volume or 0 for s in week_sessions)
            week_rpe_values = [s.overall_rpe for s in week_sessions if s.overall_rpe]
            week_avg_rpe = sum(week_rpe_values) / len(week_rpe_values) if week_rpe_values else None
            
            weeks_data.append({
                "week_start": week_start.strftime("%Y-%m-%d"),
                "workouts": len(week_sessions),
                "total_volume": round(week_volume, 1),
                "average_rpe": round(week_avg_rpe, 1) if week_avg_rpe else None
            })
    
    return {
        "athlete_id": athlete_id,
        "athlete_name": athlete.name,
        "period_days": days,
        "total_workouts": total_workouts,
        "total_volume_lifted": round(total_volume, 1),
        "average_rpe": round(avg_rpe, 1) if avg_rpe else None,
        "weekly_breakdown": weeks_data,
        "training_experience": athlete.training_experience.value
    }


