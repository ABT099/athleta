"""
Prescription Generator Service

Generates scientifically-validated training prescriptions for target RPE, RIR, and rest periods.

Based on:
- Zourdos et al. (2016): RPE-based autoregulation
- Schoenfeld et al. (2016): Rest interval research
- Grgic et al. (2018): Rest period meta-analysis
"""
from typing import Dict
from autoregulation.utils.constants import (
    ExerciseIntensityCategory,
    TrainingType,
    BASE_RPE_RANGES,
    BASE_REST_PERIODS,
    HYBRID_CATEGORY_MAPPING,
    PHASE_MODIFIERS,
    MICROCYCLE_RPE_MODIFIERS,
    COMPOUND_RPE_SAFETY_CAP,
    DELOAD_RPE_FLOOR,
    ABSOLUTE_RPE_FLOOR,
    ABSOLUTE_RPE_CEILING,
    MICROCYCLE_RPE_MODIFIER_DEFAULT
)


class PrescriptionGeneratorService:
    """
    Generates scientifically-validated training prescriptions.
    
    Enforces:
    - CNS Tax Rule: Compound exercises capped at RPE 9.0
    - Inverse RPE/RIR Law: RIR = 10 - RPE (strictly enforced)
    - Deload Safety: Aggressive intensity reduction during deload
    - Microcycle Progression: Week-in-phase progressive overload
    - Hybrid Logic: Compounds follow strength rules, isolations follow hypertrophy rules
    """
    
    def generate_prescription(
        self,
        intensity_category: ExerciseIntensityCategory,
        training_type: TrainingType,
        training_phase: str,  # accumulation/intensification/realization/deload
        week_in_phase: int,   # 1-4 typically
        is_primary: bool = True
    ) -> Dict:
        """
        Generate target_rpe, target_rir, and rest_period_seconds.
        
        Args:
            intensity_category: Exercise intensity category from database
            training_type: Training goal (strength/hypertrophy/hybrid)
            training_phase: Current training phase
            week_in_phase: Week number within the phase (1-4)
            is_primary: Whether this is a primary exercise (affects rest period)
            
        Returns:
            Dict with target_rpe, target_rir, rest_period_seconds
        """
        # 1. For hybrid: route to appropriate base type
        effective_type = training_type
        if training_type == TrainingType.HYBRID:
            effective_type = HYBRID_CATEGORY_MAPPING[intensity_category]
        
        # 2. Get base RPE from effective type + category matrix
        rpe_range = BASE_RPE_RANGES[effective_type][intensity_category]
        base_rpe = rpe_range["max"]
        
        # 3. Apply phase modifier
        phase_mod = PHASE_MODIFIERS.get(training_phase, {"rpe": 0, "rest": 1.0})
        target_rpe = base_rpe + phase_mod["rpe"]
        
        # 4. Apply microcycle progression (week-in-phase)
        # Skip for deload - deload is flat, no progression
        if training_phase != "deload":
            week_mod = MICROCYCLE_RPE_MODIFIERS.get(
                min(week_in_phase, 4), MICROCYCLE_RPE_MODIFIER_DEFAULT  # Cap at week 4 modifier
            )
            target_rpe += week_mod
        
        # 5. Apply safety caps
        # CNS Tax Rule: compounds capped at 9
        if intensity_category != ExerciseIntensityCategory.ISOLATION:
            target_rpe = min(target_rpe, COMPOUND_RPE_SAFETY_CAP)
        
        # Deload floor
        if training_phase == "deload":
            target_rpe = max(target_rpe, DELOAD_RPE_FLOOR)
        
        # Absolute bounds
        target_rpe = max(ABSOLUTE_RPE_FLOOR, min(ABSOLUTE_RPE_CEILING, target_rpe))
        
        # 6. Calculate RIR (Inverse Law - strictly enforced)
        target_rir = self._calculate_rir(target_rpe)
        
        # 7. Calculate rest period
        rest_range = BASE_REST_PERIODS[effective_type][intensity_category]
        rest_period = self._calculate_rest_period(
            rest_range, phase_mod["rest"], is_primary
        )
        
        return {
            "target_rpe": round(target_rpe, 1),
            "target_rir": target_rir,
            "rest_period_seconds": rest_period,
        }
    
    def _calculate_rir(self, rpe: float) -> int:
        """
        Inverse RPE/RIR Law: RIR = 10 - RPE
        
        Strictly enforced - this relationship must always hold.
        """
        return max(0, round(10 - rpe))
    
    def _calculate_rest_period(
        self,
        rest_range: Dict[str, int],
        phase_multiplier: float,
        is_primary: bool
    ) -> int:
        """
        Calculate rest period with phase and priority adjustments.
        
        Args:
            rest_range: Dict with min/max rest period values
            phase_multiplier: Phase-based rest multiplier
            is_primary: Whether exercise is primary (gets more rest)
            
        Returns:
            Rest period in seconds
        """
        # Primary exercises get max rest, accessories get midpoint
        base_rest = rest_range["max"] if is_primary else (
            (rest_range["min"] + rest_range["max"]) // 2
        )
        
        # Apply phase multiplier
        adjusted_rest = int(base_rest * phase_multiplier)
        
        # Clamp to range
        return max(rest_range["min"], min(rest_range["max"], adjusted_rest))


