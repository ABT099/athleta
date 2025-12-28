"""
Muscle Group Balance Analyzer.

Analyzes push/pull and upper/lower balance ratios.
References: Contreras, Helms - Push/pull balance for shoulder health.
"""
from typing import Dict, List, Optional, Set
from sqlalchemy.orm import Session

from app.models import Exercise, ExerciseMuscle, MuscleGroupModel
from app.utils.constants import (
    PUSH_PULL_RATIO_TARGET, PUSH_PULL_RATIO_TOLERANCE,
    UPPER_LOWER_RATIO_TARGET, UPPER_LOWER_RATIO_TOLERANCE,
    EFFECTIVE_SET_RIR_THRESHOLD, FocusArea
)


class MuscleGroupBalanceAnalyzer:
    """
    Analyzes muscle group balance in the plan.
    
    Checks:
    - Push/Pull ratio (1:1 optimal)
    - Upper/Lower ratio (context-dependent)
    - Antagonist pair balance
    """
    
    # Define muscle groups for push/pull/upper/lower
    PUSH_MUSCLES = {"mid_chest", "upper_chest", "lower_chest", "anterior_delt", "triceps"}
    PULL_MUSCLES = {"lats", "mid_back", "upper_traps", "lower_traps", "posterior_delt", "biceps"}
    UPPER_MUSCLES = {
        "mid_chest", "upper_chest", "lower_chest", 
        "anterior_delt", "lateral_delt", "posterior_delt",
        "lats", "mid_back", "upper_traps", "lower_traps",
        "biceps", "triceps", "forearms"
    }
    LOWER_MUSCLES = {"quadriceps", "hamstrings", "glutes", "calves", "hip_flexors"}
    
    def __init__(self, db: Session):
        self.db = db
    
    def analyze(
        self,
        workout_days: List[Dict],
        focus_areas: Optional[List[str]] = None
    ) -> Dict:
        """
        Analyze muscle group balance with focus-aware tolerance.
        
        Args:
            workout_days: List of workout day dicts with exercises
            focus_areas: Optional list of focus areas (e.g., ["chest", "back"])
            
        Returns:
            Dict with balance analysis
        """
        # Expand focus areas to muscle groups
        focus_muscle_groups = self._expand_focus_areas(focus_areas or [])
        
        # Calculate volume per muscle group
        muscle_volume = self._calculate_muscle_volume(workout_days)
        
        # Calculate push/pull volume
        push_volume = sum(muscle_volume.get(mg, 0) for mg in self.PUSH_MUSCLES)
        pull_volume = sum(muscle_volume.get(mg, 0) for mg in self.PULL_MUSCLES)
        
        # Calculate upper/lower volume
        upper_volume = sum(muscle_volume.get(mg, 0) for mg in self.UPPER_MUSCLES)
        lower_volume = sum(muscle_volume.get(mg, 0) for mg in self.LOWER_MUSCLES)
        
        # Check if focus areas create intentional imbalance
        focus_push = any(mg in focus_muscle_groups for mg in self.PUSH_MUSCLES)
        focus_pull = any(mg in focus_muscle_groups for mg in self.PULL_MUSCLES)
        focus_upper = any(mg in focus_muscle_groups for mg in self.UPPER_MUSCLES)
        focus_lower = any(mg in focus_muscle_groups for mg in self.LOWER_MUSCLES)
        
        # Calculate ratios
        push_pull_ratio = push_volume / pull_volume if pull_volume > 0 else float('inf')
        upper_lower_ratio = upper_volume / lower_volume if lower_volume > 0 else float('inf')
        
        # Assess push/pull balance (with focus tolerance)
        push_pull_diff = abs(push_pull_ratio - PUSH_PULL_RATIO_TARGET)
        push_pull_status = "optimal" if push_pull_diff <= PUSH_PULL_RATIO_TOLERANCE else "imbalanced"
        
        # Assess upper/lower balance (with focus tolerance)
        upper_lower_diff = abs(upper_lower_ratio - UPPER_LOWER_RATIO_TARGET)
        upper_lower_status = "optimal" if upper_lower_diff <= UPPER_LOWER_RATIO_TOLERANCE else "imbalanced"
        
        # Check antagonist pairs
        antagonist_analysis = self._analyze_antagonist_pairs(muscle_volume)
        
        # Generate warnings and suggestions
        warnings = []
        suggestions = []
        strengths = []
        
        # Push/pull balance
        if push_pull_status == "optimal":
            strengths.append("Excellent push/pull balance")
        else:
            # Check if imbalance is intentional due to focus
            intentional_imbalance = False
            if push_volume > pull_volume and focus_push and not focus_pull:
                intentional_imbalance = True
            elif pull_volume > push_volume and focus_pull and not focus_push:
                intentional_imbalance = True
            
            if intentional_imbalance:
                # Reduce warning severity for intentional focus-driven imbalance
                suggestions.append({
                    "category": "balance",
                    "message": f"Push/pull ratio ({push_pull_ratio:.2f}) is imbalanced but acceptable due to focus areas",
                    "impact": "low",
                    "action": "This imbalance is intentional for focus area development"
                })
            else:
                if push_volume > pull_volume:
                    warnings.append({
                        "severity": "high",
                        "category": "balance",
                        "message": f"Push volume ({push_volume:.1f} sets) exceeds pull volume ({pull_volume:.1f} sets)",
                        "affected_items": list(self.PUSH_MUSCLES),
                        "recommendation": f"Add {push_volume - pull_volume:.0f} more pull sets to balance shoulder health"
                    })
                else:
                    warnings.append({
                        "severity": "medium",
                        "category": "balance",
                        "message": f"Pull volume ({pull_volume:.1f} sets) exceeds push volume ({push_volume:.1f} sets)",
                        "affected_items": list(self.PULL_MUSCLES),
                        "recommendation": f"Add {pull_volume - push_volume:.0f} more push sets for balanced development"
                    })
        
        # Upper/lower balance
        if upper_lower_status == "optimal":
            strengths.append("Good upper/lower balance")
        else:
            # Check if imbalance is intentional due to focus
            intentional_imbalance = False
            if upper_volume > lower_volume and focus_upper and not focus_lower:
                intentional_imbalance = True
            elif lower_volume > upper_volume and focus_lower and not focus_upper:
                intentional_imbalance = True
            
            if intentional_imbalance:
                suggestions.append({
                    "category": "balance",
                    "message": f"Upper/lower ratio ({upper_lower_ratio:.2f}) is imbalanced but acceptable due to focus areas",
                    "impact": "low",
                    "action": "This imbalance is intentional for focus area development"
                })
            else:
                if upper_volume > lower_volume:
                    suggestions.append({
                        "category": "balance",
                        "message": f"Upper body volume ({upper_volume:.1f} sets) exceeds lower body ({lower_volume:.1f} sets)",
                        "impact": "low",
                        "action": "Consider adding more leg exercises for balanced development"
                    })
                else:
                    suggestions.append({
                        "category": "balance",
                        "message": f"Lower body volume ({lower_volume:.1f} sets) exceeds upper body ({upper_volume:.1f} sets)",
                        "impact": "low",
                        "action": "Consider adding more upper body exercises for balanced development"
                    })
        
        return {
            "push_pull": {
                "push_volume": round(push_volume, 1),
                "pull_volume": round(pull_volume, 1),
                "ratio": round(push_pull_ratio, 2),
                "target": PUSH_PULL_RATIO_TARGET,
                "status": push_pull_status,
            },
            "upper_lower": {
                "upper_volume": round(upper_volume, 1),
                "lower_volume": round(lower_volume, 1),
                "ratio": round(upper_lower_ratio, 2),
                "target": UPPER_LOWER_RATIO_TARGET,
                "status": upper_lower_status,
            },
            "antagonist_pairs": antagonist_analysis,
            "warnings": warnings,
            "suggestions": suggestions,
            "strengths": strengths,
        }
    
    def _calculate_muscle_volume(self, workout_days: List[Dict]) -> Dict[str, float]:
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
                exercise_id = exercise.get("exercise_id")
                if not exercise_id:
                    continue
                
                # Calculate effective sets (only RIR 0-4 count toward volume landmarks)
                effective_sets = self._calculate_effective_sets(exercise)
                
                # Get muscle activations for this exercise via junction table
                muscle_links = (
                    self.db.query(ExerciseMuscle, MuscleGroupModel)
                    .join(MuscleGroupModel, ExerciseMuscle.muscle_group_id == MuscleGroupModel.id)
                    .filter(ExerciseMuscle.exercise_id == exercise_id)
                    .all()
                )
                
                # Weight sets by role (convert role to activation weight)
                # Use constant from constants.py
                from app.utils.constants import MUSCLE_ROLE_WEIGHTS
                for link, muscle in muscle_links:
                    muscle_name = muscle.name
                    activation_weight = MUSCLE_ROLE_WEIGHTS.get(link.role, MUSCLE_ROLE_WEIGHTS["stabilizer"])
                    
                    # Weight by activation percentage
                    # Primary muscles (prime_mover) get full weight, secondary get proportional
                    weighted_sets = effective_sets * activation_weight
                    
                    muscle_volume[muscle_name] = muscle_volume.get(muscle_name, 0) + weighted_sets
        
        return muscle_volume
    
    def _calculate_effective_sets(self, exercise: Dict) -> float:
        """
        Calculate effective sets - only sets close to failure (RIR 0-4) count toward volume landmarks.
        
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
    
    def _analyze_antagonist_pairs(self, muscle_volume: Dict[str, float]) -> Dict:
        """
        Analyze balance between antagonist muscle pairs.
        
        Args:
            muscle_volume: Dict mapping muscle group to volume
            
        Returns:
            Dict with antagonist pair analysis
        """
        # Define antagonist pairs using muscle names
        antagonist_pairs = [
            ("mid_chest", "mid_back"),
            ("anterior_delt", "posterior_delt"),
            ("biceps", "triceps"),
            ("quadriceps", "hamstrings"),
        ]
        
        pairs_analysis = {}
        
        for muscle1, muscle2 in antagonist_pairs:
            vol1 = muscle_volume.get(muscle1, 0)
            vol2 = muscle_volume.get(muscle2, 0)
            
            if vol1 == 0 and vol2 == 0:
                continue
            
            ratio = vol1 / vol2 if vol2 > 0 else float('inf')
            status = "balanced" if 0.8 <= ratio <= 1.2 else "imbalanced"
            
            pairs_analysis[f"{muscle1}_{muscle2}"] = {
                muscle1: round(vol1, 1),
                muscle2: round(vol2, 1),
                "ratio": round(ratio, 2),
                "status": status,
            }
        
        return pairs_analysis
    
    def _expand_focus_areas(self, focus_areas: List[str]) -> Set[str]:
        """
        Expand focus areas to muscle group names.
        
        Args:
            focus_areas: List of focus area strings (e.g., ["chest", "back"])
            
        Returns:
            Set of muscle group names
        """
        if not focus_areas:
            return set()
        
        # Map focus areas to muscle names
        focus_to_muscles = {
            "chest": {"upper_chest", "mid_chest", "lower_chest"},
            "back": {"lats", "upper_traps", "mid_back", "lower_traps"},
            "shoulders": {"anterior_delt", "lateral_delt", "posterior_delt"},
            "arms": {"biceps", "triceps", "forearms"},
            "legs": {"quadriceps", "hamstrings", "glutes", "hip_flexors", "calves"},
            "core": {"abs", "erector_spinae"},
        }
        
        muscle_groups = set()
        for focus_area_str in focus_areas:
            try:
                focus_area_lower = focus_area_str.lower()
                # Try as FocusArea enum
                try:
                    focus_area = FocusArea(focus_area_lower)
                    muscles = focus_to_muscles.get(focus_area.value, set())
                    muscle_groups.update(muscles)
                except ValueError:
                    # Maybe it's a direct muscle name
                    muscle_groups.add(focus_area_lower)
            except (ValueError, KeyError):
                continue
        
        return muscle_groups
