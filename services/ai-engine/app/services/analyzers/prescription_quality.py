"""
Prescription Quality Analyzer.

Validates RPE/RIR/rest periods against training type and phase.
Uses PrescriptionGeneratorService to get expected values.
"""
from typing import Dict, List, Optional, Set
from sqlalchemy.orm import Session

from app.models import ExerciseMuscle, MuscleGroupModel
from app.utils.constants import (
    TrainingType, ExerciseIntensityCategory, FOCUS_AREA_RPE_BONUS,
    FocusArea
)
from app.services.prescription_generator import PrescriptionGeneratorService


class PrescriptionQualityAnalyzer:
    """
    Analyzes prescription quality (RPE/RIR/rest).
    
    Checks:
    - Missing prescriptions
    - Inconsistent RPE/RIR (should follow RIR = 10 - RPE)
    - Inappropriate rest periods
    - RPE/RIR outside expected ranges
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.prescription_generator = PrescriptionGeneratorService()
    
    def analyze(
        self,
        exercises: List[Dict],
        training_type: TrainingType,
        phase: str = "accumulation",
        week_in_phase: int = 1,
        focus_areas: Optional[List[str]] = None
    ) -> Dict:
        """
        Analyze prescription quality for all exercises with focus-aware RPE allowance.
        
        Args:
            exercises: List of exercise dicts with prescriptions
            training_type: Training type (strength/hypertrophy/hybrid)
            phase: Training phase (accumulation/intensification/realization/deload)
            week_in_phase: Week number within phase
            focus_areas: Optional list of focus areas (e.g., ["chest", "back"])
            
        Returns:
            Dict with prescription quality analysis
        """
        # Expand focus areas to muscle groups
        focus_muscle_groups = self._expand_focus_areas(focus_areas or [])
        
        # Normalize phase string (lowercase, handle variations)
        if isinstance(phase, str):
            phase = phase.lower()
            phase_map = {
                "accumulation": "accumulation",
                "intensification": "intensification",
                "realization": "realization",
                "deload": "deload",
                "peaking": "realization",  # Alias
                "volume": "accumulation",  # Alias
                "strength": "intensification",  # Alias
            }
            phase = phase_map.get(phase, "accumulation")
        else:
            phase = "accumulation"  # Default
        warnings = []
        suggestions = []
        missing_count = 0
        inconsistent_count = 0
        
        for exercise in exercises:
            exercise_id = exercise.get("exercise_id")
            if not exercise_id:
                continue
            
            # Get exercise details
            from app.models import Exercise
            ex = self.db.query(Exercise).filter(Exercise.id == exercise_id).first()
            if not ex:
                continue
            
            # Check if exercise targets focus muscle
            is_focus_exercise = self._is_focus_exercise(ex, focus_muscle_groups)
            
            # Get actual prescriptions
            target_rpe = exercise.get("target_rpe")
            target_rir = exercise.get("target_rir")
            rest_period = exercise.get("rest_period_seconds")
            
            # Check for missing prescriptions
            if target_rpe is None and target_rir is None:
                missing_count += 1
                focus_note = " (focus muscle - consider higher RPE)" if is_focus_exercise else ""
                suggestions.append({
                    "category": "prescription",
                    "message": f"Missing RPE/RIR for '{ex.name}'{focus_note}",
                    "impact": "medium",
                    "action": "Auto-generate prescription based on training phase"
                })
                continue
            
            # Get expected prescription with fallback
            intensity_category = ex.intensity_category
            if not intensity_category:
                # Fallback: infer from exercise_type and movement_pattern
                intensity_category = _get_intensity_category_with_fallback(
                    ex.exercise_type, ex.movement_pattern
                )
            else:
                try:
                    intensity_category = ExerciseIntensityCategory(intensity_category)
                except (ValueError, AttributeError):
                    intensity_category = ExerciseIntensityCategory.ISOLATION
            
            expected = self.prescription_generator.generate_prescription(
                intensity_category=intensity_category,
                training_type=training_type,
                training_phase=phase,
                week_in_phase=week_in_phase,
                is_primary=exercise.get("is_primary", True)
            )
            
            # Adjust expected RPE for focus exercises
            expected_rpe = expected["target_rpe"]
            if is_focus_exercise:
                expected_rpe += FOCUS_AREA_RPE_BONUS
                # Cap at 10.0
                expected_rpe = min(expected_rpe, 10.0)
            
            # Check RPE/RIR consistency
            if target_rpe is not None and target_rir is not None:
                expected_rir = round(10 - target_rpe)
                if abs(target_rir - expected_rir) > 0:
                    inconsistent_count += 1
                    warnings.append({
                        "severity": "medium",
                        "category": "prescription",
                        "message": f"RPE/RIR inconsistency for '{ex.name}': RPE {target_rpe} should have RIR {expected_rir}, but has {target_rir}",
                        "affected_items": [ex.name],
                        "recommendation": f"Adjust RIR to {expected_rir} to match RPE {target_rpe} (RIR = 10 - RPE)"
                    })
            
            # Check RPE against expected range (with focus allowance)
            if target_rpe is not None:
                rpe_diff = abs(target_rpe - expected_rpe)
                
                # For focus exercises, allow up to FOCUS_AREA_RPE_BONUS difference
                tolerance = 1.0
                if is_focus_exercise:
                    tolerance = 1.0 + FOCUS_AREA_RPE_BONUS
                
                if rpe_diff > tolerance:
                    if is_focus_exercise and target_rpe < expected_rpe:
                        # Focus exercise with low RPE - suggest increasing
                        suggestions.append({
                            "category": "prescription",
                            "message": f"Focus exercise '{ex.name}' has RPE {target_rpe}, consider increasing to {expected_rpe:.1f} for optimal stimulus",
                            "impact": "medium",
                            "action": f"Increase RPE to {expected_rpe:.1f} to maximize focus area development"
                        })
                    else:
                        suggestions.append({
                            "category": "prescription",
                            "message": f"RPE {target_rpe} for '{ex.name}' differs significantly from expected {expected_rpe:.1f} for {phase} phase",
                            "impact": "low",
                            "action": f"Consider adjusting RPE to {expected_rpe:.1f} for optimal phase progression"
                        })
            
            # Check rest period
            if rest_period is not None:
                expected_rest = expected["rest_period_seconds"]
                rest_diff = abs(rest_period - expected_rest) / expected_rest
                
                if rest_diff > 0.3:  # More than 30% difference
                    suggestions.append({
                        "category": "prescription",
                        "message": f"Rest period {rest_period}s for '{ex.name}' differs from expected {expected_rest}s",
                        "impact": "low",
                        "action": f"Consider adjusting rest to {expected_rest}s for optimal recovery"
                    })
        
        return {
            "missing_prescriptions": missing_count,
            "inconsistent_rpe_rir": inconsistent_count,
            "warnings": warnings,
            "suggestions": suggestions,
        }
    
    def _is_focus_exercise(self, exercise, focus_muscle_groups: set) -> bool:
        """
        Check if exercise targets a focus muscle group.
        
        Args:
            exercise: Exercise model object
            focus_muscle_groups: Set of muscle group names that are focus areas
            
        Returns:
            True if exercise targets a focus muscle group
        """
        if not focus_muscle_groups:
            return False
        
        # Get primary muscles via junction table (activation >= 70%)
        muscle_links = (
            self.db.query(ExerciseMuscle, MuscleGroupModel)
            .join(MuscleGroupModel, ExerciseMuscle.muscle_group_id == MuscleGroupModel.id)
            .filter(
                ExerciseMuscle.exercise_id == exercise.id,
                ExerciseMuscle.role == "prime_mover"  # Primary targets only
            )
            .all()
        )
        
        for link, muscle in muscle_links:
            if muscle.name in focus_muscle_groups:
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


def _get_intensity_category_with_fallback(
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

