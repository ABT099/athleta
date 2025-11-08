"""
Plan updater service.

Updates PlanEntry records and generates next workout with adjusted parameters.
"""
from typing import Dict, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session, undefer

from app.models import (
    PlanEntry, WorkoutDay, WorkoutDayExercise,
    WorkoutSession, ExerciseSet, RecoveryMetrics
)
from app.schemas.workout import (
    WorkoutDayResponse,
    WorkoutDayExerciseResponse,
)


class PlanUpdaterService:
    """
    Updates training plans and generates next workout prescriptions.
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def update_plan_entry_after_workout(
        self,
        plan_entry_id: int,
        workout_session: WorkoutSession,
        recovery_metrics: RecoveryMetrics,
        ai_adjustments: Dict
    ):
        """
        Update PlanEntry with completed workout data and AI adjustments.
        
        Args:
            plan_entry_id: PlanEntry ID
            workout_session: Completed workout session
            recovery_metrics: Recovery metrics
            ai_adjustments: AI-generated adjustments
        """
        plan_entry = self.db.query(PlanEntry).filter(
            PlanEntry.id == plan_entry_id
        ).first()
        
        if not plan_entry:
            return
        
        # Update completed workouts count
        plan_entry.completed_workouts += 1
        
        # Update average metrics
        if workout_session.overall_rpe:
            if plan_entry.average_rpe:
                # Running average
                total_workouts = plan_entry.completed_workouts
                plan_entry.average_rpe = (
                    (plan_entry.average_rpe * (total_workouts - 1) + workout_session.overall_rpe)
                    / total_workouts
                )
            else:
                plan_entry.average_rpe = workout_session.overall_rpe
        
        # Update average recovery score
        if recovery_metrics.readiness_score:
            if plan_entry.average_recovery_score:
                total_workouts = plan_entry.completed_workouts
                plan_entry.average_recovery_score = (
                    (plan_entry.average_recovery_score * (total_workouts - 1) + recovery_metrics.readiness_score)
                    / total_workouts
                )
            else:
                plan_entry.average_recovery_score = recovery_metrics.readiness_score
        
        # Update total volume
        if workout_session.total_volume:
            if plan_entry.total_volume:
                plan_entry.total_volume += workout_session.total_volume
            else:
                plan_entry.total_volume = workout_session.total_volume
        
        # Store AI adjustments
        plan_entry.ai_adjustments = ai_adjustments
        
        # Apply multipliers from adjustments
        if ai_adjustments.get("volume_multiplier"):
            plan_entry.target_volume_multiplier = ai_adjustments["volume_multiplier"]
        if ai_adjustments.get("intensity_multiplier"):
            plan_entry.target_intensity_multiplier = ai_adjustments["intensity_multiplier"]
        
        self.db.commit()
    
    def generate_next_workout(
        self,
        athlete_id: int,
        workout_day_id: int,
        ai_adjustments: Dict,
        injury_warnings: List[str],
        recovery_recommendations: List[str]
    ) -> Dict:
        """
        Generate next workout with AI-adjusted parameters.
        
        Args:
            athlete_id: Athlete ID
            workout_day_id: Workout day to generate (could be next in rotation)
            ai_adjustments: AI adjustments to apply
            injury_warnings: Injury warnings
            recovery_recommendations: Recovery recommendations
            
        Returns:
            Dict with next workout data
        """
        workout_day = self.db.query(WorkoutDay).filter(
            WorkoutDay.id == workout_day_id
        ).first()
        
        if not workout_day:
            raise ValueError(f"Workout day {workout_day_id} not found")
        
        # Get prescribed exercises
        prescribed_exercises = (
            self.db.query(WorkoutDayExercise)
            .filter(WorkoutDayExercise.workout_day_id == workout_day_id)
            .order_by(WorkoutDayExercise.order_in_workout)
            .all()
        )
        
        # Apply adjustments to each exercise
        adjusted_exercises = []
        exercise_adjustments = ai_adjustments.get("exercise_adjustments", {})
        volume_mult = ai_adjustments.get("volume_multiplier", 1.0)
        intensity_mult = ai_adjustments.get("intensity_multiplier", 1.0)
        
        for prescribed in prescribed_exercises:
            # Get exercise-specific adjustments if available
            ex_adj = exercise_adjustments.get(str(prescribed.exercise_id), {})
            ex_volume_mult = ex_adj.get("volume_multiplier", volume_mult)
            ex_intensity_mult = ex_adj.get("intensity_multiplier", intensity_mult)
            
            # Calculate adjusted parameters
            adjusted_sets = max(1, int(prescribed.target_sets * ex_volume_mult))
            
            # Get last weight used for this exercise
            last_weight = self._get_last_weight_used(
                athlete_id, prescribed.exercise_id
            )
            
            # Calculate adjusted weight
            adjusted_weight = None
            if last_weight:
                adjusted_weight = round(last_weight * ex_intensity_mult / 2.5) * 2.5  # Round to 2.5kg
            
            # Adjust rep ranges slightly based on volume
            reps_adjustment = 0
            if ex_volume_mult > 1.05:
                reps_adjustment = 1  # Add a rep
            elif ex_volume_mult < 0.95:
                reps_adjustment = -1  # Remove a rep
            
            adjusted_reps_min = max(1, prescribed.target_reps_min + reps_adjustment)
            adjusted_reps_max = max(adjusted_reps_min, prescribed.target_reps_max + reps_adjustment)
            
            # Create adjusted exercise response
            adjusted_ex = WorkoutDayExerciseResponse(
                id=prescribed.id,
                workout_day_id=prescribed.workout_day_id,
                exercise_id=prescribed.exercise_id,
                order_in_workout=prescribed.order_in_workout,
                target_sets=prescribed.target_sets,
                target_reps_min=prescribed.target_reps_min,
                target_reps_max=prescribed.target_reps_max,
                target_rpe=prescribed.target_rpe,
                target_rir=prescribed.target_rir,
                rest_period_seconds=prescribed.rest_period_seconds,
                tempo=prescribed.tempo,
                notes=prescribed.notes,
                is_primary=bool(prescribed.is_primary),
                progression_scheme=prescribed.progression_scheme,
                adjusted_weight=adjusted_weight,
                adjusted_sets=adjusted_sets,
                adjusted_reps_min=adjusted_reps_min,
                adjusted_reps_max=adjusted_reps_max,
                adjustment_reason=ex_adj.get("reason", ai_adjustments.get("reasoning", "Standard progression"))
            )
            
            adjusted_exercises.append(adjusted_ex)
        
        # Undefer deferred fields for response
        workout_day = self.db.query(WorkoutDay).options(
            undefer(WorkoutDay.name),
            undefer(WorkoutDay.description),
            undefer(WorkoutDay.created_at)
        ).filter(WorkoutDay.id == workout_day.id).first()
        
        # Create workout day response
        workout_day_response = WorkoutDayResponse(
            id=workout_day.id,
            workout_plan_id=workout_day.workout_plan_id,
            name=workout_day.name,
            description=workout_day.description,
            day_of_week=workout_day.day_of_week,
            order_in_week=workout_day.order_in_week,
            target_muscle_groups=workout_day.target_muscle_groups,
            exercises=adjusted_exercises,
            created_at=workout_day.created_at
        )
        
        # Generate adjustments summary
        adjustments_summary = {
            "volume_change": f"{(volume_mult - 1) * 100:+.1f}%",
            "intensity_change": f"{(intensity_mult - 1) * 100:+.1f}%",
            "reasoning": ai_adjustments.get("reasoning", "Standard progression"),
            "exercises_adjusted": len(exercise_adjustments)
        }
        
        # Calculate weekly progress
        weekly_progress = self._calculate_weekly_progress(athlete_id)
        
        return {
            "workout_day": workout_day_response,
            "adjustments_summary": adjustments_summary,
            "injury_warnings": injury_warnings,
            "recovery_recommendations": recovery_recommendations,
            "weekly_progress": weekly_progress
        }
    
    def _get_last_weight_used(self, athlete_id: int, exercise_id: int) -> float:
        """
        Get the last weight used for an exercise.
        
        Args:
            athlete_id: Athlete ID
            exercise_id: Exercise ID
            
        Returns:
            Last weight used (kg) or None
        """
        last_set = (
            self.db.query(ExerciseSet)
            .join(WorkoutSession)
            .filter(
                WorkoutSession.athlete_id == athlete_id,
                ExerciseSet.exercise_id == exercise_id
            )
            .order_by(WorkoutSession.session_date.desc())
            .first()
        )
        
        return last_set.weight if last_set else None
    
    def _calculate_weekly_progress(self, athlete_id: int) -> Dict:
        """
        Calculate weekly progress metrics.
        
        Args:
            athlete_id: Athlete ID
            
        Returns:
            Dict with weekly progress
        """
        # Get workouts from this week
        week_start = datetime.utcnow() - timedelta(days=datetime.utcnow().weekday())
        
        weekly_sessions = (
            self.db.query(WorkoutSession)
            .filter(
                WorkoutSession.athlete_id == athlete_id,
                WorkoutSession.session_date >= week_start
            )
            .all()
        )
        
        if not weekly_sessions:
            return {
                "workouts_this_week": 0,
                "total_volume": 0,
                "average_rpe": None,
                "trend": "starting"
            }
        
        # Calculate metrics
        total_volume = sum(s.total_volume or 0 for s in weekly_sessions)
        rpe_values = [s.overall_rpe for s in weekly_sessions if s.overall_rpe]
        avg_rpe = sum(rpe_values) / len(rpe_values) if rpe_values else None
        
        # Compare to last week
        last_week_start = week_start - timedelta(days=7)
        last_week_sessions = (
            self.db.query(WorkoutSession)
            .filter(
                WorkoutSession.athlete_id == athlete_id,
                WorkoutSession.session_date >= last_week_start,
                WorkoutSession.session_date < week_start
            )
            .all()
        )
        
        trend = "stable"
        if last_week_sessions:
            last_week_volume = sum(s.total_volume or 0 for s in last_week_sessions)
            if last_week_volume > 0:
                volume_change = (total_volume - last_week_volume) / last_week_volume
                if volume_change > 0.05:
                    trend = "increasing"
                elif volume_change < -0.05:
                    trend = "decreasing"
        
        return {
            "workouts_this_week": len(weekly_sessions),
            "total_volume": round(total_volume, 1),
            "average_rpe": round(avg_rpe, 1) if avg_rpe else None,
            "trend": trend,
            "volume_vs_last_week": f"{((total_volume / sum(s.total_volume or 0 for s in last_week_sessions or [1])) - 1) * 100:+.1f}%" if last_week_sessions else "N/A"
        }
    
    def create_plan_entry_for_week(
        self,
        workout_plan_id: int,
        week_number: int,
        start_date: datetime,
        training_phase: str
    ) -> PlanEntry:
        """
        Create a new PlanEntry for a week.
        
        Args:
            workout_plan_id: Workout plan ID
            week_number: Week number
            start_date: Week start date
            training_phase: Training phase
            
        Returns:
            Created PlanEntry
        """
        from app.utils.constants import TrainingPhase
        
        # Determine if deload week (every 4th week)
        is_deload = (week_number % 4 == 0)
        
        plan_entry = PlanEntry(
            workout_plan_id=workout_plan_id,
            week_number=week_number,
            start_date=start_date,
            end_date=start_date + timedelta(days=7),
            training_phase=TrainingPhase(training_phase),
            target_volume_multiplier=0.5 if is_deload else 1.0,
            target_intensity_multiplier=0.9 if is_deload else 1.0,
            is_deload_week=1 if is_deload else 0
        )
        
        self.db.add(plan_entry)
        self.db.commit()
        self.db.refresh(plan_entry)
        
        return plan_entry


