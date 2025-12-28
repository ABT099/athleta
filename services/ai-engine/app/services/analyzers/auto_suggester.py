"""
Auto Suggestion Service.

Auto-generates missing prescriptions using PrescriptionGeneratorService.
"""
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

from app.utils.constants import TrainingType, ExerciseIntensityCategory
from app.services.prescription_generator import PrescriptionGeneratorService
from app.models import Exercise


class AutoSuggestionService:
    """
    Auto-generates missing prescriptions for exercises.
    
    Uses PrescriptionGeneratorService to suggest:
    - Target RPE
    - Target RIR
    - Rest period
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.prescription_generator = PrescriptionGeneratorService()
    
    def suggest_missing(
        self,
        exercises: List[Dict],
        training_type: TrainingType,
        phase: str = "accumulation",
        week_in_phase: int = 1
    ) -> Dict:
        """
        Generate suggestions for missing prescriptions.
        
        Args:
            exercises: List of exercise dicts
            training_type: Training type
            phase: Training phase
            week_in_phase: Week in phase
            
        Returns:
            Dict mapping exercise_id to suggested prescriptions
        """
        suggestions = {}
        
        # Collect all exercise IDs that need to be queried
        exercise_ids = []
        for exercise in exercises:
            exercise_id = exercise.get("exercise_id")
            if exercise_id:
                exercise_ids.append(exercise_id)
        
        # Load all exercises upfront to avoid N+1 queries
        all_exercises = (
            self.db.query(Exercise)
            .filter(Exercise.id.in_(exercise_ids))
            .all()
        )
        exercise_map = {ex.id: ex for ex in all_exercises}
        
        for exercise in exercises:
            exercise_id = exercise.get("exercise_id")
            if not exercise_id:
                continue
            
            # Check if prescription is missing
            target_rpe = exercise.get("target_rpe")
            target_rir = exercise.get("target_rir")
            rest_period = exercise.get("rest_period_seconds")
            
            if target_rpe is None and target_rir is None:
                # Get exercise details from pre-loaded map
                ex = exercise_map.get(exercise_id)
                if not ex:
                    continue
                
                # Get intensity category
                try:
                    intensity_category = ExerciseIntensityCategory(ex.intensity_category)
                except (ValueError, AttributeError):
                    intensity_category = ExerciseIntensityCategory.ISOLATION
                
                # Generate prescription
                prescription = self.prescription_generator.generate_prescription(
                    intensity_category=intensity_category,
                    training_type=training_type,
                    training_phase=phase,
                    week_in_phase=week_in_phase,
                    is_primary=exercise.get("is_primary", True)
                )
                
                suggestions[exercise_id] = {
                    "exercise_name": ex.name,
                    "target_rpe": prescription["target_rpe"],
                    "target_rir": prescription["target_rir"],
                    "rest_period_seconds": prescription["rest_period_seconds"],
                    "reasoning": f"Auto-generated for {phase} phase, week {week_in_phase}"
                }
            elif rest_period is None:
                # Only rest period missing
                ex = exercise_map.get(exercise_id)
                if not ex:
                    continue
                
                try:
                    intensity_category = ExerciseIntensityCategory(ex.intensity_category)
                except (ValueError, AttributeError):
                    intensity_category = ExerciseIntensityCategory.ISOLATION
                
                prescription = self.prescription_generator.generate_prescription(
                    intensity_category=intensity_category,
                    training_type=training_type,
                    training_phase=phase,
                    week_in_phase=week_in_phase,
                    is_primary=exercise.get("is_primary", True)
                )
                
                suggestions[exercise_id] = {
                    "exercise_name": ex.name,
                    "rest_period_seconds": prescription["rest_period_seconds"],
                    "reasoning": f"Auto-generated rest period for {phase} phase"
                }
        
        return suggestions

