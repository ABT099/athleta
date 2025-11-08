"""
Exercise-specific progression service.

Handles compound vs isolation progression rates, exercise familiarity,
and double progression logic for hypertrophy training.
"""
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models import (
    Athlete, Exercise, ExerciseProgressionTracking, WorkoutSession
)
from app.utils.constants import (
    TrainingExperience, TrainingType, ExerciseType,
    EXERCISE_PROGRESSION_RATES, NEW_EXERCISE_PROGRESSION_RATE,
    DOUBLE_PROGRESSION_CONFIG, FAMILIARITY_INCREASE_RATE,
    FAMILIARITY_THRESHOLD, ProgressionState
)


class ExerciseProgressionService:
    """
    Manages exercise-specific progression logic.
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_exercise_progression_rate(
        self,
        exercise_id: int,
        athlete_id: int,
        experience: TrainingExperience
    ) -> float:
        """
        Get progression rate for a specific exercise based on type and familiarity.
        
        Compound exercises progress slower than isolation exercises.
        New exercises progress even slower until athlete is familiar.
        
        Args:
            exercise_id: Exercise ID
            athlete_id: Athlete ID
            experience: Training experience level
            
        Returns:
            Progression rate (e.g., 0.02 = 2% per session)
        """
        exercise = self.db.query(Exercise).filter(Exercise.id == exercise_id).first()
        if not exercise:
            return 0.02  # Default rate
        
        # Determine exercise type
        exercise_type = ExerciseType(exercise.exercise_type) if exercise.exercise_type else ExerciseType.COMPOUND
        
        # Get base rate for exercise type and experience
        base_rate = EXERCISE_PROGRESSION_RATES[exercise_type][experience]
        
        # Check familiarity
        familiarity = self.get_exercise_familiarity(athlete_id, exercise_id)
        
        if familiarity < FAMILIARITY_THRESHOLD:
            # New exercise - use slower progression rate
            return NEW_EXERCISE_PROGRESSION_RATE
        
        return base_rate
    
    def get_exercise_familiarity(self, athlete_id: int, exercise_id: int) -> float:
        """
        Calculate exercise familiarity score (0.0 - 1.0).
        
        Familiarity increases with each session. New exercises start at 0.0
        and increase by FAMILIARITY_INCREASE_RATE per session.
        
        Args:
            athlete_id: Athlete ID
            exercise_id: Exercise ID
            
        Returns:
            Familiarity score (0.0 = new, 1.0 = completely familiar)
        """
        # Get most recent progression tracking record
        latest_tracking = self.db.query(ExerciseProgressionTracking).filter(
            ExerciseProgressionTracking.athlete_id == athlete_id,
            ExerciseProgressionTracking.exercise_id == exercise_id
        ).order_by(desc(ExerciseProgressionTracking.session_date)).first()
        
        if not latest_tracking:
            return 0.0
        
        return min(latest_tracking.familiarity_score, 1.0)
    
    def update_exercise_familiarity(
        self,
        athlete_id: int,
        exercise_id: int,
        current_familiarity: float
    ) -> float:
        """
        Increase familiarity score after completing a session.
        
        Args:
            athlete_id: Athlete ID
            exercise_id: Exercise ID
            current_familiarity: Current familiarity score
            
        Returns:
            Updated familiarity score
        """
        new_familiarity = min(current_familiarity + FAMILIARITY_INCREASE_RATE, 1.0)
        return round(new_familiarity, 2)
    
    def calculate_double_progression(
        self,
        athlete_id: int,
        exercise_id: int,
        current_weight: float,
        total_reps_achieved: int,
        total_sets: int,
        training_type: TrainingType
    ) -> Dict:
        """
        Calculate double progression parameters.
        
        Double progression:
        1. Increase reps until max threshold is hit
        2. Then increase weight and reset reps to minimum
        
        This is particularly effective for hypertrophy training.
        
        Args:
            athlete_id: Athlete ID
            exercise_id: Exercise ID
            current_weight: Current weight used (kg)
            total_reps_achieved: Total reps achieved across all sets
            total_sets: Number of sets performed
            training_type: Training type (hypertrophy uses double progression)
            
        Returns:
            Dict with progression recommendations
        """
        # Only apply double progression for hypertrophy and hybrid training
        if training_type not in [TrainingType.HYPERTROPHY, TrainingType.HYBRID]:
            return {
                "use_double_progression": False,
                "next_weight": current_weight,
                "next_target_reps": None,
                "progression_state": ProgressionState.MAINTAINING
            }
        
        config = DOUBLE_PROGRESSION_CONFIG
        avg_reps_per_set = total_reps_achieved / total_sets if total_sets > 0 else 0
        
        # Get previous tracking
        latest_tracking = self.db.query(ExerciseProgressionTracking).filter(
            ExerciseProgressionTracking.athlete_id == athlete_id,
            ExerciseProgressionTracking.exercise_id == exercise_id
        ).order_by(desc(ExerciseProgressionTracking.session_date)).first()
        
        current_state = ProgressionState.REP_PROGRESSION
        if latest_tracking:
            current_state = ProgressionState(latest_tracking.progression_state)
        
        # Check if hit max reps - time to increase weight
        if avg_reps_per_set >= config["max_reps"]:
            new_weight = current_weight * (1 + config["weight_increase_percent"])
            # Round to nearest 2.5kg for practical loading
            new_weight = round(new_weight / 2.5) * 2.5
            
            return {
                "use_double_progression": True,
                "next_weight": new_weight,
                "next_target_reps": config["reset_reps_to"],
                "progression_state": ProgressionState.WEIGHT_PROGRESSION,
                "message": f"Hit max reps! Increase weight to {new_weight}kg and reset to {config['reset_reps_to']} reps"
            }
        
        # Still in rep progression phase
        elif avg_reps_per_set < config["max_reps"]:
            target_reps = min(
                int(avg_reps_per_set) + config["rep_increase_per_session"],
                config["max_reps"]
            )
            
            return {
                "use_double_progression": True,
                "next_weight": current_weight,
                "next_target_reps": target_reps,
                "progression_state": ProgressionState.REP_PROGRESSION,
                "message": f"Continue adding reps. Target {target_reps} reps per set"
            }
        
        # Maintain current parameters
        return {
            "use_double_progression": True,
            "next_weight": current_weight,
            "next_target_reps": int(avg_reps_per_set),
            "progression_state": ProgressionState.MAINTAINING,
            "message": "Maintain current weight and reps"
        }
    
    def track_exercise_progression(
        self,
        athlete_id: int,
        exercise_id: int,
        workout_session_id: int,
        session_date: datetime,
        weight_used: float,
        total_reps: int,
        total_sets: int,
        average_rpe: float,
        estimated_1rm: float,
        volume_load: float,
        progression_state: str,
        rep_progression_target: Optional[int] = None
    ) -> ExerciseProgressionTracking:
        """
        Create a tracking record for exercise progression.
        
        Args:
            athlete_id: Athlete ID
            exercise_id: Exercise ID
            workout_session_id: Workout session ID
            session_date: Session date
            weight_used: Weight used (kg)
            total_reps: Total reps across all sets
            total_sets: Number of sets
            average_rpe: Average RPE across sets
            estimated_1rm: Estimated 1RM
            volume_load: Total volume load (sets x reps x weight)
            progression_state: Current progression state
            rep_progression_target: Target reps for next session (double progression)
            
        Returns:
            Created ExerciseProgressionTracking record
        """
        # Get previous tracking to calculate sessions at weight
        previous_tracking = self.db.query(ExerciseProgressionTracking).filter(
            ExerciseProgressionTracking.athlete_id == athlete_id,
            ExerciseProgressionTracking.exercise_id == exercise_id
        ).order_by(desc(ExerciseProgressionTracking.session_date)).first()
        
        sessions_at_weight = 1
        weeks_at_weight = 1
        current_familiarity = 0.0
        
        if previous_tracking:
            current_familiarity = previous_tracking.familiarity_score
            
            # Check if weight is the same
            if abs(previous_tracking.weight_used - weight_used) < 0.1:
                sessions_at_weight = previous_tracking.sessions_at_weight + 1
                
                # Calculate weeks at weight
                days_diff = (session_date - previous_tracking.session_date).days
                weeks_at_weight = max(1, days_diff // 7)
            else:
                sessions_at_weight = 1
                weeks_at_weight = 1
        
        # Update familiarity
        new_familiarity = self.update_exercise_familiarity(
            athlete_id, exercise_id, current_familiarity
        )
        
        # Determine if ready for weight progression
        weight_progression_ready = (
            progression_state == ProgressionState.WEIGHT_PROGRESSION or
            sessions_at_weight >= 3  # At same weight for 3+ sessions
        )
        
        tracking = ExerciseProgressionTracking(
            athlete_id=athlete_id,
            exercise_id=exercise_id,
            workout_session_id=workout_session_id,
            session_date=session_date,
            weight_used=weight_used,
            total_reps=total_reps,
            total_sets=total_sets,
            average_rpe=average_rpe,
            estimated_1rm=estimated_1rm,
            volume_load=volume_load,
            progression_state=progression_state,
            weeks_at_weight=weeks_at_weight,
            sessions_at_weight=sessions_at_weight,
            rep_progression_target=rep_progression_target,
            weight_progression_ready=weight_progression_ready,
            familiarity_score=new_familiarity
        )
        
        self.db.add(tracking)
        self.db.commit()
        self.db.refresh(tracking)
        
        return tracking

