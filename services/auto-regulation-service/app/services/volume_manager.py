"""
Volume Landmarks Management System.

Tracks volume per muscle group and provides MEV/MAV/MRV-based recommendations.
Based on Renaissance Periodization volume landmarks research.
"""
from typing import Dict, List, Optional, Tuple, Set
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from autoregulation.models import (
    Athlete, WorkoutSession, ExerciseSet, Exercise, WorkoutDayExercise,
    MuscleGroupModel, ExerciseMuscle
)
from autoregulation.utils.constants import (
    TrainingExperience, MuscleSize,
    MEV_SETS_PER_WEEK, MRV_SETS_PER_WEEK, FocusArea,
    EFFECTIVE_SET_RIR_THRESHOLD,
    VOLUME_PERCENTAGE_BELOW_MEV_SCALE, VOLUME_PERCENTAGE_MEV_TO_MRV_BASE,
    VOLUME_PERCENTAGE_MEV_TO_MRV_SCALE, VOLUME_PERCENTAGE_ABOVE_MRV_BASE,
    VOLUME_PERCENTAGE_ABOVE_MRV_SCALE
)
from autoregulation.services.training_calculations import TrainingCalculations


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
        muscle_name: str
    ) -> Dict[str, int]:
        """
        Get MEV, MAV, and MRV for a muscle group based on experience.
        
        Args:
            experience: Training experience level
            muscle_name: Muscle group name to get landmarks for
            
        Returns:
            Dict with 'mev', 'mav', 'mrv' in sets per week
        """
        # Get muscle from database
        muscle = self.db.query(MuscleGroupModel).filter(
            MuscleGroupModel.name == muscle_name
        ).first()
        
        if not muscle:
            # Fallback to default values if muscle not found
            return {"mev": 10, "mav": 15, "mrv": 20}
        
        # Get base MEV/MRV from experience
        base_mev = MEV_SETS_PER_WEEK[experience]
        base_mrv = MRV_SETS_PER_WEEK[experience]
        
        # Adjust for muscle size
        size_multiplier = {
            "small": 0.8,
            "medium": 0.9,
            "large": 1.0,
        }
        
        multiplier = size_multiplier.get(muscle.size, 0.9)
        mev = int(base_mev * multiplier)
        mrv = int(base_mrv * multiplier)
        mav = int((mev + mrv) / 2)  # Maximum Adaptive Volume (midpoint)
        
        return {
            "mev": mev,
            "mav": mav,
            "mrv": mrv,
        }

    def get_volume_target_for_muscle(
        self,
        experience: TrainingExperience,
        muscle_name: str,
        focus_areas: Optional[List[str]] = None
    ) -> Dict[str, int | str]:
        """
        Determine the weekly set target for a muscle group based on focus areas.

        - Focus muscles: aim for MAV (upper adaptive range) without exceeding MRV.
        - Maintenance muscles: hold MEV to preserve adaptations with minimal fatigue.
        """
        landmarks = self.get_volume_landmarks(experience, muscle_name)
        prioritized_muscles = self._expand_focus_areas(focus_areas or [])

        is_focus = muscle_name in prioritized_muscles
        if is_focus:
            target_sets = min(landmarks["mav"], landmarks["mrv"])
            upper_bound = landmarks["mrv"]
            focus_state = "focus"
        else:
            target_sets = landmarks["mev"]
            upper_bound = landmarks["mav"]
            focus_state = "maintenance"

        return {
            "muscle_group": muscle_name,
            "target_sets": target_sets,
            "upper_bound": upper_bound,
            "focus_state": focus_state,
            "mev": landmarks["mev"],
            "mav": landmarks["mav"],
            "mrv": landmarks["mrv"],
        }

    @staticmethod
    def _expand_focus_areas(focus_areas: List[str]) -> Set[str]:
        """Convert simplified focus areas into the underlying muscle group names."""
        # Map focus areas to muscle names
        focus_to_muscles = {
            "chest": {"upper_chest", "mid_chest", "lower_chest"},
            "back": {"lats", "upper_traps", "mid_back", "lower_traps"},
            "shoulders": {"anterior_delt", "lateral_delt", "posterior_delt"},
            "arms": {"biceps", "triceps", "forearms"},
            "legs": {"quadriceps", "hamstrings", "glutes", "hip_flexors", "calves"},
            "core": {"abs", "erector_spinae"},
        }
        
        prioritized = set()
        for area in focus_areas:
            # Lowercase the area for consistent matching with database muscle names
            area_lower = area.lower()
            
            # Try as focus area first (expands to granular muscle names)
            try:
                focus_area_enum = FocusArea(area_lower)
                muscles = focus_to_muscles.get(focus_area_enum.value, set())
                prioritized.update(muscles)
            except (ValueError, KeyError):
                # Not a valid focus area - might be a direct muscle name
                # Only add if it's a direct muscle name (not a focus area)
                prioritized.add(area_lower)
        
        return prioritized
    
    def calculate_current_volume(
        self,
        athlete_id: int,
        muscle_name: str,
        days_lookback: int = 7
    ) -> Dict:
        """
        Calculate current weekly volume for a muscle group.
        
        Args:
            athlete_id: Athlete ID
            muscle_name: Muscle group name to analyze
            days_lookback: Days to look back (default 7 for weekly volume)
            
        Returns:
            Dict with volume metrics
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_lookback)
        
        # Get muscle from database
        muscle = self.db.query(MuscleGroupModel).filter(
            MuscleGroupModel.name == muscle_name
        ).first()
        
        if not muscle:
            return {
                "muscle_group": muscle_name,
                "total_sets": 0.0,
                "total_volume_load": 0.0,
                "exercises_count": 0,
                "days_analyzed": days_lookback,
                "note": "Muscle group not found"
            }
        
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
        
        total_sets = 0.0
        total_volume_load = 0.0
        exercises_tracked = set()
        
        # Load all sets for all sessions in one query to avoid N+1
        session_ids = [s.id for s in sessions]
        all_sets = (
            self.db.query(ExerciseSet)
            .filter(ExerciseSet.workout_session_id.in_(session_ids))
            .all()
        )
        
        # Group sets by session_id
        sets_by_session = {}
        for set_record in all_sets:
            session_id = set_record.workout_session_id
            if session_id not in sets_by_session:
                sets_by_session[session_id] = []
            sets_by_session[session_id].append(set_record)
        
        # Collect all exercise IDs
        all_exercise_ids = set()
        for sets_list in sets_by_session.values():
            for set_record in sets_list:
                all_exercise_ids.add(set_record.exercise_id)
        
        # Load all ExerciseMuscle links in one query to avoid N+1
        muscle_links = (
            self.db.query(ExerciseMuscle)
            .filter(
                ExerciseMuscle.exercise_id.in_(all_exercise_ids),
                ExerciseMuscle.muscle_group_id == muscle.id
            )
            .all()
        )
        muscle_link_map = {link.exercise_id: link for link in muscle_links}
        
        # Process sessions using pre-loaded data
        for session in sessions:
            sets = sets_by_session.get(session.id, [])
            
            # Group sets by exercise
            exercise_sets = {}
            for set_record in sets:
                ex_id = set_record.exercise_id
                if ex_id not in exercise_sets:
                    exercise_sets[ex_id] = []
                exercise_sets[ex_id].append(set_record)
            
            # Check each exercise for muscle group targeting
            for ex_id, sets_list in exercise_sets.items():
                # Use pre-loaded muscle link map instead of querying
                muscle_link = muscle_link_map.get(ex_id)
                
                if muscle_link:
                    exercises_tracked.add(ex_id)
                    
                    # Weight sets by role (convert role to activation weight)
                    from autoregulation.utils.constants import MUSCLE_ROLE_WEIGHTS
                    activation_weight = MUSCLE_ROLE_WEIGHTS.get(muscle_link.role, MUSCLE_ROLE_WEIGHTS["stabilizer"])
                    
                    # Calculate effective sets (only RIR 0-4 count toward MEV/MRV)
                    effective_sets = self._calculate_effective_sets_from_sets(sets_list)
                    total_sets += effective_sets * activation_weight
                    
                    # Calculate volume load (weight × reps) weighted by activation
                    for set_record in sets_list:
                        effectiveness = self._get_set_effectiveness(set_record.rir)
                        total_volume_load += (
                            set_record.weight * set_record.reps * 
                            effectiveness * activation_weight
                        )
        
        return {
            "muscle_group": muscle_name,
            "total_sets": round(total_sets, 1),
            "total_volume_load": round(total_volume_load, 1),
            "exercises_count": len(exercises_tracked),
            "days_analyzed": days_lookback,
            "note": "Volume weighted by muscle activation % (RIR 0-4 count fully, RIR 5-6 count 50%, RIR 7+ count 0%). Volume load weighted by set effectiveness and activation."
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
    
    def calculate_overreach_volume(
        self,
        experience: TrainingExperience,
        muscle_name: str,
        current_volume: float,
        focus_areas: Optional[List[str]] = None
    ) -> Dict[str, float]:
        """
        Calculate overreach volume for volume cycling intervention.
        
        Overreach = 110-120% of MRV to force adaptation.
        Used for breaking metabolic plateaus.
        
        Args:
            experience: Training experience
            muscle_name: Muscle group name
            current_volume: Current weekly volume (effective sets)
            focus_areas: Optional focus areas
            
        Returns:
            Dict with overreach volume and duration
        """
        landmarks = self.get_volume_landmarks(experience, muscle_name)
        mrv = landmarks["mrv"]
        
        # Overreach is 110-120% of MRV
        overreach_volume = mrv * 1.15  # 115% of MRV
        
        # Duration: 1-2 weeks depending on experience
        duration_weeks = 2 if experience == TrainingExperience.ADVANCED else 1
        
        return {
            "overreach_volume": round(overreach_volume, 1),
            "current_volume": round(current_volume, 1),
            "volume_increase": round((overreach_volume - current_volume) / current_volume * 100, 1) if current_volume > 0 else 0,
            "duration_weeks": duration_weeks,
            "mrv": mrv,
            "note": "Overreach volume for breaking metabolic plateaus. Follow with deload week."
        }
    
    def get_volume_cycle_phase(
        self,
        athlete_id: int,
        muscle_name: str,
        lookback_weeks: int = 4
    ) -> Optional[str]:
        """
        Determine current volume cycle phase (overreach, deload, normal).
        
        Args:
            athlete_id: Athlete ID
            muscle_name: Muscle group name to check
            lookback_weeks: Weeks to look back
            
        Returns:
            "overreach", "deload", or None (normal)
        """
        # Get current volume
        current_volume = self.calculate_current_volume(
            athlete_id, muscle_name, days_lookback=lookback_weeks * 7
        )
        
        # Get athlete experience
        athlete = self.db.query(Athlete).filter(Athlete.id == athlete_id).first()
        if not athlete:
            return None
        
        landmarks = self.get_volume_landmarks(athlete.training_experience, muscle_name)
        mrv = landmarks["mrv"]
        mev = landmarks["mev"]
        
        total_sets = current_volume.get("total_sets", 0)
        
        # Overreach: >110% of MRV
        if total_sets > mrv * 1.1:
            return "overreach"
        
        # Deload: <MEV (intentional reduction)
        if total_sets < mev * 0.9:
            return "deload"
        
        # Normal: MEV to MRV range
        return None
    
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
        muscle_name: str,
        experience: TrainingExperience,
        days_lookback: int = 7
    ) -> Dict:
        """
        Get current volume position relative to MEV/MAV/MRV landmarks.
        
        Args:
            athlete_id: Athlete ID
            muscle_name: Muscle group name to analyze
            experience: Training experience level
            days_lookback: Days to look back
            
        Returns:
            Dict with volume position and recommendations
        """
        # Get landmarks
        landmarks = self.get_volume_landmarks(experience, muscle_name)
        mev = landmarks["mev"]
        mav = landmarks["mav"]
        mrv = landmarks["mrv"]
        
        # Get current volume
        current = self.calculate_current_volume(athlete_id, muscle_name, days_lookback)
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
            percentage = (current_sets / mev) * VOLUME_PERCENTAGE_BELOW_MEV_SCALE if mev > 0 else 0  # 0-50% range
        elif current_sets < mrv:
            # 50-100% range (between MEV and MRV)
            percentage = VOLUME_PERCENTAGE_MEV_TO_MRV_BASE + ((current_sets - mev) / (mrv - mev)) * VOLUME_PERCENTAGE_MEV_TO_MRV_SCALE if (mrv - mev) > 0 else VOLUME_PERCENTAGE_MEV_TO_MRV_BASE
        else:
            percentage = VOLUME_PERCENTAGE_ABOVE_MRV_BASE + ((current_sets - mrv) / mrv) * VOLUME_PERCENTAGE_ABOVE_MRV_SCALE if mrv > 0 else VOLUME_PERCENTAGE_ABOVE_MRV_BASE  # >100% if above MRV
        
        return {
            "muscle_group": muscle_name,
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
        muscle_name: str,
        experience: TrainingExperience,
        current_volume_multiplier: float = 1.0
    ) -> Dict:
        """
        Get volume adjustment recommendation based on current position.
        
        Args:
            athlete_id: Athlete ID
            muscle_name: Muscle group name to analyze
            experience: Training experience level
            current_volume_multiplier: Current volume multiplier being applied
            
        Returns:
            Dict with recommended volume adjustment
        """
        volume_position = self.get_volume_position(athlete_id, muscle_name, experience)
        
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
            "muscle_group": muscle_name,
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
        # Query all muscle groups from database
        all_muscles = self.db.query(MuscleGroupModel).all()
        muscle_names = [m.name for m in all_muscles]
        
        # Focus on major muscles for summary
        major_muscle_names = [
            "mid_chest", "lats", "anterior_delt", "biceps", "triceps",
            "quadriceps", "hamstrings", "glutes", "calves"
        ]
        
        status = {}
        for muscle_name in major_muscle_names:
            if muscle_name in muscle_names:
                status[muscle_name] = self.get_volume_position(
                    athlete_id, muscle_name, experience, days_lookback
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
                "total_muscle_groups": len(status),
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
