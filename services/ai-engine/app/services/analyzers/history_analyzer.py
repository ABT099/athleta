"""
Athlete History Analyzer.

Provides personalized adjustments based on athlete's training history.
Uses PerformanceTrend data to identify patterns.
"""
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from datetime import datetime, timedelta, timezone

from app.models import Athlete, PerformanceTrend, Exercise, ExerciseSet, WorkoutSession


class AthleteHistoryAnalyzer:
    """
    Analyzes athlete's training history for personalized recommendations.
    
    Identifies:
    - Exercises with poor performance history
    - Exercises with good progress
    - Volume/intensity patterns
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def analyze(
        self,
        athlete_id: int,
        plan_data: Dict
    ) -> Dict:
        """
        Analyze athlete history and provide personalized notes.
        
        Args:
            athlete_id: Athlete ID
            plan_data: Plan data with exercises
            
        Returns:
            Dict with personalized analysis
        """
        # Get athlete
        athlete = self.db.query(Athlete).filter(Athlete.id == athlete_id).first()
        if not athlete:
            return {"personalized_notes": []}
        
        # Get recent performance trends (last 30 days)
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=30)
        recent_trends = (
            self.db.query(PerformanceTrend)
            .filter(
                PerformanceTrend.athlete_id == athlete_id,
                PerformanceTrend.session_date >= cutoff_date
            )
            .order_by(desc(PerformanceTrend.session_date))
            .limit(20)
            .all()
        )
        
        if not recent_trends:
            return {"personalized_notes": []}
        
        # Analyze exercise performance
        exercise_performance = self._analyze_exercise_performance(athlete_id, plan_data)
        
        # Generate personalized notes
        personalized_notes = []
        
        # Check for exercises with poor performance
        from app.utils.constants import HIGH_RPE_THRESHOLD
        poor_performers = [
            ex for ex, data in exercise_performance.items()
            if data.get("avg_rpe", 0) > HIGH_RPE_THRESHOLD or data.get("struggles", 0) > 2
        ]
        
        if poor_performers:
            personalized_notes.append(
                f"Consider reducing intensity for: {', '.join(poor_performers[:3])}. "
                f"These exercises have shown high RPE or frequent struggles in recent sessions."
            )
        
        # Check for exercises with good progress
        good_performers = [
            ex for ex, data in exercise_performance.items()
            if data.get("progress", 0) > 0.05 and data.get("sessions", 0) >= 3
        ]
        
        if good_performers:
            personalized_notes.append(
                f"Strong progress on: {', '.join(good_performers[:3])}. "
                f"Consider maintaining or slightly increasing load on these exercises."
            )
        
        # Check overall volume trends
        avg_volume = sum(t.total_volume for t in recent_trends) / len(recent_trends)
        if avg_volume > 0:
            plan_volume = self._estimate_plan_volume(plan_data)
            if plan_volume > avg_volume * 1.2:
                personalized_notes.append(
                    f"Plan volume ({plan_volume:.0f} kg/week) is 20%+ higher than recent average ({avg_volume:.0f} kg/week). "
                    f"Consider gradual volume progression to avoid overreaching."
                )
        
        return {
            "personalized_notes": personalized_notes,
            "exercise_performance": exercise_performance,
            "recent_sessions_analyzed": len(recent_trends),
        }
    
    def _analyze_exercise_performance(
        self,
        athlete_id: int,
        plan_data: Dict
    ) -> Dict[str, Dict]:
        """
        Analyze performance for exercises in the plan.
        
        Args:
            athlete_id: Athlete ID
            plan_data: Plan data
            
        Returns:
            Dict mapping exercise name to performance metrics
        """
        # Get exercise IDs from plan
        exercise_ids = []
        for workout_day in plan_data.get("workout_days", []):
            for exercise in workout_day.get("exercises", []):
                ex_id = exercise.get("exercise_id")
                if ex_id:
                    exercise_ids.append(ex_id)
        
        if not exercise_ids:
            return {}
        
        # Get recent sessions (last 30 days)
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=30)
        sessions = (
            self.db.query(WorkoutSession)
            .filter(
                WorkoutSession.athlete_id == athlete_id,
                WorkoutSession.session_date >= cutoff_date
            )
            .all()
        )
        
        exercise_performance = {}
        
        session_ids = [s.id for s in sessions]
        all_exercise_sets = (
            self.db.query(ExerciseSet)
            .filter(
                ExerciseSet.workout_session_id.in_(session_ids),
                ExerciseSet.exercise_id.in_(exercise_ids)
            )
            .all()
        )
        
        # Group sets by (session_id, exercise_id) for efficient lookup
        sets_by_session_exercise = {}
        for set_record in all_exercise_sets:
            key = (set_record.workout_session_id, set_record.exercise_id)
            if key not in sets_by_session_exercise:
                sets_by_session_exercise[key] = []
            sets_by_session_exercise[key].append(set_record)
        
        all_exercises = (
            self.db.query(Exercise)
            .filter(Exercise.id.in_(exercise_ids))
            .all()
        )
        exercise_map = {ex.id: ex for ex in all_exercises}
        
        for ex_id in exercise_ids:
            # Use pre-loaded exercise map instead of querying
            ex = exercise_map.get(ex_id)
            if not ex:
                continue
            
            # Get sets for this exercise in recent sessions
            all_sets = []
            struggles = 0
            
            for session in sessions:
                sets = sets_by_session_exercise.get((session.id, ex_id), [])
                
                for set_record in sets:
                    if set_record.rpe:
                        all_sets.append(set_record.rpe)
                    from app.utils.constants import STRUGGLE_RPE_THRESHOLD
                    if set_record.rpe and set_record.rpe > STRUGGLE_RPE_THRESHOLD:
                        struggles += 1
            
            if all_sets:
                avg_rpe = sum(all_sets) / len(all_sets)
                max_rpe = max(all_sets)
                
                # Calculate progress (weight increase over time)
                progress = 0.0
                if len(sessions) >= 2:
                    # Simple progress estimate
                    recent_weights = [
                        set_record.weight for set_record in all_sets if set_record.weight
                    ]
                    if len(recent_weights) >= 4:
                        first_half = recent_weights[:len(recent_weights)//2]
                        second_half = recent_weights[len(recent_weights)//2:]
                        if first_half and second_half:
                            avg_first = sum(first_half) / len(first_half)
                            avg_second = sum(second_half) / len(second_half)
                            if avg_first > 0:
                                progress = (avg_second - avg_first) / avg_first
                
                # Get unique session IDs
                session_ids = set()
                for set_record in all_sets:
                    if hasattr(set_record, 'workout_session_id'):
                        session_ids.add(set_record.workout_session_id)
                    else:
                        # If sets don't have session_id, count from sessions list
                        session_ids.add(session.id)
                
                exercise_performance[ex.name] = {
                    "avg_rpe": round(avg_rpe, 1),
                    "max_rpe": round(max_rpe, 1),
                    "struggles": struggles,
                    "sessions": len(session_ids),
                    "progress": round(progress, 3),
                }
        
        return exercise_performance
    
    def _estimate_plan_volume(self, plan_data: Dict) -> float:
        """
        Estimate weekly volume from plan.
        
        Args:
            plan_data: Plan data
            
        Returns:
            Estimated weekly volume in kg
        """
        # This is a simplified estimate
        # In practice, would need exercise weights from athlete's PRs
        total_sets = 0
        
        for workout_day in plan_data.get("workout_days", []):
            for exercise in workout_day.get("exercises", []):
                sets_min = exercise.get("target_sets_min", 0)
                sets_max = exercise.get("target_sets_max", 0)
                avg_sets = (sets_min + sets_max) / 2 if sets_max > 0 else sets_min
                total_sets += avg_sets
        
        # Rough estimate: 10kg per set (very rough)
        return total_sets * 10

