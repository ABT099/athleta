"""
Personal Record (PR) tracking service.

Automatically detects, stores, and uses PRs for smarter progression.
"""
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from autoregulation.models import (
    ExercisePersonalRecord, ExerciseSet, WorkoutSession, Exercise
)
from autoregulation.services.training_calculations import TrainingCalculations


class PRTrackerService:
    """
    Manages personal record detection, storage, and retrieval.
    """
    
    # Rep ranges for PR detection (inclusive)
    REP_RANGES = {
        1: (1, 1),      # 1RM
        3: (2, 3),      # 3RM
        5: (4, 5),      # 5RM
        8: (6, 8),      # 8RM
        10: (9, 10),    # 10RM
        12: (11, 12),   # 12RM
    }
    
    def __init__(self, db: Session):
        self.db = db
        self.calc = TrainingCalculations()
    
    def detect_and_update_prs(self, workout_session_id: int, commit: bool = True) -> Dict:
        """
        Detect and update PRs from a completed workout session.
        
        Args:
            workout_session_id: Workout session ID
            commit: Whether to commit the transaction (default: True). Set to False when called within a larger transaction.
            
        Returns:
            Dict with PR updates and achievements
        """
        session = self.db.query(WorkoutSession).filter(
            WorkoutSession.id == workout_session_id
        ).first()
        
        if not session:
            return {"achievements": [], "updates": []}
        
        athlete_id = session.athlete_id
        session_date = session.session_date
        
        # Get all sets for this session
        sets = self.db.query(ExerciseSet).filter(
            ExerciseSet.workout_session_id == workout_session_id
        ).all()
        
        if not sets:
            return {"achievements": [], "updates": []}
        
        # Group sets by exercise
        exercise_sets = {}
        for set_record in sets:
            ex_id = set_record.exercise_id
            if ex_id not in exercise_sets:
                exercise_sets[ex_id] = []
            exercise_sets[ex_id].append(set_record)
        
        achievements = []
        updates = []
        records_to_update = []
        
        # Process each exercise
        for exercise_id, sets_list in exercise_sets.items():
            # Get or create PR record
            pr_record = self._get_or_create_pr_record(athlete_id, exercise_id)
            
            # Check rep-max PRs
            rep_max_updates = self._check_rep_max_prs(
                pr_record, sets_list, session_date
            )
            updates.extend(rep_max_updates)
            
            # Check volume PRs
            volume_updates = self._check_volume_prs(
                pr_record, sets_list, session_date
            )
            updates.extend(volume_updates)
            
            # Generate achievement messages
            for update in rep_max_updates + volume_updates:
                if update.get("is_new_pr"):
                    achievements.append(self._format_achievement(update))
            
            # Update metadata if any PRs were set
            if rep_max_updates or volume_updates:
                pr_record.total_pr_count += len([u for u in rep_max_updates + volume_updates if u.get("is_new_pr")])
                pr_record.last_pr_date = session_date
                pr_record.updated_at = datetime.now(timezone.utc)
                records_to_update.append(pr_record)
        
        # Persist changes: flush when commit=False, commit when commit=True
        # When called from complete_workout, commit=False to avoid nested commits
        # but we still need to flush to persist changes in the parent transaction
        if records_to_update:
            if commit:
                self.db.commit()
            else:
                self.db.flush()  # Flush changes to persist in parent transaction
        
        return {
            "achievements": achievements,
            "updates": updates
        }
    
    def _get_or_create_pr_record(
        self, athlete_id: int, exercise_id: int
    ) -> ExercisePersonalRecord:
        """Get existing PR record or create new one."""
        pr_record = self.db.query(ExercisePersonalRecord).filter(
            and_(
                ExercisePersonalRecord.athlete_id == athlete_id,
                ExercisePersonalRecord.exercise_id == exercise_id
            )
        ).first()
        
        if not pr_record:
            pr_record = ExercisePersonalRecord(
                athlete_id=athlete_id,
                exercise_id=exercise_id,
                total_pr_count=0
            )
            self.db.add(pr_record)
            self.db.flush()
        
        return pr_record
    
    def _check_rep_max_prs(
        self, pr_record: ExercisePersonalRecord, sets: List[ExerciseSet], session_date: datetime
    ) -> List[Dict]:
        """Check for rep-max PRs (1RM, 3RM, 5RM, etc.)."""
        updates = []
        
        # Find best set for each rep range
        for rep_max, (min_reps, max_reps) in self.REP_RANGES.items():
            # Find sets in this rep range
            matching_sets = [
                s for s in sets
                if min_reps <= s.reps <= max_reps
            ]
            
            if not matching_sets:
                continue
            
            # Find heaviest weight in this rep range
            best_set = max(matching_sets, key=lambda s: s.weight)
            weight = best_set.weight
            reps = best_set.reps
            
            # Get current PR for this rep range
            current_pr = self._get_rep_max_pr(pr_record, rep_max)
            current_pr_weight = current_pr[0] if current_pr else None
            
            # Check if this is a new PR
            if current_pr_weight is None or weight > current_pr_weight:
                # Update PR
                self._set_rep_max_pr(pr_record, rep_max, weight, session_date)
                
                improvement = weight - (current_pr_weight or 0)
                updates.append({
                    "exercise_id": pr_record.exercise_id,
                    "pr_type": f"{rep_max}RM",
                    "old_value": current_pr_weight,
                    "new_value": weight,
                    "improvement": improvement,
                    "reps": reps,
                    "is_new_pr": True
                })
        
        return updates
    
    def _check_volume_prs(
        self, pr_record: ExercisePersonalRecord, sets: List[ExerciseSet], session_date: datetime
    ) -> List[Dict]:
        """Check for volume PRs (total volume, total reps)."""
        updates = []
        
        # Calculate total volume (weight × reps)
        total_volume = sum(s.weight * s.reps for s in sets)
        total_reps = sum(s.reps for s in sets)
        
        # Check volume PR
        if pr_record.max_volume_session is None or total_volume > pr_record.max_volume_session:
            old_volume = pr_record.max_volume_session or 0
            pr_record.max_volume_session = total_volume
            pr_record.max_volume_date = session_date
            
            updates.append({
                "exercise_id": pr_record.exercise_id,
                "pr_type": "volume",
                "old_value": old_volume,
                "new_value": total_volume,
                "improvement": total_volume - old_volume,
                "is_new_pr": True
            })
        
        # Check total reps PR
        if pr_record.max_total_reps is None or total_reps > pr_record.max_total_reps:
            old_reps = pr_record.max_total_reps or 0
            pr_record.max_total_reps = total_reps
            pr_record.max_reps_date = session_date
            
            updates.append({
                "exercise_id": pr_record.exercise_id,
                "pr_type": "total_reps",
                "old_value": old_reps,
                "new_value": total_reps,
                "improvement": total_reps - old_reps,
                "is_new_pr": True
            })
        
        return updates
    
    def _get_rep_max_pr(self, pr_record: ExercisePersonalRecord, rep_max: int) -> Tuple[Optional[float], Optional[datetime]]:
        """Get PR weight and date for a rep range."""
        pr_map = {
            1: (pr_record.one_rep_max, pr_record.one_rm_date),
            3: (pr_record.three_rep_max, pr_record.three_rm_date),
            5: (pr_record.five_rep_max, pr_record.five_rm_date),
            8: (pr_record.eight_rep_max, pr_record.eight_rm_date),
            10: (pr_record.ten_rep_max, pr_record.ten_rm_date),
            12: (pr_record.twelve_rep_max, pr_record.twelve_rm_date),
        }
        return pr_map.get(rep_max, (None, None))
    
    def _set_rep_max_pr(
        self, pr_record: ExercisePersonalRecord, rep_max: int, weight: float, date: datetime
    ):
        """Set PR weight and date for a rep range."""
        if rep_max == 1:
            pr_record.one_rep_max = weight
            pr_record.one_rm_date = date
        elif rep_max == 3:
            pr_record.three_rep_max = weight
            pr_record.three_rm_date = date
        elif rep_max == 5:
            pr_record.five_rep_max = weight
            pr_record.five_rm_date = date
        elif rep_max == 8:
            pr_record.eight_rep_max = weight
            pr_record.eight_rm_date = date
        elif rep_max == 10:
            pr_record.ten_rep_max = weight
            pr_record.ten_rm_date = date
        elif rep_max == 12:
            pr_record.twelve_rep_max = weight
            pr_record.twelve_rm_date = date
    
    def _format_achievement(self, update: Dict) -> str:
        """Format PR achievement message."""
        pr_type = update["pr_type"]
        new_value = update["new_value"]
        improvement = update["improvement"]
        
        if pr_type == "volume":
            return f"🎉 Volume PR! {new_value:.1f}kg total (up {improvement:.1f}kg)"
        elif pr_type == "total_reps":
            return f"🎉 Rep PR! {int(new_value)} total reps (up {int(improvement)})"
        else:
            # Rep-max PR
            return f"🎉 New {pr_type} PR! {new_value:.1f}kg (up {improvement:.1f}kg)"
    
    def get_pr_for_rep_range(
        self, exercise_id: int, athlete_id: int, target_reps: float
    ) -> Optional[Dict]:
        """
        Get the most relevant PR for a target rep range.
        
        Args:
            exercise_id: Exercise ID
            athlete_id: Athlete ID
            target_reps: Target rep count (use midpoint of range)
            
        Returns:
            Dict with weight, reps, date, or None if no PR exists
        """
        pr_record = self.db.query(ExercisePersonalRecord).filter(
            and_(
                ExercisePersonalRecord.athlete_id == athlete_id,
                ExercisePersonalRecord.exercise_id == exercise_id
            )
        ).first()
        
        if not pr_record:
            return None
        
        # Find closest rep-max PR
        target_rep_int = int(round(target_reps))
        
        # Map target reps to rep-max category
        if target_rep_int <= 1:
            rep_max = 1
        elif target_rep_int <= 3:
            rep_max = 3
        elif target_rep_int <= 5:
            rep_max = 5
        elif target_rep_int <= 8:
            rep_max = 8
        elif target_rep_int <= 10:
            rep_max = 10
        else:
            rep_max = 12
        
        weight, date = self._get_rep_max_pr(pr_record, rep_max)
        
        if weight is None:
            return None
        
        return {
            "weight": weight,
            "reps": rep_max,
            "date": date,
            "rep_max": rep_max
        }
    
    def calculate_training_percentage(
        self, week_number: int, phase: str, is_deload: bool = False
    ) -> float:
        """
        Calculate training percentage of PR based on week and phase.
        
        Args:
            week_number: Current week in mesocycle
            phase: Training phase (accumulation, intensification, realization)
            is_deload: Whether this is a deload week
            
        Returns:
            Training percentage (0.0-1.0)
        """
        # Base percentages by phase
        from autoregulation.utils.constants import (
            PR_ACCUMULATION_PERCENTAGE, PR_INTENSIFICATION_PERCENTAGE, PR_REALIZATION_PERCENTAGE,
            PR_DELOAD_PERCENTAGE, PR_DEFAULT_PERCENTAGE,
            PR_WEEK_ADJUSTMENT_CAP, PR_WEEK_ADJUSTMENT_RATE, PR_MAX_PERCENTAGE
        )
        
        if is_deload:
            return PR_DELOAD_PERCENTAGE
        
        phase_percentages = {
            "accumulation": PR_ACCUMULATION_PERCENTAGE,
            "intensification": PR_INTENSIFICATION_PERCENTAGE,
            "realization": PR_REALIZATION_PERCENTAGE,
        }
        
        base_pct = phase_percentages.get(phase.lower(), PR_DEFAULT_PERCENTAGE)
        
        # Adjust slightly based on week (later weeks = slightly higher %)
        week_adjustment = min(PR_WEEK_ADJUSTMENT_CAP, (week_number - 1) * PR_WEEK_ADJUSTMENT_RATE)
        
        return min(PR_MAX_PERCENTAGE, base_pct + week_adjustment)
    
    def detect_plateau(
        self, exercise_id: int, athlete_id: int, weeks: int = 4
    ) -> Dict:
        """
        Detect if athlete has plateaued (no PRs in X weeks).
        
        Args:
            exercise_id: Exercise ID
            athlete_id: Athlete ID
            weeks: Number of weeks to check
            
        Returns:
            Dict with plateau status and details
        """
        pr_record = self.db.query(ExercisePersonalRecord).filter(
            and_(
                ExercisePersonalRecord.athlete_id == athlete_id,
                ExercisePersonalRecord.exercise_id == exercise_id
            )
        ).first()
        
        if not pr_record or not pr_record.last_pr_date:
            return {
                "is_plateaued": False,
                "weeks_since_pr": None,
                "message": None
            }
        
        # Handle timezone-naive dates from database
        last_pr = pr_record.last_pr_date
        if last_pr.tzinfo is None:
            last_pr = last_pr.replace(tzinfo=timezone.utc)
        weeks_since = (datetime.now(timezone.utc) - last_pr).days / 7
        
        is_plateaued = weeks_since >= weeks
        
        message = None
        if is_plateaued:
            message = f"No PRs in {int(weeks_since)} weeks. Consider deload or volume increase."
        
        return {
            "is_plateaued": is_plateaued,
            "weeks_since_pr": round(weeks_since, 1),
            "message": message
        }
    
    def compare_to_pr(
        self, exercise_id: int, athlete_id: int, best_set: Dict
    ) -> Dict:
        """
        Compare a set to the relevant PR.
        
        Args:
            exercise_id: Exercise ID
            athlete_id: Athlete ID
            best_set: Dict with weight, reps
            
        Returns:
            Dict with comparison data
        """
        pr_data = self.get_pr_for_rep_range(
            exercise_id, athlete_id, best_set["reps"]
        )
        
        if not pr_data:
            return {
                "is_pr": False,
                "diff_kg": None,
                "weeks_since": None,
                "pr_trend": "unknown"
            }
        
        pr_weight = pr_data["weight"]
        current_weight = best_set["weight"]
        diff_kg = current_weight - pr_weight
        
        # Check if this is a new PR (handled in detect_and_update_prs)
        is_pr = current_weight > pr_weight
        
        # Calculate weeks since PR
        weeks_since = None
        if pr_data["date"]:
            # Handle timezone-naive dates from database
            pr_date = pr_data["date"]
            if pr_date.tzinfo is None:
                pr_date = pr_date.replace(tzinfo=timezone.utc)
            weeks_since = (datetime.now(timezone.utc) - pr_date).days / 7
        
        # Determine trend
        if is_pr:
            pr_trend = "improving"
        elif diff_kg >= -2.5:  # Within 2.5kg of PR
            pr_trend = "maintaining"
        elif diff_kg >= -5.0:  # 2.5-5kg below PR
            pr_trend = "slight_regression"
        else:  # More than 5kg below PR
            pr_trend = "regressing"
        
        return {
            "is_pr": is_pr,
            "diff_kg": round(diff_kg, 1),
            "weeks_since": round(weeks_since, 1) if weeks_since else None,
            "pr_trend": pr_trend,
            "pr_weight": pr_weight,
            "pr_reps": pr_data["reps"]
        }

