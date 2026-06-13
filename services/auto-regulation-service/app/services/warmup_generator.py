"""
Warm-up set generation service.

Generates appropriate warm-up sets based on working weight and exercise characteristics.
"""
from typing import List, Dict, Optional
from autoregulation.models import Exercise
from autoregulation.utils.constants import (
    WARMUP_MAX_WEIGHT_PERCENTAGE, WARMUP_PEAK_INTENSITY_BOOST_MIN,
    WARMUP_PEAK_INTENSITY_BOOST_MAX, WARMUP_EARLY_INTENSITY_REDUCTION_MIN,
    WARMUP_EARLY_INTENSITY_REDUCTION_MAX, WARMUP_PEAK_PHASE_THRESHOLD,
    WARMUP_EARLY_PHASE_THRESHOLD, WARMUP_MIN_WEIGHT_PERCENTAGE
)


class WarmupGenerator:
    """
    Service for generating warm-up sets for exercises.
    
    Generates warm-up pyramids based on working weight and number of warm-up sets.
    """
    
    # Warm-up pyramid configurations
    WARMUP_PYRAMIDS = {
        0: [],  # No warm-up sets
        1: [
            {"weight_percentage": 0.60, "reps_min": 6, "reps_max": 10}
        ],
        2: [
            {"weight_percentage": 0.50, "reps_min": 6, "reps_max": 10},
            {"weight_percentage": 0.70, "reps_min": 4, "reps_max": 6}
        ],
        3: [
            {"weight_percentage": 0.45, "reps_min": 6, "reps_max": 10},
            {"weight_percentage": 0.65, "reps_min": 4, "reps_max": 6},
            {"weight_percentage": 0.85, "reps_min": 3, "reps_max": 4}
        ],
        4: [
            {"weight_percentage": 0.45, "reps_min": 6, "reps_max": 10},
            {"weight_percentage": 0.60, "reps_min": 4, "reps_max": 6},
            {"weight_percentage": 0.75, "reps_min": 3, "reps_max": 5},
            {"weight_percentage": 0.85, "reps_min": 2, "reps_max": 4}
        ]
    }
    
    def generate_warmup_sets(
        self,
        working_weight: float,
        num_warmup_sets: int,
        exercise_type: Optional[str] = None,
        adjusted_sets: Optional[int] = None,
        sets_range_position: Optional[float] = None,
        is_deload_week: Optional[bool] = None
    ) -> List[Dict]:
        """
        Generate warm-up sets based on working weight and number of sets.
        
        Adapts warmup intensity and volume based on training phase and set variations.
        
        Args:
            working_weight: The planned working weight (kg)
            num_warmup_sets: Number of warm-up sets (0-4)
            exercise_type: Exercise type ("compound" or "isolation") for validation
            adjusted_sets: The actual number of working sets planned (for context)
            sets_range_position: Position in min/max range (0.0 = at min, 1.0 = at max)
            is_deload_week: Whether this is a deload week (reduces warmup)
            
        Returns:
            List of warm-up set dictionaries with:
            - set_number: int (1-based)
            - weight_percentage: float
            - weight: float (calculated weight in kg)
            - reps_min: int
            - reps_max: int
            - is_warmup: bool (always True)
        """
        # Validate number of warm-up sets
        base_warmup_sets = max(0, min(4, int(num_warmup_sets)))
        
        # Apply adaptive adjustments based on context
        adjusted_warmup_sets = self._adjust_warmup_count_for_context(
            base_warmup_sets=base_warmup_sets,
            adjusted_sets=adjusted_sets,
            sets_range_position=sets_range_position,
            is_deload_week=is_deload_week
        )
        
        if adjusted_warmup_sets == 0:
            return []
        
        # Get pyramid configuration
        pyramid = self.WARMUP_PYRAMIDS.get(adjusted_warmup_sets, [])
        
        if not pyramid:
            return []
        
        # Adjust pyramid intensity based on set range position (for peak weeks)
        pyramid = self._adjust_pyramid_intensity(
            pyramid=pyramid,
            sets_range_position=sets_range_position
        )
        
        # Generate warm-up sets
        warmup_sets = []
        for idx, config in enumerate(pyramid, start=1):
            weight = round(working_weight * config["weight_percentage"] / 2.5) * 2.5  # Round to 2.5kg
            
            warmup_sets.append({
                "set_number": idx,
                "weight_percentage": config["weight_percentage"],
                "weight": weight,
                "reps_min": config["reps_min"],
                "reps_max": config["reps_max"],
                "is_warmup": True
            })
        
        return warmup_sets
    
    def _adjust_warmup_count_for_context(
        self,
        base_warmup_sets: int,
        adjusted_sets: Optional[int] = None,
        sets_range_position: Optional[float] = None,
        is_deload_week: Optional[bool] = None
    ) -> int:
        """
        Adjust warmup set count based on training context.
        
        Args:
            base_warmup_sets: Base number of warmup sets
            adjusted_sets: Actual working sets planned
            sets_range_position: Position in set range (0.0 = min, 1.0 = max)
            is_deload_week: Whether this is a deload week
            
        Returns:
            Adjusted number of warmup sets (0-4)
        """
        adjusted = base_warmup_sets
        
        # Deload week: reduce warmup by 1 (minimum 0)
        if is_deload_week:
            adjusted = max(0, adjusted - 1)
        
        # Peak phase (sets at maximum): consider adding warmup if high volume
        if sets_range_position is not None and sets_range_position >= 0.8:
            # At peak volume, ensure adequate warmup
            if adjusted_sets and adjusted_sets >= 5 and adjusted < 4:
                # High volume peak week: add one warmup set if room
                adjusted = min(4, adjusted + 1)
        
        # Early phase (sets at minimum): can reduce warmup slightly
        if sets_range_position is not None and sets_range_position <= 0.2:
            # Early phase with low volume: can reduce warmup
            if adjusted_sets and adjusted_sets <= 3 and adjusted > 1:
                # Low volume early week: reduce by 1 if above minimum
                adjusted = max(1, adjusted - 1)
        
        return max(0, min(4, adjusted))
    
    def _adjust_pyramid_intensity(
        self,
        pyramid: List[Dict],
        sets_range_position: Optional[float] = None
    ) -> List[Dict]:
        """
        Adjust warmup pyramid intensity based on training phase.
        
        For peak weeks, slightly increase final warmup intensity to better prepare
        for high-volume work.
        
        Args:
            pyramid: Base pyramid configuration
            sets_range_position: Position in set range (0.0 = min, 1.0 = max)
            
        Returns:
            Adjusted pyramid configuration
        """
        if not pyramid or sets_range_position is None:
            return pyramid
        
        # Create a copy to avoid modifying the original
        adjusted_pyramid = [config.copy() for config in pyramid]
        
        # Peak phase: increase final warmup intensity slightly
        if sets_range_position >= WARMUP_PEAK_PHASE_THRESHOLD and len(adjusted_pyramid) > 0:
            # Increase final warmup set intensity by 2-5% for better preparation
            final_set = adjusted_pyramid[-1]
            intensity_boost = WARMUP_PEAK_INTENSITY_BOOST_MIN + (sets_range_position - WARMUP_PEAK_PHASE_THRESHOLD) * ((WARMUP_PEAK_INTENSITY_BOOST_MAX - WARMUP_PEAK_INTENSITY_BOOST_MIN) / (1.0 - WARMUP_PEAK_PHASE_THRESHOLD))
            final_set["weight_percentage"] = min(WARMUP_MAX_WEIGHT_PERCENTAGE, final_set["weight_percentage"] + intensity_boost)
            # Slightly reduce reps for higher intensity
            if final_set["reps_min"] > 2:
                final_set["reps_min"] = max(2, final_set["reps_min"] - 1)
            if final_set["reps_max"] > 3:
                final_set["reps_max"] = max(3, final_set["reps_max"] - 1)
        
        # Early phase: can slightly reduce final intensity for easier transition
        elif sets_range_position <= WARMUP_EARLY_PHASE_THRESHOLD and len(adjusted_pyramid) > 0:
            final_set = adjusted_pyramid[-1]
            # Reduce final warmup intensity slightly (1-2%)
            intensity_reduction = WARMUP_EARLY_INTENSITY_REDUCTION_MIN + (WARMUP_EARLY_PHASE_THRESHOLD - sets_range_position) * ((WARMUP_EARLY_INTENSITY_REDUCTION_MAX - WARMUP_EARLY_INTENSITY_REDUCTION_MIN) / WARMUP_EARLY_PHASE_THRESHOLD)
            final_set["weight_percentage"] = max(WARMUP_MIN_WEIGHT_PERCENTAGE, final_set["weight_percentage"] - intensity_reduction)
        
        return adjusted_pyramid
    
    def determine_warmup_set_count(
        self,
        exercise: Exercise,
        is_primary: bool = True
    ) -> int:
        """
        Determine recommended number of warm-up sets based on exercise characteristics.
        
        Args:
            exercise: Exercise model
            is_primary: Whether this is a primary exercise (default: True)
            
        Returns:
            Recommended number of warm-up sets (0-4)
        """
        base_sets = 0
        
        # Base recommendation on exercise type
        if exercise.exercise_type == "compound":
            base_sets = 3  # Compound exercises need more warm-up
        elif exercise.exercise_type == "isolation":
            base_sets = 1  # Isolation exercises need less warm-up
        else:
            base_sets = 2  # Default for unknown types
        
        # Adjust based on complexity score (higher = more warm-up sets)
        # Complexity score typically ranges from 0.5 to 2.0
        complexity_adjustment = 0
        if exercise.complexity_score:
            if exercise.complexity_score >= 1.5:
                complexity_adjustment = 1
            elif exercise.complexity_score >= 1.2:
                complexity_adjustment = 0
            elif exercise.complexity_score <= 0.8:
                complexity_adjustment = -1
        
        # Adjust based on injury risk (higher = more warm-up sets)
        # Injury risk typically ranges from 0.0 to 1.0
        injury_adjustment = 0
        if exercise.injury_risk_level:
            if exercise.injury_risk_level >= 0.7:
                injury_adjustment = 1
            elif exercise.injury_risk_level >= 0.5:
                injury_adjustment = 0
            elif exercise.injury_risk_level <= 0.3:
                injury_adjustment = -1
        
        # Adjust based on whether it's a primary exercise
        primary_adjustment = 1 if is_primary else -1
        
        # Calculate total
        total_sets = base_sets + complexity_adjustment + injury_adjustment + primary_adjustment
        
        # Clamp to valid range (0-4)
        return max(0, min(4, total_sets))
    
    def get_warmup_pyramid_description(self, num_sets: int) -> str:
        """
        Get human-readable description of warm-up pyramid.
        
        Args:
            num_sets: Number of warm-up sets
            
        Returns:
            Description string
        """
        if num_sets == 0:
            return "No warm-up sets"
        elif num_sets == 1:
            return "Single warm-up set: ~60% of working weight for 6-10 reps"
        elif num_sets == 2:
            return "Mini warm-up pyramid: 50% (6-10 reps) → 70% (4-6 reps)"
        elif num_sets == 3:
            return "Full warm-up pyramid: 45% (6-10 reps) → 65% (4-6 reps) → 85% (3-4 reps)"
        elif num_sets == 4:
            return "Extended warm-up pyramid: 45% (6-10 reps) → 60% (4-6 reps) → 75% (3-5 reps) → 85% (2-4 reps)"
        else:
            return f"{num_sets} warm-up sets"

