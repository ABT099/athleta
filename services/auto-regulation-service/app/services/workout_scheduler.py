"""
Workout rotation helper service.

Handles determining the next workout in rotation based on order_in_week.
Schedule generation is handled by the frontend using day_of_week configuration.
"""
from typing import Optional
from sqlalchemy.orm import Session

from autoregulation.models import WorkoutPlan


class WorkoutScheduler:
    """
    Simple helper for workout rotation logic.
    
    Determines next workout in rotation based on order_in_week.
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_next_workout_in_rotation(
        self,
        athlete_id: int,
        completed_workout_day_id: int,
        plan_id: int
    ) -> Optional[int]:
        """
        Get the next workout day ID in rotation.
        
        Args:
            athlete_id: Athlete ID (unused, kept for API compatibility)
            completed_workout_day_id: Just completed workout day ID
            plan_id: Plan ID
            
        Returns:
            Next workout day ID or None
        """
        plan = self.db.query(WorkoutPlan).filter(WorkoutPlan.id == plan_id).first()
        
        if not plan or not plan.workout_days:
            return None
        
        sorted_days = sorted(plan.workout_days, key=lambda d: d.order_in_week)
        
        # Find current position
        current_idx = next(
            (i for i, d in enumerate(sorted_days) if d.id == completed_workout_day_id),
            None
        )
        
        if current_idx is None:
            # If not found, return first workout
            return sorted_days[0].id
        
        # Return next in rotation (wrap around)
        next_idx = (current_idx + 1) % len(sorted_days)
        return sorted_days[next_idx].id

