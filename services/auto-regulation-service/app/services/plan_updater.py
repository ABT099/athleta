"""
Plan updater service.

Updates PlanEntry records and generates next workout with adjusted parameters.
"""
from typing import Dict, List
from datetime import datetime, timedelta, timezone
from autoregulation.utils.constants import DELOAD_INTENSITY_MULTIPLIER, DELOAD_VOLUME_MULTIPLIER
from sqlalchemy.orm import Session, undefer

from autoregulation.models import (
    PlanEntry, WorkoutDay, WorkoutDayExercise,
    WorkoutSession, ExerciseSet, RecoveryMetrics, Exercise
)
from autoregulation.schemas.workout import (
    WorkoutDayResponse,
    WorkoutDayExerciseResponse,
    WarmupSetSchema,
)
from autoregulation.services.warmup_generator import WarmupGenerator
from autoregulation.services.pr_tracker import PRTrackerService


class PlanUpdaterService:
    """
    Updates training plans and generates next workout prescriptions.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.warmup_generator = WarmupGenerator()
    
    def update_plan_entry_after_workout(
        self,
        plan_entry_id: int,
        workout_session: WorkoutSession,
        recovery_metrics: RecoveryMetrics,
        ai_adjustments: Dict,
        commit: bool = True
    ):
        """
        Update PlanEntry with completed workout data and AI adjustments.
        
        Args:
            plan_entry_id: PlanEntry ID
            workout_session: Completed workout session
            recovery_metrics: Recovery metrics
            ai_adjustments: AI-generated adjustments
            commit: Whether to commit the transaction (default: True). Set to False when called within a larger transaction.
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
        
        # Commit only if requested (default: True for standalone calls)
        # When called from complete_workout, commit=False to avoid nested commits
        if commit:
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
        
        # Get plan context for weekly progression
        from autoregulation.services.progressive_overload_engine import ProgressiveOverloadEngine
        engine = ProgressiveOverloadEngine(self.db)
        plan_context = engine.analyze_plan_context(athlete_id)
        
        # Extract recovery indicators from recommendations
        recovery_score = self._estimate_recovery_from_recommendations(recovery_recommendations)
        
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
            
            # Calculate adjusted sets using dynamic range selection
            adjusted_sets = self._calculate_dynamic_sets(
                prescribed=prescribed,
                plan_context=plan_context,
                recovery_score=recovery_score,
                volume_multiplier=ex_volume_mult
            )
            
            # Calculate adjusted weight using PR if available
            pr_tracker = PRTrackerService(self.db)
            target_reps_avg = (prescribed.target_reps_min + prescribed.target_reps_max) / 2
            pr_record = pr_tracker.get_pr_for_rep_range(
                prescribed.exercise_id,
                athlete_id,
                target_reps_avg
            )
            
            adjusted_weight = None
            if pr_record:
                # Use % of PR based on week/phase
                training_pct = pr_tracker.calculate_training_percentage(
                    plan_context.get("week_number", 1),
                    plan_context.get("current_phase", "accumulation"),
                    plan_context.get("is_deload_week", False)
                )
                base_weight = pr_record["weight"] * training_pct
                # Apply intensity multiplier
                adjusted_weight = round(base_weight * ex_intensity_mult / 2.5) * 2.5
            else:
                # Fallback to old method (last weight)
                last_weight = self._get_last_weight_used(
                    athlete_id, prescribed.exercise_id
                )
                if last_weight:
                    adjusted_weight = round(last_weight * ex_intensity_mult / 2.5) * 2.5
            
            # Adjust rep ranges slightly based on volume
            reps_adjustment = 0
            from autoregulation.utils.constants import (
                VOLUME_MULTIPLIER_INCREASE_THRESHOLD,
                VOLUME_MULTIPLIER_DECREASE_THRESHOLD
            )
            if ex_volume_mult > VOLUME_MULTIPLIER_INCREASE_THRESHOLD:
                reps_adjustment = 1  # Add a rep
            elif ex_volume_mult < VOLUME_MULTIPLIER_DECREASE_THRESHOLD:
                reps_adjustment = -1  # Remove a rep
            
            adjusted_reps_min = max(1, prescribed.target_reps_min + reps_adjustment)
            adjusted_reps_max = max(adjusted_reps_min, prescribed.target_reps_max + reps_adjustment)
            
            # Generate warm-up sets if auto-generate is enabled
            warmup_sets = None
            if adjusted_weight:
                # Determine number of warm-up sets if not set
                num_warmup_sets = prescribed.warm_up_sets
                if num_warmup_sets == 0:
                    # Auto-determine based on exercise characteristics
                    exercise = self.db.query(Exercise).filter(
                        Exercise.id == prescribed.exercise_id
                    ).first()
                    if exercise:
                        num_warmup_sets = self.warmup_generator.determine_warmup_set_count(
                            exercise, bool(prescribed.is_primary)
                        )
                
                # Calculate set range position for context-aware warmup
                sets_range_position = None
                sets_min = prescribed.target_sets_min
                sets_max = prescribed.target_sets_max
                if sets_max > sets_min and adjusted_sets is not None:
                    # Calculate position: 0.0 = at min, 1.0 = at max
                    sets_range_position = (adjusted_sets - sets_min) / (sets_max - sets_min)
                    sets_range_position = max(0.0, min(1.0, sets_range_position))
                
                # Get deload status from plan context
                is_deload_week = plan_context.get("is_deload_week", False)
                
                # Generate warm-up sets with context
                if num_warmup_sets > 0:
                    warmup_data = self.warmup_generator.generate_warmup_sets(
                        working_weight=adjusted_weight,
                        num_warmup_sets=num_warmup_sets,
                        exercise_type=exercise.exercise_type if exercise else None,
                        adjusted_sets=adjusted_sets,
                        sets_range_position=sets_range_position,
                        is_deload_week=is_deload_week
                    )
                    warmup_sets = [WarmupSetSchema(**warmup) for warmup in warmup_data]
            
            # Get intensity technique recommendations from AI adjustments
            intensity_technique = ex_adj.get("intensity_technique", {})
            
            # Create adjusted exercise response
            adjusted_ex = WorkoutDayExerciseResponse(
                id=prescribed.id,
                workout_day_id=prescribed.workout_day_id,
                exercise_id=prescribed.exercise_id,
                order_in_workout=prescribed.order_in_workout,
                target_sets_min=prescribed.target_sets_min,
                target_sets_max=prescribed.target_sets_max,
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
                adjustment_reason=ex_adj.get("reason", ai_adjustments.get("reasoning", "Standard progression")),
                warm_up_sets=prescribed.warm_up_sets,
                warmup_sets=warmup_sets,
                # Include intensity techniques from AI recommendations or prescribed values
                # Use explicit None checks to preserve empty dicts (which are falsy but valid)
                set_type=intensity_technique.get("set_type") if intensity_technique.get("set_type") is not None else prescribed.set_type,
                rep_style=intensity_technique.get("rep_style") if intensity_technique.get("rep_style") is not None else prescribed.rep_style,
                set_type_params=intensity_technique.get("set_type_params") if "set_type_params" in intensity_technique else prescribed.set_type_params,
                rep_style_params=intensity_technique.get("rep_style_params") if "rep_style_params" in intensity_technique else prescribed.rep_style_params
            )
            
            adjusted_exercises.append(adjusted_ex)
        
        # Undefer deferred fields for response
        workout_day = self.db.query(WorkoutDay).options(
            undefer(WorkoutDay.name),
            undefer(WorkoutDay.created_at)
        ).filter(WorkoutDay.id == workout_day.id).first()
        
        # Create workout day response
        workout_day_response = WorkoutDayResponse(
            id=workout_day.id,
            workout_plan_id=workout_day.workout_plan_id,
            name=workout_day.name,
            day_of_week=workout_day.day_of_week,
            order_in_week=workout_day.order_in_week,
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
    
    def _calculate_dynamic_sets(
        self,
        prescribed: WorkoutDayExercise,
        plan_context: Dict,
        recovery_score: float,
        volume_multiplier: float
    ) -> int:
        """
        Calculate optimal number of sets using weekly progression and recovery.
        
        Implements Option 3c: Weekly progression + Recovery adaptation
        
        Args:
            prescribed: Prescribed exercise with set range
            plan_context: Plan context with week number, deload status, etc.
            recovery_score: Recovery score (0.0 = poor, 1.0 = excellent)
            volume_multiplier: Volume multiplier from AI adjustments
            
        Returns:
            Optimal number of sets within [min, max] range
        """
        sets_min = prescribed.target_sets_min
        sets_max = prescribed.target_sets_max
        sets_range = sets_max - sets_min
        
        # If range is 0, just return the single value
        if sets_range == 0:
            return max(1, int(sets_min * volume_multiplier))
        
        # === 1. Weekly Progression ===
        # Progress from min to max over mesocycle
        week_number = plan_context.get("week_number", 1)
        is_deload = plan_context.get("is_deload_week", False)
        duration_weeks = plan_context.get("duration_weeks", 12)  # Default 12 weeks
        
        if is_deload:
            # Deload week: use minimum sets
            base_sets = sets_min
        else:
            # Calculate progression: early weeks = min, peak weeks = max
            # Use a smooth progression curve
            progress_ratio = min(1.0, (week_number - 1) / max(1, duration_weeks - 1))
            # Apply a slight curve (ease in) for more gradual progression
            progress_curve = progress_ratio ** 0.7
            base_sets = sets_min + (sets_range * progress_curve)
            base_sets = round(base_sets)
        
        # === 2. Recovery Adaptation ===
        # Adjust within range based on recovery status
        from autoregulation.utils.constants import (
            POOR_RECOVERY_THRESHOLD, EXCELLENT_RECOVERY_THRESHOLD,
            POOR_RECOVERY_SET_REDUCTION_LARGE, POOR_RECOVERY_SET_REDUCTION_SMALL,
            EXCELLENT_RECOVERY_SET_INCREASE
        )
        
        # Poor recovery (0.0-0.4) → reduce by 1-2 sets
        # Good recovery (0.6-1.0) → can increase within range
        # Medium recovery (0.4-0.6) → stay at base
        
        recovery_adjustment = 0
        if recovery_score < POOR_RECOVERY_THRESHOLD:
            # Poor recovery: reduce sets
            recovery_adjustment = POOR_RECOVERY_SET_REDUCTION_LARGE if sets_range >= 2 else POOR_RECOVERY_SET_REDUCTION_SMALL
        elif recovery_score > EXCELLENT_RECOVERY_THRESHOLD:
            # Excellent recovery: can increase if room
            if base_sets < sets_max:
                recovery_adjustment = EXCELLENT_RECOVERY_SET_INCREASE
        # Medium recovery: no adjustment
        
        # === 3. Apply Volume Multiplier ===
        # Volume multiplier can further adjust
        volume_adjusted = base_sets + recovery_adjustment
        volume_adjusted = int(volume_adjusted * volume_multiplier)
        
        # === 4. Clamp to Range ===
        final_sets = max(sets_min, min(sets_max, volume_adjusted))
        
        return final_sets
    
    def _estimate_recovery_from_recommendations(self, recovery_recommendations: List[str]) -> float:
        """
        Estimate recovery score from recovery recommendations.
        
        Args:
            recovery_recommendations: List of recovery recommendation strings
            
        Returns:
            Recovery score (0.0 = poor, 1.0 = excellent)
        """
        if not recovery_recommendations:
            return 0.7  # Default to moderate recovery
        
        # Analyze recommendations for recovery indicators
        recommendations_text = " ".join(recovery_recommendations).lower()
        
        # Negative indicators (poor recovery)
        poor_indicators = ["rest", "recovery", "fatigue", "tired", "sore", "reduce", "lower", "deload"]
        # Positive indicators (good recovery)
        good_indicators = ["ready", "fresh", "energized", "good", "excellent", "strong"]
        
        poor_count = sum(1 for indicator in poor_indicators if indicator in recommendations_text)
        good_count = sum(1 for indicator in good_indicators if indicator in recommendations_text)
        
        # Calculate score
        if poor_count > good_count:
            # More poor indicators
            score = max(0.2, 0.7 - (poor_count * 0.15))
        elif good_count > poor_count:
            # More good indicators
            score = min(1.0, 0.7 + (good_count * 0.1))
        else:
            # Balanced or neutral
            score = 0.6
        
        return score
    
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
        now = datetime.now(timezone.utc)
        week_start = now - timedelta(days=now.weekday())
        
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
                "trend": "starting",
                "volume_vs_last_week": "N/A"
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
        last_week_volume = 0
        volume_vs_last_week = "N/A"
        
        if last_week_sessions:
            last_week_volume = sum(s.total_volume or 0 for s in last_week_sessions)
            if last_week_volume > 0:
                volume_change = (total_volume - last_week_volume) / last_week_volume
                volume_vs_last_week = f"{volume_change * 100:+.1f}%"
                
                if volume_change > 0.05:
                    trend = "increasing"
                elif volume_change < -0.05:
                    trend = "decreasing"
            elif total_volume > 0:
                # Last week 0, this week > 0
                trend = "increasing"
                volume_vs_last_week = "+100.0%"  # Technically infinite, but show +100% or similar
        
        return {
            "workouts_this_week": len(weekly_sessions),
            "total_volume": round(total_volume, 1),
            "average_rpe": round(avg_rpe, 1) if avg_rpe else None,
            "trend": trend,
            "volume_vs_last_week": volume_vs_last_week
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
        from autoregulation.utils.constants import TrainingPhase
        
        # Determine if deload week (every 4th week)
        is_deload = (week_number % 4 == 0)
        
        plan_entry = PlanEntry(
            workout_plan_id=workout_plan_id,
            week_number=week_number,
            start_date=start_date,
            end_date=start_date + timedelta(days=7),
            training_phase=TrainingPhase(training_phase),
            target_volume_multiplier=DELOAD_VOLUME_MULTIPLIER if is_deload else 1.0,
            target_intensity_multiplier=DELOAD_INTENSITY_MULTIPLIER if is_deload else 1.0,
            is_deload_week=1 if is_deload else 0
        )
        
        self.db.add(plan_entry)
        # Commit here because this creates a new plan entry independently
        # This method may be called outside of larger transactions
        self.db.commit()
        self.db.refresh(plan_entry)
        
        return plan_entry


