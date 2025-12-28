"""
Intensity Technique Recommendation Service

AI-powered recommendations for set types and rep styles.
ONLY recommends techniques when specific triggers are detected:
- Plateau detection (performance stalled)
- Struggling performance (high RPE, no progression)
- Volume ceiling (at MRV but needs more stimulus)
- Phase-based (late accumulation phase)

By default, returns STRAIGHT sets with NORMAL rep style.
"""
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.utils.constants import (
    SetType, RepStyle, TrainingType, TrainingPhase, TrainingExperience,
    ExerciseType, SET_TYPE_CONFIG, REP_STYLE_CONFIG, VALID_TECHNIQUE_COMBINATIONS,
    MRV_SETS_PER_WEEK, EFFECTIVE_SET_RIR_THRESHOLD,
    PLATEAU_IMPROVEMENT_THRESHOLD, STRUGGLING_DETECTION_RPE_THRESHOLD,
    MRV_CEILING_THRESHOLD, PARTIAL_EFFECTIVE_SET_WEIGHT
)

from app.models import ExerciseMuscle, MuscleGroupModel

class IntensityTechniqueService:
    """
    Service for recommending intensity techniques ONLY when needed.
    
    The AI defaults to straight sets with normal tempo and only
    recommends intensity techniques when specific triggers are detected.
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def recommend_techniques(
        self,
        athlete_id: int,
        exercise_id: int,
        training_type: TrainingType,
        training_phase: TrainingPhase,
        exercise_type: ExerciseType,
        experience: TrainingExperience,
        readiness_score: float,
        is_primary: bool,
        order_in_workout: int,
        performance_level: Optional[str] = None,
        week_number: Optional[int] = None,
        muscle_name: Optional[str] = None
    ) -> Dict[str, any]:
        """
        Recommend set type and rep style for an exercise.
        
        ONLY recommends non-standard techniques when triggers are detected:
        1. Plateau: Performance stalled for 2-3 sessions
        2. Struggling: High RPE (8+) with no progression
        3. Volume ceiling: At MRV but needs more stimulus
        4. Phase-based: Late accumulation phase (week 3-4)
        
        Returns:
            Dict with recommended set_type, rep_style, parameters, and trigger info
        """
        # Check all triggers
        triggers = self._detect_triggers(
            athlete_id=athlete_id,
            exercise_id=exercise_id,
            training_type=training_type,
            training_phase=training_phase,
            experience=experience,
            performance_level=performance_level,
            week_number=week_number,
            muscle_name=muscle_name
        )
        
        # If no triggers detected, return defaults
        if not triggers["any_triggered"]:
            return {
                "set_type": SetType.STRAIGHT,
                "rep_style": RepStyle.NORMAL,
                "set_type_params": {},
                "rep_style_params": {},
                "reasoning": "Standard straight sets - no intensity technique needed",
                "triggers": triggers
            }
        
        # Triggers detected - recommend appropriate technique
        set_type = self._select_set_type_for_triggers(
            triggers=triggers,
            training_type=training_type,
            training_phase=training_phase,
            exercise_type=exercise_type,
            experience=experience,
            readiness_score=readiness_score,
            is_primary=is_primary
        )
        
        rep_style = self._select_rep_style_for_triggers(
            triggers=triggers,
            set_type=set_type,
            training_type=training_type,
            training_phase=training_phase,
            exercise_type=exercise_type,
            experience=experience,
            readiness_score=readiness_score
        )
        
        # Validate combination
        if not self.validate_combination(set_type, rep_style):
            rep_style = RepStyle.NORMAL
        
        # Get parameters
        set_type_params = self.get_default_params(set_type)
        rep_style_params = self.get_default_params(rep_style, is_rep_style=True)
        
        return {
            "set_type": set_type,
            "rep_style": rep_style,
            "set_type_params": set_type_params,
            "rep_style_params": rep_style_params,
            "reasoning": self._generate_reasoning(set_type, rep_style, triggers),
            "triggers": triggers
        }
    
    def _detect_triggers(
        self,
        athlete_id: int,
        exercise_id: int,
        training_type: TrainingType,
        training_phase: TrainingPhase,
        experience: TrainingExperience,
        performance_level: Optional[str],
        week_number: Optional[int],
        muscle_name: Optional[str]
    ) -> Dict[str, any]:
        """
        Detect all triggers that would warrant an intensity technique.
        
        Returns:
            Dict with trigger status for each condition
        """
        triggers = {
            "plateau_detected": False,
            "struggling_detected": False,
            "volume_ceiling_detected": False,
            "phase_based_triggered": False,
            "any_triggered": False,
            "details": {}
        }
        
        # 1. Plateau detection: Check if performance has stalled
        plateau_info = self._check_plateau(athlete_id, exercise_id)
        if plateau_info["is_plateau"]:
            triggers["plateau_detected"] = True
            triggers["details"]["plateau"] = plateau_info
        
        # 2. Struggling detection: High RPE with no progression
        if performance_level in ["struggling", "failed"]:
            struggling_info = self._check_struggling(athlete_id, exercise_id)
            if struggling_info["is_struggling"]:
                triggers["struggling_detected"] = True
                triggers["details"]["struggling"] = struggling_info
        
        # 3. Volume ceiling: At MRV but hypertrophy-focused
        if training_type == TrainingType.HYPERTROPHY and muscle_name:
            volume_info = self._check_volume_ceiling(athlete_id, experience, muscle_name)
            if volume_info["at_ceiling"]:
                triggers["volume_ceiling_detected"] = True
                triggers["details"]["volume_ceiling"] = volume_info
    
        # 4. Phase-based: Late accumulation phase (week 3-4 of mesocycle)
        if training_phase == TrainingPhase.ACCUMULATION and week_number:
            if week_number >= 3 and (week_number % 4) != 0:  # Week 3-4, not deload
                triggers["phase_based_triggered"] = True
                triggers["details"]["phase"] = {
                    "week_number": week_number,
                    "reason": "Late accumulation phase - technique can maximize stimulus"
                }
        
        # Check if any trigger fired
        triggers["any_triggered"] = (
            triggers["plateau_detected"] or
            triggers["struggling_detected"] or
            triggers["volume_ceiling_detected"] or
            triggers["phase_based_triggered"]
        )
        
        return triggers
    
    def _check_plateau(self, athlete_id: int, exercise_id: int) -> Dict:
        """
        Check if performance on an exercise has plateaued.
        
        Plateau = no weight or rep increase for 2-3 consecutive sessions.
        """
        from app.models import ExerciseSet, WorkoutSession
        
        # Get last 4 sessions for this exercise
        recent_sets = (
            self.db.query(ExerciseSet)
            .join(WorkoutSession)
            .filter(
                WorkoutSession.athlete_id == athlete_id,
                ExerciseSet.exercise_id == exercise_id
            )
            .order_by(desc(WorkoutSession.session_date))
            .limit(20)  # Get enough sets to cover 3-4 sessions
            .all()
        )
        
        if len(recent_sets) < 6:  # Need at least 2 sessions worth of data
            return {"is_plateau": False, "sessions_analyzed": 0}
        
        # Group by session and get best set per session
        session_bests = {}
        for set_record in recent_sets:
            session_id = set_record.workout_session_id
            volume = set_record.weight * set_record.reps
            if session_id not in session_bests or volume > session_bests[session_id]["volume"]:
                session_bests[session_id] = {
                    "weight": set_record.weight,
                    "reps": set_record.reps,
                    "volume": volume
                }
        
        # Check if stalled (no improvement in last 2-3 sessions)
        sessions_sorted = list(session_bests.values())
        if len(sessions_sorted) < 3:
            return {"is_plateau": False, "sessions_analyzed": len(sessions_sorted)}
        
        # Compare recent sessions to previous
        recent_avg = sum(s["volume"] for s in sessions_sorted[:2]) / 2
        previous_avg = sum(s["volume"] for s in sessions_sorted[2:4]) / max(1, len(sessions_sorted[2:4]))
        
        # Plateau if no improvement (< 2% increase)
        improvement = (recent_avg - previous_avg) / previous_avg if previous_avg > 0 else 0
        is_plateau = improvement < PLATEAU_IMPROVEMENT_THRESHOLD
        
        return {
            "is_plateau": is_plateau,
            "sessions_analyzed": len(sessions_sorted),
            "recent_avg_volume": round(recent_avg, 1),
            "previous_avg_volume": round(previous_avg, 1),
            "improvement_percent": round(improvement * 100, 1)
        }
    
    def _check_struggling(self, athlete_id: int, exercise_id: int) -> Dict:
        """
        Check if athlete is struggling: high RPE with no progression.
        """
        from app.models import ExerciseSet, WorkoutSession
        
        # Get recent sets
        recent_sets = (
            self.db.query(ExerciseSet)
            .join(WorkoutSession)
            .filter(
                WorkoutSession.athlete_id == athlete_id,
                ExerciseSet.exercise_id == exercise_id,
                ExerciseSet.rpe.isnot(None)
            )
            .order_by(desc(WorkoutSession.session_date))
            .limit(10)
            .all()
        )
        
        if len(recent_sets) < 3:
            return {"is_struggling": False}
        
        # Check average RPE of recent sets
        recent_rpes = [s.rpe for s in recent_sets[:5] if s.rpe]
        avg_rpe = sum(recent_rpes) / len(recent_rpes) if recent_rpes else 0
        
        # Struggling = high RPE (8+) with no volume increase
        is_struggling = avg_rpe >= STRUGGLING_DETECTION_RPE_THRESHOLD
        
        return {
            "is_struggling": is_struggling,
            "avg_rpe": round(avg_rpe, 1),
            "sets_analyzed": len(recent_sets)
        }
    
    def _check_volume_ceiling(
        self,
        athlete_id: int,
        experience: TrainingExperience,
        muscle_name: str
    ) -> Dict:
        """
        Check if athlete is at MRV (Maximum Recoverable Volume) for a muscle group.
        """
        from app.models import ExerciseSet, WorkoutSession, Exercise
        
        # Get muscle from database
        muscle = self.db.query(MuscleGroupModel).filter(
            MuscleGroupModel.name == muscle_name
        ).first()
        
        if not muscle:
            return {"at_ceiling": False}
        
        # Get MRV for this experience level
        mrv = MRV_SETS_PER_WEEK.get(experience, 20)
        
        # Calculate weekly sets for this muscle group
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        
        # Get exercises targeting this muscle with significant activation
        exercise_links = (
            self.db.query(ExerciseMuscle.exercise_id)
            .filter(
                ExerciseMuscle.muscle_group_id == muscle.id,
                ExerciseMuscle.role == "prime_mover"  # Primary targets only
            )
            .all()
        )
        exercise_ids = [link[0] for link in exercise_links]
        
        if not exercise_ids:
            return {"at_ceiling": False}
        
        # Get all sets in last week and calculate effective sets
        sets = (
            self.db.query(ExerciseSet)
            .join(WorkoutSession)
            .filter(
                WorkoutSession.athlete_id == athlete_id,
                WorkoutSession.session_date >= week_ago,
                ExerciseSet.exercise_id.in_(exercise_ids)
            )
            .all()
        )
        
        # Calculate effective sets (only RIR 0-4 count toward MRV)
        weekly_sets = self._calculate_effective_sets_from_sets(sets)
        
        # At ceiling if >= 90% of MRV
        at_ceiling = weekly_sets >= (mrv * MRV_CEILING_THRESHOLD)
        
        return {
            "at_ceiling": at_ceiling,
            "weekly_sets": round(weekly_sets, 1),
            "mrv": mrv,
            "percentage_of_mrv": round((weekly_sets / mrv) * 100, 1) if mrv > 0 else 0,
            "note": "Volume calculated using effective sets (RIR 0-4 count fully, RIR 5-6 count 50%, RIR 7+ count 0%)"
        }
    
    def _select_set_type_for_triggers(
        self,
        triggers: Dict,
        training_type: TrainingType,
        training_phase: TrainingPhase,
        exercise_type: ExerciseType,
        experience: TrainingExperience,
        readiness_score: float,
        is_primary: bool
    ) -> SetType:
        """
        Select the best set type based on which triggers fired.
        """
        # Filter valid set types for this context
        valid_types = self._get_valid_set_types(
            training_type=training_type,
            training_phase=training_phase,
            exercise_type=exercise_type,
            experience=experience,
            readiness_score=readiness_score
        )
        
        # Prioritize based on triggers
        
        # Plateau or struggling: Need to break through
        if triggers["plateau_detected"] or triggers["struggling_detected"]:
            # For isolation: drop sets or myo-reps
            if exercise_type == ExerciseType.ISOLATION:
                if SetType.DROP_SET in valid_types:
                    return SetType.DROP_SET
                if SetType.MYO_REPS in valid_types:
                    return SetType.MYO_REPS
            # For compound: rest-pause or cluster sets
            else:
                if training_type == TrainingType.STRENGTH and SetType.CLUSTER_SET in valid_types:
                    return SetType.CLUSTER_SET
                if SetType.REST_PAUSE in valid_types:
                    return SetType.REST_PAUSE
        
        # Volume ceiling: Need more stimulus without more sets
        if triggers["volume_ceiling_detected"]:
            if exercise_type == ExerciseType.ISOLATION:
                if SetType.MYO_REPS in valid_types:
                    return SetType.MYO_REPS
                if SetType.DROP_SET in valid_types:
                    return SetType.DROP_SET
            else:
                if SetType.REST_PAUSE in valid_types:
                    return SetType.REST_PAUSE
        
        # Phase-based: Late accumulation
        if triggers["phase_based_triggered"]:
            if exercise_type == ExerciseType.ISOLATION:
                if SetType.MYO_REPS in valid_types:
                    return SetType.MYO_REPS
            if SetType.REST_PAUSE in valid_types:
                return SetType.REST_PAUSE
        
        # Fallback to first valid non-straight type, or straight
        for st in valid_types:
            if st != SetType.STRAIGHT:
                return st
        
        return SetType.STRAIGHT
    
    def _select_rep_style_for_triggers(
        self,
        triggers: Dict,
        set_type: SetType,
        training_type: TrainingType,
        training_phase: TrainingPhase,
        exercise_type: ExerciseType,
        experience: TrainingExperience,
        readiness_score: float
    ) -> RepStyle:
        """
        Select the best rep style based on triggers and context.
        
        Rep styles are generally less impactful than set types,
        so we're more conservative here.
        """
        # Get valid combinations for this set type
        valid_styles = VALID_TECHNIQUE_COMBINATIONS.get(set_type, [RepStyle.NORMAL])
        
        # Filter by experience and readiness
        filtered_styles = []
        for style in valid_styles:
            config = REP_STYLE_CONFIG.get(style, {})
            
            # Check experience
            exp_levels = [TrainingExperience.BEGINNER, TrainingExperience.INTERMEDIATE, TrainingExperience.ADVANCED]
            min_exp = config.get("min_experience", TrainingExperience.BEGINNER)
            if exp_levels.index(experience) < exp_levels.index(min_exp):
                continue
            
            # Check readiness for high-fatigue styles
            if readiness_score < 0.6 and config.get("fatigue_multiplier", 1.0) > 1.2:
                continue
            
            # Check applicable training types
            if training_type not in config.get("applicable_training_types", [training_type]):
                continue
            
            filtered_styles.append(style)
        
        if not filtered_styles:
            return RepStyle.NORMAL
        
        # For plateau/struggling: consider tempo techniques
        if triggers["plateau_detected"] or triggers["struggling_detected"]:
            if exercise_type == ExerciseType.ISOLATION and RepStyle.LENGTHENED_PARTIALS in filtered_styles:
                return RepStyle.LENGTHENED_PARTIALS
            if RepStyle.TEMPO_ECCENTRIC in filtered_styles:
                return RepStyle.TEMPO_ECCENTRIC
        
        # Default to normal for most cases
        return RepStyle.NORMAL
    
    def _get_valid_set_types(
        self,
        training_type: TrainingType,
        training_phase: TrainingPhase,
        exercise_type: ExerciseType,
        experience: TrainingExperience,
        readiness_score: float
    ) -> List[SetType]:
        """Get list of valid set types for the given context."""
        valid = [SetType.STRAIGHT]  # Always include straight
        
        exp_levels = [TrainingExperience.BEGINNER, TrainingExperience.INTERMEDIATE, TrainingExperience.ADVANCED]
        
        for set_type in SetType:
            if set_type == SetType.STRAIGHT:
                continue
            
            config = SET_TYPE_CONFIG.get(set_type, {})
            
            # Check training type
            if training_type not in config.get("applicable_training_types", []):
                continue
            
            # Check exercise type
            if exercise_type not in config.get("applicable_exercise_types", []):
                continue
            
            # Check experience
            min_exp = config.get("min_experience", TrainingExperience.BEGINNER)
            if exp_levels.index(experience) < exp_levels.index(min_exp):
                continue
            
            # Check phase
            if training_phase not in config.get("applicable_phases", []):
                continue
            
            # Check readiness
            if readiness_score < 0.6 and config.get("fatigue_multiplier", 1.0) > 1.2:
                continue
            
            valid.append(set_type)
        
        return valid
    
    def validate_combination(self, set_type: SetType, rep_style: RepStyle) -> bool:
        """Validate that a set type and rep style combination is safe."""
        valid_styles = VALID_TECHNIQUE_COMBINATIONS.get(set_type, [RepStyle.NORMAL])
        return rep_style in valid_styles
    
    def get_default_params(self, technique: SetType | RepStyle, is_rep_style: bool = False) -> Dict:
        """Get default parameters for a technique."""
        if is_rep_style:
            config = REP_STYLE_CONFIG.get(technique, {})
        else:
            config = SET_TYPE_CONFIG.get(technique, {})
        
        return config.get("default_params", {}).copy()
    
    def calculate_fatigue_impact(
        self,
        set_type: SetType,
        rep_style: RepStyle,
        base_volume: float
    ) -> Dict[str, float]:
        """Calculate fatigue and volume impact of technique combination."""
        set_config = SET_TYPE_CONFIG.get(set_type, {})
        rep_config = REP_STYLE_CONFIG.get(rep_style, {})
        
        volume_mult = set_config.get("volume_multiplier", 1.0) * rep_config.get("volume_multiplier", 1.0)
        fatigue_mult = set_config.get("fatigue_multiplier", 1.0) * rep_config.get("fatigue_multiplier", 1.0)
        
        return {
            "volume_multiplier": volume_mult,
            "fatigue_multiplier": fatigue_mult,
            "adjusted_volume": base_volume * volume_mult
        }
    
    def _generate_reasoning(
        self,
        set_type: SetType,
        rep_style: RepStyle,
        triggers: Dict
    ) -> str:
        """Generate human-readable reasoning for technique selection."""
        reasons = []
        
        # Explain which triggers fired
        if triggers["plateau_detected"]:
            reasons.append("Plateau detected - adding intensity technique to break through")
        if triggers["struggling_detected"]:
            reasons.append("High effort with stalled progress - technique to maximize stimulus")
        if triggers["volume_ceiling_detected"]:
            reasons.append("At volume ceiling - technique to increase stimulus without more sets")
        if triggers["phase_based_triggered"]:
            reasons.append("Late accumulation phase - optimal time for intensity technique")
        
        # Explain the technique
        if set_type != SetType.STRAIGHT:
            reasons.append(f"{set_type.value.replace('_', ' ').title()} recommended")
        if rep_style != RepStyle.NORMAL:
            reasons.append(f"with {rep_style.value.replace('_', ' ').title()} rep style")
        
        return " | ".join(reasons) if reasons else "Standard straight sets"
    
    def _calculate_effective_sets_from_sets(self, sets: List) -> float:
        """
        Calculate effective sets from completed workout sets.
        
        Only sets close to failure (RIR 0-4) count toward MEV/MRV landmarks.
        References: Schoenfeld et al. (2017) - Volume landmarks research
        
        Args:
            sets: List of ExerciseSet records from completed workouts
            
        Returns:
            Effective sets count (float)
        """
        if not sets:
            return 0.0
        
        effective_count = 0.0
        
        for set_record in sets:
            rir = set_record.rir
            
            # If no RIR recorded, assume effective (user may not have recorded it)
            if rir is None:
                effective_count += 1.0
            # RIR 0-4: Fully effective (close to failure)
            elif rir <= EFFECTIVE_SET_RIR_THRESHOLD:
                effective_count += 1.0
            # RIR 5-6: Partially effective (warm-up territory, minimal hypertrophy stimulus)
            elif rir <= 6:
                effective_count += PARTIAL_EFFECTIVE_SET_WEIGHT
            # RIR 7+: Not effective for hypertrophy (too far from failure)
            else:
                effective_count += 0.0
        
        return effective_count
