"""
Exercise Substitution Service.

Finds suitable exercise variations based on:
- Same movement pattern, different equipment
- Same muscles, different angle
- Novel stimulus for psychological plateaus
"""
from typing import Dict, List, Optional, Set
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func

from app.models import Exercise, ExerciseMuscle, MuscleGroupModel


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
    
    def _get_primary_muscles(self, exercise: Exercise) -> Set[int]:
        """
        Get primary muscle IDs for an exercise (prime_mover role).
        
        Args:
            exercise: Exercise model
            
        Returns:
            Set of muscle group IDs
        """
        primary_links = (
            self.db.query(ExerciseMuscle.muscle_group_id)
            .filter(
                ExerciseMuscle.exercise_id == exercise.id,
                ExerciseMuscle.role == "prime_mover"
            )
            .all()
        )
        return {link[0] for link in primary_links}
    
    def _calculate_muscle_similarity(self, exercise1_id: int, exercise2_id: int) -> float:
        """
        Calculate muscle activation similarity between two exercises.
        
        Uses weighted Jaccard similarity based on activation percentages.
        
        Args:
            exercise1_id: First exercise ID
            exercise2_id: Second exercise ID
            
        Returns:
            Similarity score (0.0 - 1.0)
        """
        # Get muscle activations for both exercises
        # Convert role to activation weight: prime_mover=85%, synergist=55%, stabilizer=20%
        def role_to_weight(role: str) -> int:
            if role == "prime_mover":
                return 85
            elif role == "synergist":
                return 55
            else:  # stabilizer
                return 20
        
        ex1_muscles = {}
        ex2_muscles = {}
        
        for link in self.db.query(ExerciseMuscle).filter(ExerciseMuscle.exercise_id == exercise1_id).all():
            ex1_muscles[link.muscle_group_id] = role_to_weight(link.role)
        
        for link in self.db.query(ExerciseMuscle).filter(ExerciseMuscle.exercise_id == exercise2_id).all():
            ex2_muscles[link.muscle_group_id] = role_to_weight(link.role)
        
        if not ex1_muscles or not ex2_muscles:
            return 0.0
        
        # Calculate weighted Jaccard similarity
        all_muscles = set(ex1_muscles.keys()) | set(ex2_muscles.keys())
        
        intersection_sum = 0.0
        union_sum = 0.0
        
        for muscle_id in all_muscles:
            act1 = ex1_muscles.get(muscle_id, 0)
            act2 = ex2_muscles.get(muscle_id, 0)
            intersection_sum += min(act1, act2)
            union_sum += max(act1, act2)
        
        if union_sum == 0:
            return 0.0
        
        return intersection_sum / union_sum
    
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
        # Get primary muscles for the original exercise
        original_muscles = self._get_primary_muscles(original)
        if not original_muscles:
            return None
        
        # Find exercises that target the same muscles
        candidate_ids = (
            self.db.query(ExerciseMuscle.exercise_id)
            .filter(
                ExerciseMuscle.exercise_id != original.id,
                ExerciseMuscle.muscle_group_id.in_(original_muscles),
                ExerciseMuscle.role == "prime_mover"
            )
            .group_by(ExerciseMuscle.exercise_id)
            .having(func.count(ExerciseMuscle.muscle_group_id) >= len(original_muscles) * 0.5)
            .all()
        )
        
        if not candidate_ids:
            return None
        
        # Get full exercise objects
        candidates = (
            self.db.query(Exercise)
            .filter(Exercise.id.in_([cid[0] for cid in candidate_ids]))
            .all()
        )
        
        # Score candidates by muscle similarity and prefer same movement pattern
        best_candidate = None
        best_score = 0.0
        
        for candidate in candidates:
            similarity = self._calculate_muscle_similarity(original.id, candidate.id)
            
            # Bonus for same movement pattern
            if candidate.movement_pattern == original.movement_pattern:
                similarity += 0.2
            
            if similarity > best_score:
                best_score = similarity
                best_candidate = candidate
        
        return best_candidate
    
    def _find_novel_stimulus(self, original: Exercise) -> Optional[Exercise]:
        """
        Find exercise with same primary muscles but different movement pattern.
        
        Provides psychological novelty while maintaining muscle targeting.
        """
        # Get primary muscles for the original exercise
        original_muscles = self._get_primary_muscles(original)
        if not original_muscles:
            return None
        
        # Find exercises with similar muscles but different movement pattern
        candidate_ids = (
            self.db.query(ExerciseMuscle.exercise_id)
            .filter(
                ExerciseMuscle.exercise_id != original.id,
                ExerciseMuscle.muscle_group_id.in_(original_muscles),
                ExerciseMuscle.role.in_(["prime_mover", "synergist"])
            )
            .group_by(ExerciseMuscle.exercise_id)
            .all()
        )
        
        if not candidate_ids:
            return None
        
        # Get candidates with different movement patterns
        candidates = (
            self.db.query(Exercise)
            .filter(
                Exercise.id.in_([cid[0] for cid in candidate_ids]),
                or_(
                    Exercise.movement_pattern != original.movement_pattern,
                    Exercise.movement_pattern.is_(None)
                )
            )
            .all()
        )
        
        if not candidates:
            return None
        
        # Prefer similar exercise_type for similar training effect
        for candidate in candidates:
            if candidate.exercise_type == original.exercise_type:
                return candidate
        
        # Fallback to any candidate
        return candidates[0]
    
    def _find_same_muscles(self, original: Exercise) -> Optional[Exercise]:
        """
        Find any exercise targeting the same primary muscles.
        """
        # Get primary muscles for the original exercise
        original_muscles = self._get_primary_muscles(original)
        if not original_muscles:
            return None
        
        # Find any exercise with significant overlap
        candidate_id = (
            self.db.query(ExerciseMuscle.exercise_id)
            .filter(
                ExerciseMuscle.exercise_id != original.id,
                ExerciseMuscle.muscle_group_id.in_(original_muscles),
                ExerciseMuscle.role.in_(["prime_mover", "synergist"])
            )
            .first()
        )
        
        if not candidate_id:
            return None
        
        return self.db.query(Exercise).filter(Exercise.id == candidate_id[0]).first()
