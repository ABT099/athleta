"""
Exercise Substitution Service.

Finds suitable exercise variations based on:
- Same movement pattern, different equipment
- Same muscles, different angle
- Novel stimulus for psychological plateaus
"""
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from app.models import Exercise
from app.utils.constants import MuscleGroup


class ExerciseSubstitutor:
    """
    Finds exercise substitutions for plateau intervention.
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def find_substitute(
        self,
        exercise_id: int,
        variation_type: str = "equipment_or_angle"
    ) -> Optional[Dict]:
        """
        Find a suitable substitute exercise.
        
        Args:
            exercise_id: Original exercise ID
            variation_type: "equipment_or_angle", "novel_stimulus", or "same_muscles"
            
        Returns:
            Dict with substitute exercise info, or None
        """
        original = self.db.query(Exercise).filter(Exercise.id == exercise_id).first()
        if not original:
            return None
        
        if variation_type == "equipment_or_angle":
            # Try equipment variation first, then angle
            substitute = self._find_equipment_variation(original)
            if substitute:
                return {
                    "exercise_id": substitute.id,
                    "name": substitute.name,
                    "substitution_type": "equipment",
                    "reason": f"Same movement pattern, different equipment"
                }
            
            # Try angle variation
            substitute = self._find_angle_variation(original)
            if substitute:
                return {
                    "exercise_id": substitute.id,
                    "name": substitute.name,
                    "substitution_type": "angle",
                    "reason": f"Same muscles, different angle"
                }
        
        elif variation_type == "novel_stimulus":
            # Find exercise with same primary muscles but different movement pattern
            substitute = self._find_novel_stimulus(original)
            if substitute:
                return {
                    "exercise_id": substitute.id,
                    "name": substitute.name,
                    "substitution_type": "novel_stimulus",
                    "reason": f"Same muscles, different movement pattern for novelty"
                }
        
        elif variation_type == "same_muscles":
            # Any exercise targeting same primary muscles
            substitute = self._find_same_muscles(original)
            if substitute:
                return {
                    "exercise_id": substitute.id,
                    "name": substitute.name,
                    "substitution_type": "same_muscles",
                    "reason": f"Targets same primary muscles"
                }
        
        return None
    
    def _find_equipment_variation(self, original: Exercise) -> Optional[Exercise]:
        """
        Find exercise with same movement pattern but different equipment.
        
        Examples:
        - Barbell Bench Press -> Dumbbell Bench Press
        - Barbell Squat -> Dumbbell Goblet Squat
        """
        if not original.movement_pattern:
            return None
        
        # Get all exercises with same movement pattern
        candidates = (
            self.db.query(Exercise)
            .filter(
                Exercise.id != original.id,
                Exercise.movement_pattern == original.movement_pattern,
                Exercise.equipment != original.equipment,
                Exercise.equipment.isnot(None)
            )
            .all()
        )
        
        if not candidates:
            return None
        
        # Prefer same exercise_type and intensity_category
        for candidate in candidates:
            if (candidate.exercise_type == original.exercise_type and
                candidate.intensity_category == original.intensity_category):
                return candidate
        
        # Fallback to any candidate
        return candidates[0]
    
    def _find_angle_variation(self, original: Exercise) -> Optional[Exercise]:
        """
        Find exercise with same primary muscles but different angle.
        
        Examples:
        - Flat Bench Press -> Incline Bench Press
        - Barbell Row -> T-Bar Row
        """
        if not original.primary_muscles:
            return None
        
        # Get exercises with same primary muscles
        candidates = (
            self.db.query(Exercise)
            .filter(
                Exercise.id != original.id,
                Exercise.primary_muscles.contains(original.primary_muscles)
            )
            .all()
        )
        
        if not candidates:
            return None
        
        # Prefer different name (indicates different angle/variation)
        # and same movement pattern category
        for candidate in candidates:
            if (candidate.name.lower() != original.name.lower() and
                candidate.movement_pattern == original.movement_pattern):
                return candidate
        
        # Fallback to any candidate with same primary muscles
        return candidates[0] if candidates else None
    
    def _find_novel_stimulus(self, original: Exercise) -> Optional[Exercise]:
        """
        Find exercise with same primary muscles but different movement pattern.
        
        Provides psychological novelty while maintaining muscle targeting.
        """
        if not original.primary_muscles:
            return None
        
        # Get exercises with same primary muscles but different movement pattern
        candidates = (
            self.db.query(Exercise)
            .filter(
                Exercise.id != original.id,
                Exercise.primary_muscles.contains(original.primary_muscles),
                or_(
                    Exercise.movement_pattern != original.movement_pattern,
                    Exercise.movement_pattern.is_(None)
                )
            )
            .all()
        )
        
        if not candidates:
            return None
        
        # Prefer similar exercise_type
        for candidate in candidates:
            if candidate.exercise_type == original.exercise_type:
                return candidate
        
        # Fallback to any candidate
        return candidates[0]
    
    def _find_same_muscles(self, original: Exercise) -> Optional[Exercise]:
        """
        Find any exercise targeting the same primary muscles.
        """
        if not original.primary_muscles:
            return None
        
        candidate = (
            self.db.query(Exercise)
            .filter(
                Exercise.id != original.id,
                Exercise.primary_muscles.contains(original.primary_muscles)
            )
            .first()
        )
        
        return candidate

