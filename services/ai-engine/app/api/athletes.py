"""
Athletes API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, undefer
from typing import List

from app.database import get_db
from app.models import Athlete, WorkoutPlan, WorkoutSession
from app.auth import get_current_user


router = APIRouter()

@router.get("/athletes/{athlete_id}/current-plan", response_model=dict)
def get_current_plan(
    athlete_id: int,
    current_user: dict = Depends(get_current_user),
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
    
    # Get active plan with deferred fields undeferred for response
    plan = db.query(WorkoutPlan).options(
        undefer(WorkoutPlan.name),
        undefer(WorkoutPlan.description),
        undefer(WorkoutPlan.created_at)
    ).filter(
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
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get athlete's training progress and analytics.
    """
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import func
    
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    
    if not athlete:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Athlete {athlete_id} not found"
        )
    
    # Get sessions from the period
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
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
        "period_days": days,
        "total_workouts": total_workouts,
        "total_volume_lifted": round(total_volume, 1),
        "average_rpe": round(avg_rpe, 1) if avg_rpe else None,
        "weekly_breakdown": weeks_data,
        "training_experience": athlete.training_experience.value
    }
