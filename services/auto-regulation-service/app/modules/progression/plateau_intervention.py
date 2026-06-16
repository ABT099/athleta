"""
Plateau Detection and Intervention Service.

Automatically detects plateaus and recommends interventions:
- Exercise substitution
- Volume cycling (overreach/deload)
- Periodization adjustments
"""
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models import ExerciseProgressionTracking  # algo-owned, local per-exercise history
from app.modules.analysis import AnalysisContext
from app.clients.exercise_client import ExerciseClient
from app.utils.constants import (
    TrainingExperience, TrainingType, TrainingPhase
)


class PlateauType:
    """Plateau classification types."""
    NEUROMUSCULAR = "neuromuscular"  # Strength stalled, technique breakdown
    METABOLIC = "metabolic"  # Rep progression stalled
    PSYCHOLOGICAL = "psychological"  # Motivation drop, RPE perception shift


class PlateauInterventionService:
    """
    Detects plateaus and recommends interventions.
    
    Integrates automatically into workout completion flow.
    """
    
    def __init__(self, db: Session):
        self.db = db

    def _get_exercise(self, exercise_id: int):
        """Fetch a single exercise from exercise-service, or None if unknown."""
        with ExerciseClient() as client:
            exercises = client.get_exercises([exercise_id])
        return exercises[0] if exercises else None

    def detect_and_intervene(
        self,
        ctx: AnalysisContext,
        performance_analysis: Dict
    ) -> Dict:
        """
        Detect plateaus for the exercises in the completed session (from the
        context) and recommend interventions. Plateau detection reads the local
        per-exercise progression history.
        """
        athlete_id = ctx.athlete_id
        interventions = []
        exercise_substitutions = {}
        volume_cycle_phase = None
        periodization_adjustment = None

        # Exercises from the completed session
        exercise_ids = ctx.exercise_ids

        # Check each exercise for plateau
        for exercise_id in exercise_ids:
            plateau_info = self._detect_plateau(athlete_id, exercise_id)
            
            if plateau_info.get("is_plateau"):
                # Classify plateau type
                plateau_type = self._classify_plateau_type(
                    athlete_id, exercise_id, plateau_info
                )
                
                # Get intervention based on type
                intervention = self._get_intervention(
                    athlete_id, exercise_id, plateau_type, plateau_info
                )
                
                if intervention:
                    intervention_dict = {
                        "exercise_id": exercise_id,
                        "exercise_name": intervention.get("exercise_name"),
                        "plateau_type": plateau_type,
                        "intervention_type": intervention.get("type"),
                        "recommendation": intervention.get("recommendation"),
                        "details": intervention.get("details", {})
                    }
                    # Include substitute exercise name if available
                    if intervention.get("substitute_exercise_name"):
                        intervention_dict["substitute_exercise_name"] = intervention.get("substitute_exercise_name")
                    interventions.append(intervention_dict)
                    
                    # Collect exercise substitutions
                    if intervention.get("type") == "exercise_substitution":
                        exercise_substitutions[exercise_id] = intervention.get("substitute_exercise_id")
                    
                    # Check for volume cycling recommendation
                    if intervention.get("type") == "volume_cycling":
                        volume_cycle_phase = intervention.get("cycle_phase")
                    
                    # Check for periodization adjustment
                    if intervention.get("type") == "periodization_adjustment":
                        periodization_adjustment = intervention.get("adjustment")
        
        return {
            "plateaus_detected": len(interventions),
            "interventions": interventions,
            "exercise_substitutions": exercise_substitutions,
            "volume_cycle_phase": volume_cycle_phase,
            "periodization_adjustment": periodization_adjustment
        }
    
    def _detect_plateau(self, athlete_id: int, exercise_id: int) -> Dict:
        """
        Detect if an exercise has plateaued, from the local per-exercise progression
        history (ExerciseProgressionTracking carries per-session volume_load + RPE).
        """
        rows = (
            self.db.query(ExerciseProgressionTracking)
            .filter(
                ExerciseProgressionTracking.athlete_id == athlete_id,
                ExerciseProgressionTracking.exercise_id == exercise_id,
            )
            .order_by(desc(ExerciseProgressionTracking.session_date))
            .limit(5)
            .all()
        )

        sessions_analyzed = [
            {
                "date": r.session_date,
                "volume": r.volume_load,
                "avg_rpe": r.average_rpe,
            }
            for r in rows
        ]

        if len(sessions_analyzed) < 3:
            return {"is_plateau": False, "sessions_analyzed": len(sessions_analyzed)}
        
        # Check for plateau indicators
        recent_sessions = sessions_analyzed[:2]
        previous_sessions = sessions_analyzed[2:4]
        
        # Volume plateau
        recent_avg_volume = sum(s["volume"] for s in recent_sessions) / len(recent_sessions)
        previous_avg_volume = sum(s["volume"] for s in previous_sessions) / len(previous_sessions) if previous_sessions else recent_avg_volume
        
        volume_improvement = (recent_avg_volume - previous_avg_volume) / previous_avg_volume if previous_avg_volume > 0 else 0
        
        # RPE trend (increasing RPE with same/lower volume = struggling)
        recent_avg_rpe = sum(s["avg_rpe"] for s in recent_sessions if s["avg_rpe"]) / len([s for s in recent_sessions if s["avg_rpe"]]) if any(s["avg_rpe"] for s in recent_sessions) else None
        previous_avg_rpe = sum(s["avg_rpe"] for s in previous_sessions if s["avg_rpe"]) / len([s for s in previous_sessions if s["avg_rpe"]]) if previous_sessions and any(s["avg_rpe"] for s in previous_sessions) else None
        
        rpe_increasing = False
        if recent_avg_rpe and previous_avg_rpe:
            rpe_increasing = recent_avg_rpe > previous_avg_rpe + 0.5  # Significant RPE increase
        
        # Plateau if:
        # 1. Volume improvement < 2%
        # 2. OR RPE increasing with same/lower volume (struggling)
        is_plateau = volume_improvement < 0.02 or (rpe_increasing and volume_improvement <= 0.05)
        
        return {
            "is_plateau": is_plateau,
            "sessions_analyzed": len(sessions_analyzed),
            "recent_avg_volume": round(recent_avg_volume, 1),
            "previous_avg_volume": round(previous_avg_volume, 1),
            "volume_improvement": round(volume_improvement * 100, 1),
            "recent_avg_rpe": round(recent_avg_rpe, 1) if recent_avg_rpe else None,
            "previous_avg_rpe": round(previous_avg_rpe, 1) if previous_avg_rpe else None,
            "rpe_increasing": rpe_increasing
        }
    
    def _classify_plateau_type(
        self,
        athlete_id: int,
        exercise_id: int,
        plateau_info: Dict
    ) -> str:
        """
        Classify plateau type based on performance patterns.
        """
        # Get exercise to check type
        exercise = self._get_exercise(exercise_id)
        if not exercise:
            return PlateauType.METABOLIC  # Default
        
        # Neuromuscular: Strength-focused exercise, weight stalled, high RPE
        is_strength_exercise = (
            exercise.exercise_type == "compound" and
            exercise.intensity_category in ["compound_heavy", "compound_moderate"]
        )
        
        if is_strength_exercise and plateau_info.get("rpe_increasing"):
            return PlateauType.NEUROMUSCULAR
        
        # Metabolic: Rep progression stalled, volume not increasing
        if plateau_info.get("volume_improvement", 0) < 0.02:
            return PlateauType.METABOLIC
        
        # Psychological: RPE perception shift, motivation drop indicators
        if plateau_info.get("rpe_increasing") and not is_strength_exercise:
            return PlateauType.PSYCHOLOGICAL
        
        # Default to metabolic
        return PlateauType.METABOLIC
    
    def _get_intervention(
        self,
        athlete_id: int,
        exercise_id: int,
        plateau_type: str,
        plateau_info: Dict
    ) -> Optional[Dict]:
        """
        Get intervention recommendation based on plateau type.
        """
        exercise = self._get_exercise(exercise_id)
        if not exercise:
            return None
        
        if plateau_type == PlateauType.NEUROMUSCULAR:
            # Exercise variation or deload
            from app.modules.injury import ExerciseSubstitutor
            substitutor = ExerciseSubstitutor()
            substitute = substitutor.find_substitute(exercise_id, variation_type="equipment_or_angle")
            
            if substitute:
                return {
                    "type": "exercise_substitution",
                    "exercise_name": exercise.name,
                    "substitute_exercise_id": substitute["exercise_id"],
                    "substitute_exercise_name": substitute["name"],
                    "recommendation": f"Substitute {exercise.name} with {substitute['name']} to provide novel stimulus",
                    "details": {
                        "reason": "Neuromuscular plateau - exercise variation needed",
                        "substitution_type": substitute.get("substitution_type")
                    }
                }
            else:
                # Fallback to deload recommendation
                return {
                    "type": "deload",
                    "exercise_name": exercise.name,
                    "recommendation": f"Deload {exercise.name} - reduce intensity by 10-15% for 1 week",
                    "details": {"reason": "Neuromuscular plateau - deload needed"}
                }
        
        elif plateau_type == PlateauType.METABOLIC:
            # Volume cycling (overreach)
            return {
                "type": "volume_cycling",
                "exercise_name": exercise.name,
                "cycle_phase": "overreach",
                "recommendation": f"Increase volume for {exercise.name} by 15-20% for 1-2 weeks, then deload",
                "details": {
                    "reason": "Metabolic plateau - volume cycling to force adaptation",
                    "volume_increase": 0.15
                }
            }
        
        elif plateau_type == PlateauType.PSYCHOLOGICAL:
            # Exercise substitution for novelty
            from app.modules.injury import ExerciseSubstitutor
            substitutor = ExerciseSubstitutor()
            substitute = substitutor.find_substitute(exercise_id, variation_type="novel_stimulus")
            
            if substitute:
                return {
                    "type": "exercise_substitution",
                    "exercise_name": exercise.name,
                    "substitute_exercise_id": substitute["exercise_id"],
                    "substitute_exercise_name": substitute["name"],
                    "recommendation": f"Substitute {exercise.name} with {substitute['name']} for psychological refresh",
                    "details": {
                        "reason": "Psychological plateau - novel stimulus needed",
                        "substitution_type": substitute.get("substitution_type")
                    }
                }
            else:
                # Fallback to rep range change
                return {
                    "type": "rep_range_change",
                    "exercise_name": exercise.name,
                    "recommendation": f"Change rep range for {exercise.name} - try 8-12 if currently 5-8, or vice versa",
                    "details": {"reason": "Psychological plateau - rep range variation"}
                }
        
        return None

