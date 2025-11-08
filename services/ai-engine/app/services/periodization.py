"""
Advanced periodization models service.

Implements Daily Undulating Periodization (DUP) and Block Periodization
for optimized training progression.
"""
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum

from app.utils.constants import (
    TrainingType, TrainingPhase, TrainingExperience,
    PeriodizationModel, DUP_TRAINING_DAYS, BLOCK_PERIODIZATION_CONFIG
)


class DUPDay(str, Enum):
    """DUP training day types."""
    HIGH_VOLUME = "high_volume"
    MODERATE = "moderate"
    HIGH_INTENSITY = "high_intensity"


class PeriodizationService:
    """
    Manages advanced periodization strategies.
    """
    
    @staticmethod
    def get_dup_parameters(
        day_type: DUPDay,
        base_sets: int,
        estimated_1rm: float
    ) -> Dict:
        """
        Get Daily Undulating Periodization parameters for a specific day type.
        
        DUP varies volume and intensity daily within the same week:
        - Day 1: High volume, lower intensity (hypertrophy focus)
        - Day 2: Moderate volume and intensity (balanced)
        - Day 3: Low volume, high intensity (strength focus)
        
        References:
        - Rhea et al. (2002): DUP produces greater strength gains than linear
        - Zourdos et al. (2016): DUP with autoregulation
        
        Args:
            day_type: Type of DUP day
            base_sets: Baseline number of sets
            estimated_1rm: Estimated 1RM for intensity calculation
            
        Returns:
            Dict with DUP parameters
        """
        config = DUP_TRAINING_DAYS[day_type]
        
        adjusted_sets = int(base_sets * config["sets_multiplier"])
        intensity_percent = config["intensity_percent"]
        target_weight = estimated_1rm * intensity_percent
        rep_min, rep_max = config["rep_range"]
        
        return {
            "sets": adjusted_sets,
            "rep_range_min": rep_min,
            "rep_range_max": rep_max,
            "intensity_percent": intensity_percent,
            "target_weight": round(target_weight / 2.5) * 2.5,  # Round to nearest 2.5kg
            "focus": config["focus"],
            "description": f"{day_type.replace('_', ' ').title()} day: {rep_min}-{rep_max} reps at {intensity_percent*100:.0f}% 1RM"
        }
    
    @staticmethod
    def determine_dup_day(
        workout_number: int,
        workouts_per_week: int = 3
    ) -> DUPDay:
        """
        Determine which DUP day type based on workout number in the week.
        
        For 3 workouts per week:
        - Workout 1: High Volume
        - Workout 2: Moderate
        - Workout 3: High Intensity
        
        For 4+ workouts per week, cycle through the pattern.
        
        Args:
            workout_number: Workout number in the week (1-indexed)
            workouts_per_week: Total workouts per week
            
        Returns:
            DUP day type
        """
        if workouts_per_week <= 3:
            pattern = [DUPDay.HIGH_VOLUME, DUPDay.MODERATE, DUPDay.HIGH_INTENSITY]
        else:
            # For more frequent training, cycle through pattern
            pattern = [
                DUPDay.HIGH_VOLUME,
                DUPDay.MODERATE,
                DUPDay.HIGH_INTENSITY,
                DUPDay.MODERATE
            ]
        
        # Use modulo to cycle through pattern
        index = (workout_number - 1) % len(pattern)
        return pattern[index]
    
    @staticmethod
    def get_block_parameters(
        current_phase: TrainingPhase,
        week_in_phase: int,
        base_volume: float,
        base_intensity: float
    ) -> Dict:
        """
        Get Block Periodization parameters for current training phase.
        
        Block periodization organizes training into sequential blocks:
        - Accumulation: High volume, lower intensity (3-4 weeks)
        - Intensification: Moderate volume, high intensity (2-3 weeks)
        - Realization: Low volume, peak intensity (1-2 weeks)
        
        References:
        - Issurin (2010): Block periodization for sports training
        - Kiely (2012): Periodization theory
        
        Args:
            current_phase: Current training phase
            week_in_phase: Week number within the current phase
            base_volume: Baseline volume
            base_intensity: Baseline intensity
            
        Returns:
            Dict with block periodization parameters
        """
        if current_phase == TrainingPhase.ACCUMULATION:
            phase_config = BLOCK_PERIODIZATION_CONFIG["accumulation"]
        elif current_phase == TrainingPhase.INTENSIFICATION:
            phase_config = BLOCK_PERIODIZATION_CONFIG["intensification"]
        else:  # REALIZATION
            phase_config = BLOCK_PERIODIZATION_CONFIG["realization"]
        
        volume_multiplier = phase_config["volume_multiplier"]
        intensity_multiplier = phase_config["intensity_multiplier"]
        
        # Apply wave loading within phase (undulation within block)
        wave_adjustment = PeriodizationService._calculate_wave_adjustment(
            week_in_phase,
            phase_config["duration_weeks"][1]  # Max duration
        )
        
        final_volume = base_volume * volume_multiplier * wave_adjustment["volume"]
        final_intensity = base_intensity * intensity_multiplier * wave_adjustment["intensity"]
        
        return {
            "volume_multiplier": round(volume_multiplier * wave_adjustment["volume"], 3),
            "intensity_multiplier": round(intensity_multiplier * wave_adjustment["intensity"], 3),
            "adjusted_volume": final_volume,
            "adjusted_intensity": final_intensity,
            "phase": current_phase,
            "week_in_phase": week_in_phase,
            "focus": phase_config["focus"],
            "deload_frequency": phase_config["deload_frequency"],
            "description": f"{current_phase.value.title()} Block - Week {week_in_phase}"
        }
    
    @staticmethod
    def _calculate_wave_adjustment(
        week_number: int,
        max_weeks: int
    ) -> Dict[str, float]:
        """
        Calculate wave loading adjustment within a block.
        
        Implements 2-steps-forward, 1-step-back wave loading:
        - Week 1: 100%
        - Week 2: 110%
        - Week 3: 105% (step back)
        - Week 4: 115%
        
        Args:
            week_number: Week number in the phase
            max_weeks: Maximum weeks in the phase
            
        Returns:
            Dict with volume and intensity adjustments
        """
        # Define wave pattern
        if week_number == 1:
            return {"volume": 1.0, "intensity": 1.0}
        elif week_number == 2:
            return {"volume": 1.10, "intensity": 1.05}
        elif week_number == 3:
            return {"volume": 1.05, "intensity": 1.03}  # Step back
        elif week_number >= 4:
            return {"volume": 1.15, "intensity": 1.08}
        
        return {"volume": 1.0, "intensity": 1.0}
    
    @staticmethod
    def should_transition_phase(
        current_phase: TrainingPhase,
        weeks_in_phase: int,
        performance_trend: Optional[float] = None
    ) -> Tuple[bool, Optional[TrainingPhase]]:
        """
        Determine if it's time to transition to the next training phase.
        
        Args:
            current_phase: Current training phase
            weeks_in_phase: Number of weeks in current phase
            performance_trend: Optional performance trend (positive = improving)
            
        Returns:
            Tuple of (should_transition, next_phase)
        """
        if current_phase == TrainingPhase.ACCUMULATION:
            config = BLOCK_PERIODIZATION_CONFIG["accumulation"]
            max_duration = config["duration_weeks"][1]
            
            # Transition after 3-4 weeks
            if weeks_in_phase >= max_duration:
                return True, TrainingPhase.INTENSIFICATION
            
            # Early transition if performance plateaus
            if performance_trend is not None and performance_trend < 0.02 and weeks_in_phase >= 3:
                return True, TrainingPhase.INTENSIFICATION
        
        elif current_phase == TrainingPhase.INTENSIFICATION:
            config = BLOCK_PERIODIZATION_CONFIG["intensification"]
            max_duration = config["duration_weeks"][1]
            
            # Transition after 2-3 weeks
            if weeks_in_phase >= max_duration:
                return True, TrainingPhase.REALIZATION
        
        elif current_phase == TrainingPhase.REALIZATION:
            config = BLOCK_PERIODIZATION_CONFIG["realization"]
            max_duration = config["duration_weeks"][1]
            
            # Cycle back to accumulation after 1-2 weeks
            if weeks_in_phase >= max_duration:
                return True, TrainingPhase.ACCUMULATION
        
        return False, None
    
    @staticmethod
    def calculate_optimal_periodization(
        training_type: TrainingType,
        experience: TrainingExperience,
        training_frequency: int
    ) -> PeriodizationModel:
        """
        Recommend optimal periodization model based on athlete characteristics.
        
        Args:
            training_type: Training goal
            experience: Training experience level
            training_frequency: Workouts per week
            
        Returns:
            Recommended periodization model
        """
        # DUP works well for intermediate/advanced with frequent training
        if experience in [TrainingExperience.INTERMEDIATE, TrainingExperience.ADVANCED]:
            if training_frequency >= 3:
                return PeriodizationModel.UNDULATING
        
        # Block periodization for advanced athletes or specific goals
        if experience == TrainingExperience.ADVANCED:
            if training_type == TrainingType.STRENGTH:
                return PeriodizationModel.BLOCK
        
        # Linear periodization for beginners or less frequent training
        return PeriodizationModel.LINEAR

