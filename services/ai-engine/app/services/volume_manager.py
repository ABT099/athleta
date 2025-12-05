"""
Volume Landmarks Management System.

Tracks volume per muscle group and provides MEV/MAV/MRV-based recommendations.
Based on Renaissance Periodization volume landmarks research.
"""
from typing import Dict, List, Optional, Tuple, Set
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from app.models import (
    Athlete, WorkoutSession, ExerciseSet, Exercise, WorkoutDayExercise
)
from app.utils.constants import (
    TrainingExperience, MuscleGroup, MuscleSize, MUSCLE_SIZE_MAP,
    MEV_SETS_PER_WEEK, MRV_SETS_PER_WEEK, FocusArea, FOCUS_AREA_TO_MUSCLE_GROUPS,
    EFFECTIVE_SET_RIR_THRESHOLD
)
from app.services.training_calculations import TrainingCalculations


class VolumeManager:
    """
    Manages volume landmarks (MEV/MAV/MRV) and provides volume recommendations.
    
    MEV (Minimum Effective Volume): Lowest volume that produces adaptation
    MAV (Maximum Adaptive Volume): Volume that maximizes gains without excessive fatigue
    MRV (Maximum Recoverable Volume): Volume threshold beyond which recovery fails
    
    References:
    - Israetel et al.: Volume landmarks for hypertrophy
    - Schoenfeld et al. (2017): Dose-response relationship between volume and hypertrophy
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.calc = TrainingCalculations()
    
    def get_volume_landmarks(
        self,
        experience: TrainingExperience,
        muscle_group: MuscleGroup
    ) -> Dict[str, int]:
        """
        Get MEV, MAV, and MRV for a muscle group based on experience.
        
        Args:
            experience: Training experience level
            muscle_group: Muscle group to get landmarks for
            
        Returns:
            Dict with 'mev', 'mav', 'mrv' in sets per week
        """
        # Get base MEV/MRV from experience
        base_mev = MEV_SETS_PER_WEEK[experience]
        base_mrv = MRV_SETS_PER_WEEK[experience]
        
        # Adjust for muscle size
        muscle_size = MUSCLE_SIZE_MAP.get(muscle_group, MuscleSize.MEDIUM)
        size_multiplier = {
            MuscleSize.SMALL: 0.8,
            MuscleSize.MEDIUM: 0.9,
            MuscleSize.LARGE: 1.0,
        }
        
        mev = int(base_mev * size_multiplier[muscle_size])
        mrv = int(base_mrv * size_multiplier[muscle_size])
        mav = int((mev + mrv) / 2)  # Maximum Adaptive Volume (midpoint)
        
        return {
            "mev": mev,
            "mav": mav,
            "mrv": mrv,
        }

    def get_volume_target_for_muscle(
        self,
        experience: TrainingExperience,
        muscle_group: MuscleGroup,
        focus_areas: Optional[List[str]] = None
    ) -> Dict[str, int | str]:
        """
        Determine the weekly set target for a muscle group based on focus areas.

        - Focus muscles: aim for MAV (upper adaptive range) without exceeding MRV.
        - Maintenance muscles: hold MEV to preserve adaptations with minimal fatigue.
        """
        landmarks = self.get_volume_landmarks(experience, muscle_group)
        prioritized_muscles = self._expand_focus_areas(focus_areas or [])

        is_focus = muscle_group in prioritized_muscles
        if is_focus:
            target_sets = min(landmarks["mav"], landmarks["mrv"])
            upper_bound = landmarks["mrv"]
            focus_state = "focus"
        else:
            target_sets = landmarks["mev"]
            upper_bound = landmarks["mav"]
            focus_state = "maintenance"

        return {
            "muscle_group": muscle_group.value,
            "target_sets": target_sets,
            "upper_bound": upper_bound,
            "focus_state": focus_state,
            "mev": landmarks["mev"],
            "mav": landmarks["mav"],
            "mrv": landmarks["mrv"],
        }

    @staticmethod
    def _expand_focus_areas(focus_areas: List[str]) -> Set[MuscleGroup]:
        """Convert simplified focus areas into the underlying muscle groups."""
        prioritized = set()
        for area in focus_areas:
            try:
                focus_area_enum = FocusArea(area)
            except ValueError:
                continue
            for muscle in FOCUS_AREA_TO_MUSCLE_GROUPS.get(focus_area_enum, []):
                prioritized.add(muscle)
        return prioritized
    
    def calculate_current_volume(
        self,
        athlete_id: int,
        muscle_group: MuscleGroup,
        days_lookback: int = 7
    ) -> Dict:
        """
        Calculate current weekly volume for a muscle group.
        
        Args:
            athlete_id: Athlete ID
            muscle_group: Muscle group to analyze
            days_lookback: Days to look back (default 7 for weekly volume)
            
        Returns:
            Dict with volume metrics
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_lookback)
        
        # Get recent workout sessions
        sessions = (
            self.db.query(WorkoutSession)
            .filter(
                WorkoutSession.athlete_id == athlete_id,
                WorkoutSession.session_date >= cutoff_date
            )
            .order_by(WorkoutSession.session_date.desc())
            .all()
        )
        
        total_sets = 0
        total_volume_load = 0.0
        exercises_tracked = set()
        
        # For each session, find exercises targeting this muscle group
        for session in sessions:
            # Get exercise sets for this session
            sets = (
                self.db.query(ExerciseSet)
                .filter(ExerciseSet.workout_session_id == session.id)
                .all()
            )
            
            # Group sets by exercise
            exercise_sets = {}
            for set_record in sets:
                ex_id = set_record.exercise_id
                if ex_id not in exercise_sets:
                    exercise_sets[ex_id] = []
                exercise_sets[ex_id].append(set_record)
            
            # Check each exercise for muscle group targeting
            for ex_id, sets_list in exercise_sets.items():
                exercise = self.db.query(Exercise).filter(Exercise.id == ex_id).first()
                if not exercise:
                    continue
                
                # Check if exercise targets this muscle group
                targets_muscle = (
                    muscle_group.value in (exercise.primary_muscles or []) or
                    muscle_group.value in (exercise.secondary_muscles or [])
                )
                
                if targets_muscle:
                    exercises_tracked.add(ex_id)
                    # Calculate effective sets (only RIR 0-4 count toward MEV/MRV)
                    effective_sets = self._calculate_effective_sets_from_sets(sets_list)
                    total_sets += effective_sets
                    # Calculate volume load (weight × reps) only for effective sets
                    # Weight by effectiveness: RIR 0-4 = 100%, RIR 5-6 = 50%, RIR 7+ = 0%
                    for set_record in sets_list:
                        effectiveness = self._get_set_effectiveness(set_record.rir)
                        total_volume_load += set_record.weight * set_record.reps * effectiveness
        
        return {
            "muscle_group": muscle_group.value,
            "total_sets": round(total_sets, 1),
            "total_volume_load": round(total_volume_load, 1),
            "exercises_count": len(exercises_tracked),
            "days_analyzed": days_lookback,
            "note": "Volume calculated using effective sets (RIR 0-4 count fully, RIR 5-6 count 50%, RIR 7+ count 0%). Volume load is weighted by set effectiveness for consistency."
        }
    
    def _calculate_effective_sets_from_sets(self, sets_list: List[ExerciseSet]) -> float:
        """
        Calculate effective sets from completed workout sets.
        
        Only sets close to failure (RIR 0-4) count toward MEV/MRV landmarks.
        References: Schoenfeld et al. (2017) - Volume landmarks research
        
        Args:
            sets_list: List of ExerciseSet records from completed workouts
            
        Returns:
            Effective sets count (float)
        """
        if not sets_list:
            return 0.0
        
        effective_count = 0.0
        
        for set_record in sets_list:
            rir = set_record.rir
            
            # If no RIR recorded, assume effective (user may not have recorded it)
            if rir is None:
                effective_count += 1.0
            # RIR 0-4: Fully effective (close to failure)
            elif rir <= EFFECTIVE_SET_RIR_THRESHOLD:
                effective_count += 1.0
            # RIR 5-6: Partially effective (warm-up territory, minimal hypertrophy stimulus)
            elif rir <= 6:
                effective_count += 0.5
            # RIR 7+: Not effective for hypertrophy (too far from failure)
            else:
                effective_count += 0.0
        
        return effective_count
    
    def _get_set_effectiveness(self, rir: Optional[int]) -> float:
        """
        Get effectiveness multiplier for a single set based on RIR.
        
        Args:
            rir: Reps in reserve (None, 0-10+)
            
        Returns:
            Effectiveness multiplier (0.0 to 1.0)
        """
        if rir is None:
            return 1.0  # Assume effective if not recorded
        elif rir <= EFFECTIVE_SET_RIR_THRESHOLD:
            return 1.0  # Fully effective
        elif rir <= 6:
            return 0.5  # Partially effective
        else:
            return 0.0  # Not effective
    
    def get_volume_position(
        self,
        athlete_id: int,
        muscle_group: MuscleGroup,
        experience: TrainingExperience,
        days_lookback: int = 7
    ) -> Dict:
        """
        Get current volume position relative to MEV/MAV/MRV landmarks.
        
        Args:
            athlete_id: Athlete ID
            muscle_group: Muscle group to analyze
            experience: Training experience level
            days_lookback: Days to look back
            
        Returns:
            Dict with volume position and recommendations
        """
        # Get landmarks
        landmarks = self.get_volume_landmarks(experience, muscle_group)
        mev = landmarks["mev"]
        mav = landmarks["mav"]
        mrv = landmarks["mrv"]
        
        # Get current volume
        current = self.calculate_current_volume(athlete_id, muscle_group, days_lookback)
        current_sets = current["total_sets"]
        
        # Determine position
        if current_sets < mev:
            position = "below_mev"
            recommendation = "increase_volume"
            priority = "high"
            message = f"Volume below MEV ({current_sets} < {mev} sets). Increase volume to stimulate adaptation."
        elif current_sets < mav:
            position = "mev_to_mav"
            recommendation = "maintain_or_increase"
            priority = "medium"
            message = f"Volume in effective range ({current_sets} sets, MEV={mev}, MAV={mav}). Can maintain or gradually increase."
        elif current_sets < mrv:
            position = "mav_to_mrv"
            recommendation = "maintain"
            priority = "low"
            message = f"Volume in optimal range ({current_sets} sets, MAV={mav}, MRV={mrv}). Maintain current volume."
        else:
            position = "above_mrv"
            recommendation = "reduce_volume"
            priority = "high"
            message = f"Volume exceeds MRV ({current_sets} > {mrv} sets). Reduce volume to prevent overreaching."
        
        # Calculate percentage of range
        if current_sets < mev:
            percentage = (current_sets / mev) * 50 if mev > 0 else 0  # 0-50% range
        elif current_sets < mrv:
            # 50-100% range (between MEV and MRV)
            percentage = 50 + ((current_sets - mev) / (mrv - mev)) * 50 if (mrv - mev) > 0 else 50
        else:
            percentage = 100 + ((current_sets - mrv) / mrv) * 50 if mrv > 0 else 100  # >100% if above MRV
        
        return {
            "muscle_group": muscle_group.value,
            "current_sets": current_sets,
            "mev": mev,
            "mav": mav,
            "mrv": mrv,
            "position": position,
            "percentage_of_range": round(percentage, 1),
            "recommendation": recommendation,
            "priority": priority,
            "message": message,
            "volume_load": current["total_volume_load"],
        }
    
    def get_volume_adjustment_recommendation(
        self,
        athlete_id: int,
        muscle_group: MuscleGroup,
        experience: TrainingExperience,
        current_volume_multiplier: float = 1.0
    ) -> Dict:
        """
        Get volume adjustment recommendation based on current position.
        
        Args:
            athlete_id: Athlete ID
            muscle_group: Muscle group to analyze
            experience: Training experience level
            current_volume_multiplier: Current volume multiplier being applied
            
        Returns:
            Dict with recommended volume adjustment
        """
        volume_position = self.get_volume_position(athlete_id, muscle_group, experience)
        
        position = volume_position["position"]
        current_sets = volume_position["current_sets"]
        mev = volume_position["mev"]
        mrv = volume_position["mrv"]
        
        # Calculate recommended adjustment
        if position == "below_mev":
            # Need to increase volume
            sets_needed = mev - current_sets
            # Increase by enough to reach at least MEV
            adjustment = max(1.1, (mev / current_sets) if current_sets > 0 else 1.2)
            adjustment = min(adjustment, 1.3)  # Cap at 30% increase
        elif position == "mev_to_mav":
            # Can maintain or slightly increase
            adjustment = 1.0  # Maintain
        elif position == "mav_to_mrv":
            # Maintain current volume
            adjustment = 1.0
        else:  # above_mrv
            # Need to reduce volume
            # Reduce to below MRV
            adjustment = (mrv / current_sets) if current_sets > 0 else 0.8
            adjustment = max(adjustment, 0.7)  # Don't reduce more than 30%
        
        # Apply to current multiplier
        recommended_multiplier = current_volume_multiplier * adjustment
        
        return {
            "muscle_group": muscle_group.value,
            "current_volume_multiplier": current_volume_multiplier,
            "recommended_multiplier": round(recommended_multiplier, 3),
            "adjustment": round(adjustment, 3),
            "reason": volume_position["message"],
            "priority": volume_position["priority"],
        }
    
    def get_all_muscle_volume_status(
        self,
        athlete_id: int,
        experience: TrainingExperience,
        days_lookback: int = 7
    ) -> Dict:
        """
        Get volume status for all major muscle groups.
        
        Args:
            athlete_id: Athlete ID
            experience: Training experience level
            days_lookback: Days to look back
            
        Returns:
            Dict with volume status for each muscle group
        """
        muscle_groups = [
            MuscleGroup.CHEST, MuscleGroup.BACK, MuscleGroup.SHOULDERS,
            MuscleGroup.BICEPS, MuscleGroup.TRICEPS, MuscleGroup.QUADRICEPS,
            MuscleGroup.HAMSTRINGS, MuscleGroup.GLUTES, MuscleGroup.CALVES
        ]
        
        status = {}
        for muscle_group in muscle_groups:
            status[muscle_group.value] = self.get_volume_position(
                athlete_id, muscle_group, experience, days_lookback
            )
        
        # Summary statistics
        below_mev_count = sum(1 for s in status.values() if s["position"] == "below_mev")
        above_mrv_count = sum(1 for s in status.values() if s["position"] == "above_mrv")
        optimal_count = sum(1 for s in status.values() if s["position"] in ["mev_to_mav", "mav_to_mrv"])
        
        return {
            "muscle_groups": status,
            "summary": {
                "below_mev_count": below_mev_count,
                "above_mrv_count": above_mrv_count,
                "optimal_count": optimal_count,
                "total_muscle_groups": len(muscle_groups),
            },
            "overall_recommendation": self._get_overall_recommendation(
                below_mev_count, above_mrv_count, optimal_count
            ),
        }
    
    @staticmethod
    def _get_overall_recommendation(
        below_mev: int,
        above_mrv: int,
        optimal: int
    ) -> str:
        """Get overall volume recommendation."""
        if above_mrv > 0:
            return "Reduce volume for overreaching muscle groups"
        elif below_mev > optimal:
            return "Increase volume for under-stimulated muscle groups"
        else:
            return "Volume distribution is balanced"

