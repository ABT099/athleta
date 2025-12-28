"""
Exercise Order Analyzer.

Validates exercise sequencing based on NSCA guidelines.
References: NSCA Essentials of Strength Training and Conditioning.
"""
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

from app.models import ExerciseMuscle, MuscleGroupModel
from app.utils.constants import (
    ExerciseIntensityCategory,
    TrainingType,
    HYPERTROPHY_PRE_EXHAUST_ALLOWED, STRENGTH_PRE_EXHAUST_ALLOWED,
    TIER_1_SPINAL_PATTERNS, TIER_5_CORE_PATTERNS, INTENSITY_CATEGORY_TIER_MAP,
    FocusArea
)


class ExerciseOrderAnalyzer:
    """
    Analyzes exercise order within workouts using constraint-based priority system.
    
    Tier Hierarchy (Safety > Tier > Focus):
    1. Tier 1: High-Risk Spinal Loading (Squat, Deadlift, Olympic) - ALWAYS first
    2. Tier 2: Primary Compounds (compound_heavy) - Sort: Focus → Non-Focus
    3. Tier 3: Secondary Compounds (compound_moderate) - Sort: Focus → Non-Focus
    4. Tier 4: Standard Isolation - Sort: Focus → Non-Focus
    5. Tier 5: Core/Stabilizers - ALWAYS last (even if Focus)
    
    References: NSCA Essentials of Strength Training and Conditioning
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def analyze(
        self,
        workout_days: List[Dict],
        training_type: Optional[TrainingType] = None,
        focus_areas: Optional[List[str]] = None
    ) -> Dict:
        """
        Analyze exercise order in all workout days using constraint-based priority system.
        
        Uses 5-tier hierarchy: Safety Constraints > Compound/Isolation Tier > Focus Status
        
        Args:
            workout_days: List of workout day dicts with exercises
            training_type: Optional training type (strength/hypertrophy/hybrid)
            focus_areas: Optional list of focus areas (e.g., ["chest", "back"])
            
        Returns:
            Dict with order analysis and violations
        """
        all_violations = []
        all_suggestions = []
        workout_scores = []
        
        # Expand focus areas to muscle groups
        focus_muscle_groups = self._expand_focus_areas(focus_areas or [])
        
        for workout_day in workout_days:
            exercises = workout_day.get("exercises", [])
            if not exercises:
                continue
            
            # Sort exercises by order_in_workout
            sorted_exercises = sorted(exercises, key=lambda x: x.get("order_in_workout", 0))
            
            # Analyze order with constraint-based tier system
            violations, suggestions = self._check_tier_based_order(
                sorted_exercises,
                training_type,
                focus_muscle_groups
            )
            
            # Calculate order score (0-100)
            score = self._calculate_order_score(sorted_exercises, violations, training_type)
            
            workout_scores.append(score)
            all_violations.extend(violations)
            all_suggestions.extend(suggestions)
        
        avg_score = sum(workout_scores) / len(workout_scores) if workout_scores else 100
        
        return {
            "average_score": round(avg_score, 1),
            "violations": all_violations,
            "suggestions": all_suggestions,
            "workout_scores": workout_scores,
        }
    
    def _check_tier_based_order(
        self,
        exercises: List[Dict],
        training_type: Optional[TrainingType] = None,
        focus_muscle_groups: Optional[set] = None
    ) -> tuple[List[Dict], List[Dict]]:
        """
        Check exercise order using constraint-based tier system.
        
        Tier hierarchy: Safety > Tier > Focus
        1. Tier 1 (Spinal Loading) - ALWAYS first
        2. Tier 2-4 - Sort by tier, then by focus within tier
        3. Tier 5 (Core) - ALWAYS last
        
        Args:
            exercises: List of exercises sorted by order_in_workout
            training_type: Training type (strength/hypertrophy/hybrid)
            focus_muscle_groups: Set of muscle groups that are focus areas
            
        Returns:
            Tuple of (violations, suggestions)
        """
        violations = []
        suggestions = []
        focus_muscle_groups = focus_muscle_groups or set()
        
        # Determine if pre-exhaust is allowed
        allow_pre_exhaust = False
        if training_type == TrainingType.HYPERTROPHY:
            allow_pre_exhaust = HYPERTROPHY_PRE_EXHAUST_ALLOWED
        elif training_type == TrainingType.STRENGTH:
            allow_pre_exhaust = STRENGTH_PRE_EXHAUST_ALLOWED
        
        exercise_ids = [ex.get("exercise_id") for ex in exercises if ex.get("exercise_id")]
        if not exercise_ids:
            return [], []
        
        from app.models import Exercise
        # Load all exercises upfront
        all_exercises = (
            self.db.query(Exercise)
            .filter(Exercise.id.in_(exercise_ids))
            .all()
        )
        exercise_map = {ex.id: ex for ex in all_exercises}
        
        # Load all ExerciseMuscle links upfront
        all_muscle_links = (
            self.db.query(ExerciseMuscle, MuscleGroupModel.name)
            .join(MuscleGroupModel, ExerciseMuscle.muscle_group_id == MuscleGroupModel.id)
            .filter(
                ExerciseMuscle.exercise_id.in_(exercise_ids),
                ExerciseMuscle.role == "prime_mover"  # Primary only
            )
            .all()
        )
        muscle_map = {}
        for link, muscle_name in all_muscle_links:
            if link.exercise_id not in muscle_map:
                muscle_map[link.exercise_id] = []
            muscle_map[link.exercise_id].append(muscle_name)
        
        # Get tier and focus status for all exercises
        exercise_tiers = []
        for exercise in exercises:
            exercise_id = exercise.get("exercise_id")
            if not exercise_id:
                continue
            
            ex_details = self._get_exercise_details_from_maps(
                exercise_id, exercise_map, muscle_map
            )
            if not ex_details:
                continue
            
            tier = self._get_exercise_tier(ex_details)
            is_focus = self._is_focus_exercise(ex_details, focus_muscle_groups)
            exercise_tiers.append({
                "exercise": exercise,
                "details": ex_details,
                "tier": tier,
                "is_focus": is_focus,
                "index": len(exercise_tiers)
            })
        
        # Check tier violations
        for i in range(len(exercise_tiers) - 1):
            current = exercise_tiers[i]
            next_ex = exercise_tiers[i + 1]
            
            current_tier = current["tier"]
            next_tier = next_ex["tier"]
            current_name = current["details"]["name"]
            next_name = next_ex["details"]["name"]
            
            # Tier 1 violations: Spinal loading must be first
            if current_tier != 1 and next_tier == 1:
                violations.append({
                    "severity": "high",
                    "category": "order",
                    "message": f"'{next_name}' should be performed first (Tier 1: spinal loading)",
                    "affected_items": [current_name, next_name],
                    "recommendation": f"Move '{next_name}' to the beginning of the workout for safety"
                })
            
            # Tier 5 violations: Core must be last
            if current_tier == 5 and next_tier != 5:
                violations.append({
                    "severity": "high",
                    "category": "order",
                    "message": f"Core exercise '{current_name}' should be performed last (Tier 5: stabilizers)",
                    "affected_items": [current_name, next_name],
                    "recommendation": f"Move '{current_name}' to the end of the workout, even if it's a focus area"
                })
            
            # Within-tier focus violations: Focus exercises should come before non-focus in same tier
            if current_tier == next_tier and current_tier not in [1, 5]:  # Tiers 1 and 5 ignore focus
                if not current["is_focus"] and next_ex["is_focus"]:
                    suggestions.append({
                        "category": "order",
                        "message": f"Focus exercise '{next_name}' placed after non-focus '{current_name}' in same tier",
                        "impact": "low",
                        "action": f"Consider moving '{next_name}' before '{current_name}' to prioritize focus area"
                    })
            
            # Cross-tier violations: Lower tier should not come before higher tier
            if current_tier > next_tier and next_tier not in [1, 5]:  # Allow Tier 1/5 to override
                if current_tier == 5:
                    # Already handled above
                    pass
                else:
                    violations.append({
                        "severity": "medium",
                        "category": "order",
                        "message": f"Higher tier exercise '{next_name}' (Tier {next_tier}) placed after lower tier '{current_name}' (Tier {current_tier})",
                        "affected_items": [current_name, next_name],
                        "recommendation": f"Move '{next_name}' before '{current_name}' for optimal performance"
                    })
            
            # Pre-exhaust check (hypertrophy only, same muscle)
            if allow_pre_exhaust:
                if (current["details"]["exercise_type"] == "isolation" and
                    next_ex["details"]["exercise_type"] == "compound" and
                    self._same_primary_muscle(current["details"], next_ex["details"])):
                    # Pre-exhaust is acceptable for hypertrophy
                    suggestions.append({
                        "category": "order",
                        "message": f"Pre-exhaust pattern: '{current_name}' before '{next_name}' (same muscle)",
                        "impact": "low",
                        "action": "This is acceptable for hypertrophy training"
                    })
        
        return violations, suggestions
    
    
    def _get_exercise_details_from_maps(
        self,
        exercise_id: int,
        exercise_map: Dict,
        muscle_map: Dict
    ) -> Optional[Dict]:
        """Get exercise details from pre-loaded maps."""
        ex = exercise_map.get(exercise_id)
        if not ex:
            return None
        
        # Get intensity_category with fallback logic
        intensity_category = ex.intensity_category
        if not intensity_category:
            intensity_category = self._get_intensity_category_with_fallback(
                ex.exercise_type, ex.movement_pattern
            )
        
        # Get primary muscles from pre-loaded map
        primary_muscles = muscle_map.get(exercise_id, [])
        
        return {
            "id": ex.id,
            "name": ex.name,
            "exercise_type": ex.exercise_type,
            "intensity_category": intensity_category,
            "primary_muscles": primary_muscles,
            "movement_pattern": ex.movement_pattern,
        }
    
    def _get_intensity_category_with_fallback(
        self,
        exercise_type: Optional[str],
        movement_pattern: Optional[str]
    ) -> ExerciseIntensityCategory:
        """
        Infer intensity_category from exercise_type and movement_pattern.
        
        Fallback logic:
        - Heavy compounds: squat/hinge patterns with compound type
        - Moderate compounds: push/pull patterns with compound type
        - Isolation: isolation type or unknown
        """
        if not exercise_type:
            return ExerciseIntensityCategory.ISOLATION
        
        exercise_type_lower = exercise_type.lower()
        movement_pattern_lower = (movement_pattern or "").lower()
        
        # Heavy compounds: squat/hinge patterns
        if exercise_type_lower == "compound":
            if movement_pattern_lower in ["squat", "hinge"]:
                return ExerciseIntensityCategory.COMPOUND_HEAVY
            elif movement_pattern_lower in ["push", "pull"]:
                return ExerciseIntensityCategory.COMPOUND_MODERATE
            else:
                # Default compound to moderate
                return ExerciseIntensityCategory.COMPOUND_MODERATE
        
        # Isolation exercises
        elif exercise_type_lower == "isolation":
            return ExerciseIntensityCategory.ISOLATION
        
        # Default fallback
        return ExerciseIntensityCategory.ISOLATION
    
    def _get_exercise_tier(self, exercise: Dict) -> int:
        """
        Determine exercise tier using constraint-based priority system.
        
        Returns:
            1: Tier 1 (Spinal loading - ALWAYS first)
            2: Tier 2 (Primary compounds - compound_heavy)
            3: Tier 3 (Secondary compounds - compound_moderate)
            4: Tier 4 (Standard isolation)
            5: Tier 5 (Core/stabilizers - ALWAYS last)
        """
        name_lower = exercise.get("name", "").lower()
        movement_pattern = (exercise.get("movement_pattern") or "").lower()
        
        # Tier 1: Spinal loading patterns
        for pattern in TIER_1_SPINAL_PATTERNS:
            if pattern in name_lower or pattern in movement_pattern:
                return 1
        
        # Tier 5: Core/stabilizer patterns
        for pattern in TIER_5_CORE_PATTERNS:
            if pattern in name_lower or pattern in movement_pattern:
                return 5
        
        # Use intensity_category for tier mapping
        intensity_category = exercise.get("intensity_category")
        if intensity_category:
            try:
                if isinstance(intensity_category, str):
                    intensity_category = ExerciseIntensityCategory(intensity_category)
                tier = INTENSITY_CATEGORY_TIER_MAP.get(intensity_category, 4)
                return tier
            except (ValueError, AttributeError):
                pass
        
        # Fallback: use exercise_type
        exercise_type = exercise.get("exercise_type", "").lower()
        if exercise_type == "compound":
            return 3  # Default to moderate compound
        else:
            return 4  # Default to isolation
    
    def _is_focus_exercise(self, exercise: Dict, focus_muscle_groups: set) -> bool:
        """
        Check if exercise targets a focus muscle group.
        
        Args:
            exercise: Exercise details dict
            focus_muscle_groups: Set of muscle group names that are focus areas
            
        Returns:
            True if exercise targets a focus muscle group
        """
        if not focus_muscle_groups:
            return False
        
        primary_muscles = exercise.get("primary_muscles", [])
        for muscle_name in primary_muscles:
            if muscle_name in focus_muscle_groups:
                return True
        
        return False
    
    def _expand_focus_areas(self, focus_areas: List[str]) -> set:
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
    
    def _get_muscle_size(self, exercise: Dict) -> str:
        """Get muscle size category for primary muscle from database."""
        primary_muscles = exercise.get("primary_muscles", [])
        if not primary_muscles:
            return "medium"
        
        # Query muscle size from database
        muscle = self.db.query(MuscleGroupModel).filter(
            MuscleGroupModel.name == primary_muscles[0]
        ).first()
        
        if muscle:
            return muscle.size
        
        return "medium"
    
    def _same_primary_muscle(self, ex1: Dict, ex2: Dict) -> bool:
        """Check if exercises target the same primary muscle."""
        muscles1 = set(ex1.get("primary_muscles", []))
        muscles2 = set(ex2.get("primary_muscles", []))
        return bool(muscles1 & muscles2)
    
    def _calculate_order_score(
        self,
        exercises: List[Dict],
        violations: List[Dict],
        training_type: Optional[TrainingType] = None
    ) -> float:
        """
        Calculate order quality score (0-100).
        
        Args:
            exercises: List of exercises
            violations: List of violations found
            training_type: Training type for context
            
        Returns:
            Score from 0-100
        """
        if not exercises:
            return 100.0
        
        # Base score
        base_score = 100.0
        
        # Deduct points for violations
        for violation in violations:
            if violation["severity"] == "high":
                base_score -= 15
            elif violation["severity"] == "medium":
                base_score -= 10
            else:
                base_score -= 5
        
        # Bonus for good ordering (compounds first, isolations last)
        exercise_ids = [ex.get("exercise_id") for ex in exercises if ex.get("exercise_id")]
        if exercise_ids:
            from app.models import Exercise
            all_exercises = (
                self.db.query(Exercise)
                .filter(Exercise.id.in_(exercise_ids))
                .all()
            )
            exercise_map = {ex.id: ex for ex in all_exercises}
        else:
            exercise_map = {}
        
        compound_count = 0
        first_isolation_idx = -1
        for i, ex in enumerate(exercises):
            exercise_id = ex.get("exercise_id")
            if not exercise_id:
                continue
            exercise_obj = exercise_map.get(exercise_id)
            if not exercise_obj:
                continue
            if exercise_obj.exercise_type == "compound":
                compound_count += 1
            elif exercise_obj.exercise_type == "isolation" and first_isolation_idx == -1:
                first_isolation_idx = i
        
        isolation_count = len(exercises) - compound_count
        
        if compound_count > 0 and isolation_count > 0:
            # Check if compounds come before isolations
            if first_isolation_idx > compound_count - 1:
                base_score += 5  # Bonus for good ordering
        
        return max(0.0, min(100.0, base_score))

