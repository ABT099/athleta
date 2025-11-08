"""
Scientific training calculations and formulas.

Based on exercise physiology research and NSCA guidelines.
"""
import numpy as np
from typing import List, Tuple, Dict
from app.utils.constants import TrainingExperience, TrainingType, MuscleSize


class TrainingCalculations:
    """
    Scientific calculations for training progression.
    """
    
    @staticmethod
    def estimate_1rm_epley(weight: float, reps: int) -> float:
        """
        Estimate 1RM using Epley formula.
        
        Formula: 1RM = weight × (1 + reps/30)
        
        Reference: Epley, B. (1985). Poundage Chart. Boyd Epley Workout.
        
        Args:
            weight: Weight lifted (kg)
            reps: Number of reps performed
            
        Returns:
            Estimated 1RM in kg
        """
        if reps == 1:
            return weight
        return weight * (1 + reps / 30)
    
    @staticmethod
    def estimate_1rm_brzycki(weight: float, reps: int) -> float:
        """
        Estimate 1RM using Brzycki formula.
        
        Formula: 1RM = weight × (36 / (37 - reps))
        
        Reference: Brzycki, M. (1993). Strength Testing.
        
        Args:
            weight: Weight lifted (kg)
            reps: Number of reps performed
            
        Returns:
            Estimated 1RM in kg
        """
        if reps == 1:
            return weight
        if reps >= 37:
            # Formula breaks down at high reps
            return weight * 2.5
        return weight * (36 / (37 - reps))
    
    @staticmethod
    def estimate_1rm_average(weight: float, reps: int) -> float:
        """
        Average of Epley and Brzycki formulas for better accuracy.
        
        Args:
            weight: Weight lifted (kg)
            reps: Number of reps performed
            
        Returns:
            Estimated 1RM in kg
        """
        if reps == 1:
            return weight
        if reps > 12:
            # Use only Epley for high reps as Brzycki becomes less accurate
            return TrainingCalculations.estimate_1rm_epley(weight, reps)
        
        epley = TrainingCalculations.estimate_1rm_epley(weight, reps)
        brzycki = TrainingCalculations.estimate_1rm_brzycki(weight, reps)
        return (epley + brzycki) / 2
    
    @staticmethod
    def calculate_relative_intensity(weight: float, estimated_1rm: float) -> float:
        """
        Calculate relative intensity as percentage of 1RM.
        
        Args:
            weight: Weight lifted (kg)
            estimated_1rm: Estimated 1RM (kg)
            
        Returns:
            Relative intensity (0.0 - 1.0)
        """
        if estimated_1rm == 0:
            return 0.0
        return min(weight / estimated_1rm, 1.0)
    
    @staticmethod
    def calculate_volume_load(sets: List[Tuple[float, int]]) -> float:
        """
        Calculate total volume load.
        
        Formula: Volume Load = Σ(weight × reps) for all sets
        
        Args:
            sets: List of (weight, reps) tuples
            
        Returns:
            Total volume load in kg
        """
        return sum(weight * reps for weight, reps in sets)
    
    @staticmethod
    def calculate_intensity_load(sets: List[Tuple[float, int, float]]) -> float:
        """
        Calculate intensity load (volume × relative intensity).
        
        Formula: Intensity Load = Σ(weight × reps × relative_intensity)
        
        Args:
            sets: List of (weight, reps, relative_intensity) tuples
            
        Returns:
            Total intensity load
        """
        return sum(weight * reps * rel_int for weight, reps, rel_int in sets)
    
    @staticmethod
    def rpe_to_rir(rpe: float) -> int:
        """
        Convert RPE to RIR using Zourdos scale.
        
        Reference: Zourdos et al. (2016). Novel Resistance Training-Specific RPE Scale.
        
        Args:
            rpe: Rate of Perceived Exertion (6-10 scale)
            
        Returns:
            Reps in Reserve (0-5+)
        """
        rpe_to_rir_map = {
            10.0: 0,
            9.5: 0,
            9.0: 1,
            8.5: 1,
            8.0: 2,
            7.5: 2,
            7.0: 3,
            6.5: 3,
            6.0: 4,
            5.5: 4,
            5.0: 5,
        }
        
        # Round to nearest 0.5
        rpe_rounded = round(rpe * 2) / 2
        return rpe_to_rir_map.get(rpe_rounded, 5)
    
    @staticmethod
    def rir_to_rpe(rir: int) -> float:
        """
        Convert RIR to RPE.
        
        Args:
            rir: Reps in Reserve
            
        Returns:
            Estimated RPE (6-10 scale)
        """
        rir_to_rpe_map = {
            0: 10.0,
            1: 9.0,
            2: 8.0,
            3: 7.0,
            4: 6.0,
            5: 5.0,
        }
        return rir_to_rpe_map.get(rir, 5.0)
    
    @staticmethod
    def estimate_velocity_from_rpe(rpe: float, reps: int) -> str:
        """
        Estimate bar velocity category from RPE and reps.
        
        Args:
            rpe: Rate of Perceived Exertion
            reps: Number of reps performed
            
        Returns:
            Velocity category: "fast", "moderate", "slow", "grind"
        """
        rir = TrainingCalculations.rpe_to_rir(rpe)
        
        if rir >= 4:
            return "fast"
        elif rir >= 2:
            return "moderate"
        elif rir >= 1:
            return "slow"
        else:
            return "grind"
    
    @staticmethod
    def calculate_fitness_fatigue(
        training_loads: List[float],
        days: List[int],
        fitness_tau: float = 42.0,
        fatigue_tau: float = 7.0,
        k_fitness: float = 1.0,
        k_fatigue: float = 2.0
    ) -> Tuple[float, float, float]:
        """
        Simplified fitness-fatigue model (Banister model).
        
        Performance = Fitness - Fatigue
        
        Reference: Banister, E.W. (1991). Modeling elite athletic performance.
        
        Args:
            training_loads: List of training loads (e.g., volume or intensity)
            days: Days ago each training session occurred
            fitness_tau: Fitness decay time constant (days)
            fatigue_tau: Fatigue decay time constant (days)
            k_fitness: Fitness gain coefficient
            k_fatigue: Fatigue gain coefficient
            
        Returns:
            Tuple of (fitness, fatigue, performance)
        """
        fitness = 0.0
        fatigue = 0.0
        
        for load, day_ago in zip(training_loads, days):
            # Fitness accumulates slowly, decays slowly
            fitness += k_fitness * load * np.exp(-day_ago / fitness_tau)
            
            # Fatigue accumulates quickly, decays quickly
            fatigue += k_fatigue * load * np.exp(-day_ago / fatigue_tau)
        
        performance = fitness - fatigue
        
        return fitness, fatigue, performance
    
    @staticmethod
    def calculate_acute_chronic_workload_ratio(
        recent_loads: List[float],
        chronic_loads: List[float]
    ) -> float:
        """
        Calculate ACWR for injury risk assessment.
        
        ACWR = Acute Load (1 week) / Chronic Load (4 weeks average)
        
        Safe zone: 0.8 - 1.3
        Elevated risk: < 0.8 or > 1.5
        
        Reference: Gabbett, T.J. (2016). The training-injury prevention paradox.
        
        Args:
            recent_loads: Training loads from last 7 days
            chronic_loads: Training loads from last 28 days
            
        Returns:
            ACWR ratio
        """
        acute_load = np.mean(recent_loads) if recent_loads else 0.0
        chronic_load = np.mean(chronic_loads) if chronic_loads else 1.0
        
        if chronic_load == 0:
            return 0.0
        
        return acute_load / chronic_load
    
    @staticmethod
    def calculate_training_monotony(daily_loads: List[float]) -> float:
        """
        Calculate training monotony index.
        
        Monotony = Mean Daily Load / Standard Deviation
        High monotony (>2.0) increases injury risk.
        
        Reference: Foster, C. (1998). Monitoring training in athletes.
        
        Args:
            daily_loads: Training loads for each day in the period
            
        Returns:
            Monotony index
        """
        if len(daily_loads) < 2:
            return 1.0
        
        mean_load = np.mean(daily_loads)
        std_load = np.std(daily_loads)
        
        if std_load == 0:
            # Perfect monotony - return a high value (infinite in theory)
            return 10.0  # High monotony value
        
        return mean_load / std_load
    
    @staticmethod
    def calculate_training_strain(
        daily_loads: List[float],
        monotony: float
    ) -> float:
        """
        Calculate training strain.
        
        Strain = Total Weekly Load × Monotony
        
        Args:
            daily_loads: Training loads for the week
            monotony: Monotony index
            
        Returns:
            Training strain
        """
        total_load = sum(daily_loads)
        return total_load * monotony
    
    @staticmethod
    def get_mev_mrv_for_experience(
        experience: TrainingExperience,
        muscle_size: MuscleSize
    ) -> Dict[str, int]:
        """
        Get Minimum Effective Volume and Maximum Recoverable Volume.
        
        Based on Renaissance Periodization volume landmarks.
        
        Args:
            experience: Training experience level
            muscle_size: Muscle group size
            
        Returns:
            Dict with MEV, MAV, MRV in sets per week
        """
        # Base values by experience
        base_mev = {
            TrainingExperience.BEGINNER: 8,
            TrainingExperience.INTERMEDIATE: 10,
            TrainingExperience.ADVANCED: 12,
        }
        
        base_mrv = {
            TrainingExperience.BEGINNER: 15,
            TrainingExperience.INTERMEDIATE: 20,
            TrainingExperience.ADVANCED: 25,
        }
        
        # Adjust for muscle size
        size_multiplier = {
            MuscleSize.SMALL: 0.8,
            MuscleSize.MEDIUM: 0.9,
            MuscleSize.LARGE: 1.0,
        }
        
        mev = int(base_mev[experience] * size_multiplier[muscle_size])
        mrv = int(base_mrv[experience] * size_multiplier[muscle_size])
        mav = int((mev + mrv) / 2)  # Maximum Adaptive Volume (midpoint)
        
        return {
            "mev": mev,  # Minimum Effective Volume
            "mav": mav,  # Maximum Adaptive Volume
            "mrv": mrv,  # Maximum Recoverable Volume
        }
    
    @staticmethod
    def calculate_optimal_load_increase(
        current_rpe: float,
        target_rpe: float,
        current_weight: float,
        experience: TrainingExperience,
        training_type: TrainingType
    ) -> float:
        """
        Calculate optimal load increase based on RPE feedback.
        
        Args:
            current_rpe: Actual RPE from last session
            target_rpe: Target RPE for the training
            current_weight: Current weight used (kg)
            experience: Training experience level
            training_type: Type of training goal
            
        Returns:
            Recommended weight for next session (kg)
        """
        # Base progression rates by experience
        progression_rates = {
            TrainingExperience.BEGINNER: 0.05,  # 5%
            TrainingExperience.INTERMEDIATE: 0.025,  # 2.5%
            TrainingExperience.ADVANCED: 0.01,  # 1%
        }
        
        # Adjust based on training type
        type_modifiers = {
            TrainingType.STRENGTH: 1.2,  # Faster progression on strength
            TrainingType.HYPERTROPHY: 1.0,
            TrainingType.HYBRID: 1.1,
        }
        
        base_rate = progression_rates[experience] * type_modifiers[training_type]
        
        # Adjust based on RPE difference
        rpe_diff = target_rpe - current_rpe
        
        if rpe_diff > 1.5:
            # Too easy - increase significantly
            increase = current_weight * (base_rate * 2)
        elif rpe_diff > 0.5:
            # Slightly too easy - normal increase
            increase = current_weight * base_rate
        elif abs(rpe_diff) <= 0.5:
            # Perfect - maintain or small increase
            increase = current_weight * (base_rate * 0.5)
        elif rpe_diff < -1.5:
            # Too hard - decrease significantly
            increase = current_weight * (-base_rate * 1.5)
        else:  # -1.5 <= rpe_diff < -0.5
            # Slightly too hard - decrease slightly
            increase = current_weight * (-base_rate * 0.75)
        
        new_weight = current_weight + increase
        
        # Round to nearest 2.5kg for practical loading
        return round(new_weight / 2.5) * 2.5
    
    @staticmethod
    def calculate_deload_parameters(
        normal_volume: float,
        normal_intensity: float,
        deload_week: int
    ) -> Dict[str, float]:
        """
        Calculate deload parameters.
        
        Deload reduces volume by 40-50% and intensity by 10-20%.
        
        Args:
            normal_volume: Normal training volume
            normal_intensity: Normal relative intensity
            deload_week: Week number of deload
            
        Returns:
            Dict with deload_volume and deload_intensity multipliers
        """
        # Standard deload: 50% volume, 90% intensity
        return {
            "volume_multiplier": 0.5,
            "intensity_multiplier": 0.9,
            "target_rpe": 6.0,  # Very conservative
        }


