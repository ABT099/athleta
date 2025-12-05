"""
Workout Duration Estimator.

Estimates workout duration based on sets, rest periods, and transitions.
References: Schoenfeld (2016) - Optimal training duration.
"""
from typing import Dict, List

from app.utils.constants import (
    WORKOUT_DURATION_OPTIMAL, WORKOUT_DURATION_ACCEPTABLE,
    WORKOUT_DURATION_EXCESSIVE, SET_EXECUTION_SECONDS, TRANSITION_SECONDS
)


class WorkoutDurationEstimator:
    """
    Estimates workout duration and flags excessive sessions.
    
    Formula:
    Duration = (sets × (execution_time + rest_period)) + transitions
    """
    
    def estimate(self, exercises: List[Dict]) -> Dict:
        """
        Estimate workout duration.
        
        Args:
            exercises: List of exercise dicts with sets and rest periods
            
        Returns:
            Dict with duration estimate and status
        """
        total_seconds = 0
        total_sets = 0
        
        for i, exercise in enumerate(exercises):
            # Get sets (use average of min/max)
            sets_min = exercise.get("target_sets_min", 0)
            sets_max = exercise.get("target_sets_max", 0)
            avg_sets = (sets_min + sets_max) / 2 if sets_max > 0 else sets_min
            total_sets += avg_sets
            
            # Get rest period (default to 90s if not specified)
            rest_period = exercise.get("rest_period_seconds", 90)
            
            # Calculate time for this exercise
            # Sets × (execution + rest) + transition to next exercise
            exercise_time = avg_sets * (SET_EXECUTION_SECONDS + rest_period)
            
            # Add transition time (except for last exercise)
            if i < len(exercises) - 1:
                exercise_time += TRANSITION_SECONDS
            
            total_seconds += exercise_time
        
        # Convert to minutes
        duration_minutes = total_seconds / 60
        
        # Determine status
        if WORKOUT_DURATION_OPTIMAL[0] <= duration_minutes <= WORKOUT_DURATION_OPTIMAL[1]:
            status = "optimal"
        elif WORKOUT_DURATION_ACCEPTABLE[0] <= duration_minutes <= WORKOUT_DURATION_ACCEPTABLE[1]:
            status = "acceptable"
        elif duration_minutes > WORKOUT_DURATION_EXCESSIVE:
            status = "excessive"
        else:
            status = "too_short"
        
        # Generate warnings/suggestions
        warnings = []
        suggestions = []
        
        if status == "excessive":
            warnings.append({
                "severity": "high",
                "category": "duration",
                "message": f"Workout duration ({duration_minutes:.0f} minutes) exceeds optimal range (45-75 min)",
                "affected_items": ["workout"],
                "recommendation": f"Consider splitting workout or reducing volume to stay within 45-75 minute range"
            })
        elif status == "too_short":
            suggestions.append({
                "category": "duration",
                "message": f"Workout duration ({duration_minutes:.0f} minutes) is below optimal range",
                "impact": "low",
                "action": "Consider adding exercises or increasing volume for better stimulus"
            })
        elif status == "acceptable" and duration_minutes > WORKOUT_DURATION_OPTIMAL[1]:
            suggestions.append({
                "category": "duration",
                "message": f"Workout duration ({duration_minutes:.0f} minutes) is approaching excessive range",
                "impact": "medium",
                "action": "Consider reducing rest periods or splitting workout if duration increases"
            })
        
        return {
            "estimated_minutes": round(duration_minutes, 1),
            "total_sets": round(total_sets, 1),
            "status": status,
            "optimal_range": WORKOUT_DURATION_OPTIMAL,
            "warnings": warnings,
            "suggestions": suggestions,
        }

