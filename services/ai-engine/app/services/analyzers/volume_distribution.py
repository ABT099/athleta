"""
Volume Distribution Analyzer.

Analyzes if volume is distributed appropriately across muscle groups
based on MEV/MAV/MRV landmarks (Israetel et al., Schoenfeld 2017).
"""
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

from app.models import ExerciseMuscle, MuscleGroupModel
from app.utils.constants import (
    TrainingExperience, MEV_SETS_PER_WEEK, MRV_SETS_PER_WEEK,
    EFFECTIVE_SET_RIR_THRESHOLD, MAX_FOCUS_AREAS
)
from app.services.volume_manager import VolumeManager


class VolumeDistributionAnalyzer:
    """
    Analyzes volume distribution across muscle groups.
    
    Checks:
    - Weekly sets per muscle group vs MEV/MAV/MRV
    - Volume balance across muscle groups
    - Focus area compliance
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.volume_manager = VolumeManager(db)
    
    def analyze(
        self,
        workout_days: List[Dict],
        experience: TrainingExperience,
        focus_areas: Optional[List[str]] = None
    ) -> Dict:
        """
        Analyze volume distribution across the plan with focus-aware thresholds.
        
        Args:
            workout_days: List of workout day dicts with exercises
            experience: Training experience level
            focus_areas: Optional list of focus areas (e.g., ["chest", "back"])
            
        Returns:
            Dict with volume analysis per muscle group
        """
        # Validate focus areas count
        focus_areas = focus_areas or []
        if len(focus_areas) > MAX_FOCUS_AREAS:
            focus_warning = {
                "severity": "medium",
                "category": "volume",
                "message": f"Too many focus areas ({len(focus_areas)}). Maximum {MAX_FOCUS_AREAS} recommended for optimal results.",
                "affected_items": focus_areas,
                "recommendation": f"Select {MAX_FOCUS_AREAS} or fewer focus areas for better volume distribution"
            }
        else:
            focus_warning = None
        
        # Calculate weekly sets per muscle group
        muscle_volume = self._calculate_weekly_volume(workout_days)
        
        # Analyze each muscle group with focus-aware thresholds
        analysis = {}
        warnings = []
        suggestions = []
        
        if focus_warning:
            warnings.append(focus_warning)
        
        # Get all muscle groups from database
        all_muscles = self.db.query(MuscleGroupModel).all()
        
        for muscle in all_muscles:
            muscle_name = muscle.name
            weekly_sets = muscle_volume.get(muscle_name, 0)
            
            # Get focus-aware volume targets
            volume_target = self.volume_manager.get_volume_target_for_muscle(
                experience=experience,
                muscle_name=muscle_name,
                focus_areas=focus_areas
            )
            
            target_sets = volume_target["target_sets"]
            upper_bound = volume_target["upper_bound"]
            focus_state = volume_target["focus_state"]
            
            # Get landmarks for reference
            muscle_landmarks = self.volume_manager.get_volume_landmarks(
                experience, muscle_name
            )
            mev = muscle_landmarks["mev"]
            mav = muscle_landmarks["mav"]
            mrv = muscle_landmarks["mrv"]
            
            # Determine status based on focus state
            if weekly_sets == 0:
                status = "not_trained"
                severity = "medium"
            elif focus_state == "focus":
                # Focus muscles: optimal = MAV-MRV, below = under MAV
                if weekly_sets < mav:
                    status = "below_target"
                    severity = "high"
                elif weekly_sets <= mrv:
                    status = "optimal"
                    severity = None
                else:
                    status = "above_mrv"
                    severity = "high"
            else:
                # Maintenance muscles: optimal = MEV-MAV, above = over MAV
                if weekly_sets < mev:
                    status = "below_mev"
                    severity = "high"
                elif weekly_sets <= mav:
                    status = "optimal"
                    severity = None
                else:
                    status = "above_target"
                    severity = "low"
            
            analysis[muscle_name] = {
                "weekly_sets": weekly_sets,
                "mev": mev,
                "mav": mav,
                "mrv": mrv,
                "target_sets": target_sets,
                "upper_bound": upper_bound,
                "status": status,
                "severity": severity,
                "focus_state": focus_state,
            }
            
            # Generate warnings and suggestions
            if status == "not_trained":
                warnings.append({
                    "severity": "medium",
                    "category": "volume",
                    "message": f"{muscle_name.replace('_', ' ').title()} not trained in plan",
                    "affected_items": [muscle_name],
                    "recommendation": f"Add exercises targeting {muscle_name} to meet minimum volume"
                })
            elif status == "below_mev" or status == "below_target":
                if focus_state == "focus":
                    suggestions.append({
                        "category": "volume",
                        "message": f"Focus muscle {muscle_name.replace('_', ' ').title()} volume ({weekly_sets} sets) below target MAV ({mav} sets)",
                        "impact": "high",
                        "action": f"Increase to {mav}-{mrv} sets per week to maximize focus area development"
                    })
                else:
                    suggestions.append({
                        "category": "volume",
                        "message": f"{muscle_name.replace('_', ' ').title()} volume ({weekly_sets} sets) below MEV ({mev} sets)",
                        "impact": "medium",
                        "action": f"Add {mev - weekly_sets} more sets per week for {muscle_name}"
                    })
            elif status == "above_mrv":
                warnings.append({
                    "severity": "high",
                    "category": "volume",
                    "message": f"{muscle_name.replace('_', ' ').title()} volume ({weekly_sets} sets) exceeds MRV ({mrv} sets)",
                    "affected_items": [muscle_name],
                    "recommendation": f"Reduce volume to {mrv} sets per week to prevent overreaching"
                })
            elif status == "above_target" and focus_state == "maintenance":
                suggestions.append({
                    "category": "volume",
                    "message": f"Maintenance muscle {muscle_name.replace('_', ' ').title()} volume ({weekly_sets} sets) exceeds MAV ({mav} sets)",
                    "impact": "low",
                    "action": f"Consider reducing to MEV-MAV range ({mev}-{mav} sets) for maintenance"
                })
        
        return {
            "muscle_volume": analysis,
            "total_weekly_sets": sum(muscle_volume.values()),
            "warnings": warnings,
            "suggestions": suggestions,
            "note": "Volume calculated using effective sets (RIR 0-4 count fully toward MEV/MRV, RIR 5-6 count 50%, RIR 7+ count 0%). Only sets close to failure contribute to hypertrophy stimulus. Focus muscles target MAV-MRV, maintenance muscles target MEV-MAV."
        }
    
    def _calculate_weekly_volume(self, workout_days: List[Dict]) -> Dict[str, int]:
        """
        Calculate total weekly sets per muscle group.
        
        Args:
            workout_days: List of workout day dicts with exercises
            
        Returns:
            Dict mapping muscle group name to total weekly sets
        """
        muscle_volume = {}
        
        for workout_day in workout_days:
            exercises = workout_day.get("exercises", [])
            
            for exercise in exercises:
                # Get exercise details
                exercise_id = exercise.get("exercise_id")
                if not exercise_id:
                    continue
                
                # Calculate effective sets (only RIR 0-4 count toward MEV/MRV)
                effective_sets = self._calculate_effective_sets(exercise)
                
                # Get muscle activations for this exercise via junction table
                muscle_links = (
                    self.db.query(ExerciseMuscle, MuscleGroupModel)
                    .join(MuscleGroupModel, ExerciseMuscle.muscle_group_id == MuscleGroupModel.id)
                    .filter(ExerciseMuscle.exercise_id == exercise_id)
                    .all()
                )
                
                # Weight sets by role (convert role to activation weight)
                # prime_mover=85%, synergist=55%, stabilizer=20%
                role_weights = {"prime_mover": 0.85, "synergist": 0.55, "stabilizer": 0.20}
                for link, muscle in muscle_links:
                    muscle_name = muscle.name
                    activation_weight = role_weights.get(link.role, 0.20)
                    
                    # Weight by activation percentage
                    weighted_sets = effective_sets * activation_weight
                    muscle_volume[muscle_name] = muscle_volume.get(muscle_name, 0) + weighted_sets
        
        return muscle_volume
    
    def _calculate_effective_sets(self, exercise: Dict) -> float:
        """
        Calculate effective sets - only sets close to failure (RIR 0-4) count toward MEV/MRV.
        
        References: Schoenfeld et al. (2017) - Volume landmarks research
        Only sets performed close to failure contribute to hypertrophy stimulus.
        
        Args:
            exercise: Exercise dict with target_sets_min, target_sets_max, target_rir
            
        Returns:
            Effective sets count (0.0 to sets_max)
        """
        sets_min = exercise.get("target_sets_min", 0)
        sets_max = exercise.get("target_sets_max", 0)
        avg_sets = (sets_min + sets_max) / 2 if sets_max > 0 else sets_min
        
        target_rir = exercise.get("target_rir")
        
        # If no RIR specified, assume effective (user hasn't set it yet)
        if target_rir is None:
            return avg_sets
        
        # RIR 0-4: Fully effective (close to failure)
        if target_rir <= EFFECTIVE_SET_RIR_THRESHOLD:
            return avg_sets
        
        # RIR 5-6: Partially effective (warm-up territory, minimal hypertrophy stimulus)
        elif target_rir <= 6:
            return avg_sets * 0.5
        
        # RIR 7+: Not effective for hypertrophy (too far from failure)
        else:
            return 0.0

