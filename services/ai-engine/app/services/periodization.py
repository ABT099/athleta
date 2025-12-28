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
    PeriodizationModel, DUP_TRAINING_DAYS, BLOCK_PERIODIZATION_CONFIG,
    WAVE_WEEK_1_VOLUME_MULT, WAVE_WEEK_1_INTENSITY_MULT,
    WAVE_WEEK_2_VOLUME_MULT, WAVE_WEEK_2_INTENSITY_MULT,
    WAVE_WEEK_3_VOLUME_MULT, WAVE_WEEK_3_INTENSITY_MULT,
    WAVE_WEEK_4_PLUS_VOLUME_MULT, WAVE_WEEK_4_PLUS_INTENSITY_MULT
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
            return {"volume": WAVE_WEEK_1_VOLUME_MULT, "intensity": WAVE_WEEK_1_INTENSITY_MULT}
        elif week_number == 2:
            return {"volume": WAVE_WEEK_2_VOLUME_MULT, "intensity": WAVE_WEEK_2_INTENSITY_MULT}
        elif week_number == 3:
            return {"volume": WAVE_WEEK_3_VOLUME_MULT, "intensity": WAVE_WEEK_3_INTENSITY_MULT}  # Step back
        elif week_number >= 4:
            return {"volume": WAVE_WEEK_4_PLUS_VOLUME_MULT, "intensity": WAVE_WEEK_4_PLUS_INTENSITY_MULT}
        
        return {"volume": WAVE_WEEK_1_VOLUME_MULT, "intensity": WAVE_WEEK_1_INTENSITY_MULT}
    
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
    def should_adjust_periodization_on_plateau(
        current_phase: TrainingPhase,
        weeks_in_phase: int,
        plateau_count: int,
        periodization_model: PeriodizationModel
    ) -> Tuple[bool, Optional[Dict]]:
        """
        Determine if periodization should be adjusted due to plateaus.
        
        Args:
            current_phase: Current training phase
            weeks_in_phase: Weeks in current phase
            plateau_count: Number of plateaus detected in recent sessions
            periodization_model: Current periodization model
            
        Returns:
            Tuple of (should_adjust, adjustment_dict)
        """
        adjustment = None
        
        # If multiple plateaus, consider switching periodization model
        if plateau_count >= 2 and periodization_model == PeriodizationModel.LINEAR:
            # Switch to undulating (DUP) for more variation
            adjustment = {
                "action": "switch_periodization",
                "from": PeriodizationModel.LINEAR.value,
                "to": PeriodizationModel.UNDULATING.value,
                "reason": "Multiple plateaus detected - switching to undulating periodization for more variation"
            }
            return True, adjustment
        
        # Early phase transition if plateau in current phase
        if plateau_count >= 1 and weeks_in_phase >= 2:
            if current_phase == TrainingPhase.ACCUMULATION:
                adjustment = {
                    "action": "early_phase_transition",
                    "from": TrainingPhase.ACCUMULATION.value,
                    "to": TrainingPhase.INTENSIFICATION.value,
                    "reason": "Plateau detected - transitioning early to intensification phase"
                }
                return True, adjustment
            
            elif current_phase == TrainingPhase.INTENSIFICATION:
                adjustment = {
                    "action": "early_phase_transition",
                    "from": TrainingPhase.INTENSIFICATION.value,
                    "to": TrainingPhase.REALIZATION.value,
                    "reason": "Plateau detected - transitioning early to realization phase"
                }
                return True, adjustment
        
        return False, None
    
    @staticmethod
    def recommend_plan_duration(
        training_type: TrainingType,
        experience: TrainingExperience,
        periodization_model: PeriodizationModel,
        frequency: int
    ) -> Tuple[int, int]:
        """
        Recommend workout plan duration range in weeks based on athlete characteristics.
        
        Scientific rationale:
        - Beginners: 8-12 weeks (allows adaptation, skill development, habit formation)
        - Intermediate: 10-16 weeks (longer mesocycles for complex periodization)
        - Advanced: 12-20 weeks (supports block periodization and peaking phases)
        
        Duration is adjusted based on:
        - Training type (strength needs longer cycles)
        - Periodization model (block needs longer cycles)
        - Training frequency (more frequent = can handle longer cycles)
        
        References:
        - Schoenfeld et al. (2017): Volume landmarks and mesocycle length
        - Issurin (2010): Block periodization duration
        - Kiely (2012): Periodization theory
        
        Args:
            training_type: Training goal (hypertrophy, strength, hybrid)
            experience: Training experience level
            periodization_model: Recommended periodization model
            frequency: Workouts per week
            
        Returns:
            Tuple of (min_weeks, max_weeks)
        """
        # Base duration ranges by experience level
        base_ranges = {
            TrainingExperience.BEGINNER: (8, 12),
            TrainingExperience.INTERMEDIATE: (10, 16),
            TrainingExperience.ADVANCED: (12, 20)
        }
        min_weeks, max_weeks = base_ranges[experience]
        
        # Adjust for training type
        if training_type == TrainingType.STRENGTH:
            min_weeks += 2  # Strength needs longer cycles for intensity progression
            max_weeks += 4
        elif training_type == TrainingType.HYBRID:
            min_weeks += 1
            max_weeks += 2
        # Hypertrophy stays at base range
        
        # Adjust for periodization model
        if periodization_model == PeriodizationModel.BLOCK:
            # Block periodization needs at least 12 weeks (2 full blocks)
            min_weeks = max(min_weeks, 12)
            max_weeks = max(max_weeks, 20)
        elif periodization_model == PeriodizationModel.UNDULATING:
            # DUP can handle longer cycles due to weekly variation
            min_weeks = max(min_weeks, 10)
            max_weeks = max(max_weeks, 16)
        # Linear stays at base range
        
        # Adjust for frequency (more frequent = can handle longer cycles)
        if frequency >= 4:
            max_weeks += 2
        
        return (min_weeks, max_weeks)
    
    @staticmethod
    def calculate_optimal_periodization(
        training_type: TrainingType,
        experience: TrainingExperience,
        training_frequency: int,
        training_age_years: Optional[int] = None
    ) -> PeriodizationModel:
        """
        Recommend optimal periodization model based on athlete characteristics.
        
        Enhanced with training age consideration:
        - Advanced athletes with 10+ training years → prefer Block periodization for strength
        - Intermediate with 5+ years → can handle Undulating periodization better
        
        Args:
            training_type: Training goal
            experience: Training experience level
            training_frequency: Workouts per week
            training_age_years: Optional years of consistent training (if None, uses experience estimate)
            
        Returns:
            Recommended periodization model
        """
        # Use training age if provided, otherwise estimate from experience
        # Training age estimates from RecoveryAnalyzer:
        # BEGINNER: 0 (0-1 years)
        # INTERMEDIATE: 2 (2-4 years)
        # ADVANCED: 5 (5+ years)
        if training_age_years is None:
            from app.services.recovery_analyzer import RecoveryAnalyzer
            training_age_years = RecoveryAnalyzer.estimate_training_age_from_experience(experience)
        
        # Block periodization for advanced athletes with extensive training age
        if experience == TrainingExperience.ADVANCED:
            if training_type == TrainingType.STRENGTH:
                # Advanced strength athletes (estimated 5+ years, but explicit >= 10 years preferred)
                # If explicit training_age_years >= 10, strongly prefer block
                # Otherwise, still prefer block for advanced strength (estimated 5+ years)
                if training_age_years >= 10:
                    return PeriodizationModel.BLOCK
                return PeriodizationModel.BLOCK  # Still prefer block for advanced strength
        
        # DUP works well for intermediate/advanced with frequent training
        if experience in [TrainingExperience.INTERMEDIATE, TrainingExperience.ADVANCED]:
            if training_frequency >= 3:
                # Intermediate with explicit training age >= 5 years (beyond the 2-4 estimate range)
                # can better handle undulating periodization
                # Note: Using estimate gives 2 years, so >= 5 only applies when explicitly provided
                if experience == TrainingExperience.INTERMEDIATE and training_age_years >= 5:
                    return PeriodizationModel.UNDULATING
                elif experience == TrainingExperience.ADVANCED:
                    # Advanced athletes (estimated 5+ years) can use undulating if not strength-focused
                    if training_type != TrainingType.STRENGTH:
                        return PeriodizationModel.UNDULATING
        
        # Linear periodization for beginners or less frequent training
        return PeriodizationModel.LINEAR

