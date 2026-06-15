"""
Personal Record (PR) detection.

PRs are api-owned. Detection stays an auto-regulation computation: it compares the
completed sets (from the Analysis Context) against the athlete's current PRs (also
in the context, pushed by api) and *returns* the new records. api persists them —
this service performs no database writes.
"""
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone

from app.clients.api_client import ExercisePersonalRecordDTO, ExerciseSetDTO
from app.modules.analysis import AnalysisContext
from app.shared.calculations import TrainingCalculations


class PRTrackerService:
    """Detects rep-max and volume PRs from a completed session's sets."""

    # Rep ranges for PR detection (inclusive)
    REP_RANGES = {
        1: (1, 1),      # 1RM
        3: (2, 3),      # 3RM
        5: (4, 5),      # 5RM
        8: (6, 8),      # 8RM
        10: (9, 10),    # 10RM
        12: (11, 12),   # 12RM
    }

    def __init__(self):
        self.calc = TrainingCalculations()

    def detect_prs(self, ctx: AnalysisContext) -> Dict:
        """
        Detect PRs from the completed session in the context.

        Returns ``{"achievements": [...], "updates": [...]}`` where each update
        describes a new PR for api to persist. No database writes happen here.
        """
        exercise_sets: Dict[int, List[ExerciseSetDTO]] = {}
        for set_record in ctx.sets:
            exercise_sets.setdefault(set_record.exercise_id, []).append(set_record)

        session_date = ctx.session.session_date
        achievements: List[str] = []
        updates: List[Dict] = []

        for exercise_id, sets_list in exercise_sets.items():
            pr = ctx.pr_for(exercise_id)  # current PRs (DTO) or None
            rep_max_updates = self._check_rep_max_prs(exercise_id, pr, sets_list, session_date)
            volume_updates = self._check_volume_prs(exercise_id, pr, sets_list, session_date)
            updates.extend(rep_max_updates)
            updates.extend(volume_updates)
            for update in rep_max_updates + volume_updates:
                if update.get("is_new_pr"):
                    achievements.append(self._format_achievement(update))

        return {"achievements": achievements, "updates": updates}

    @staticmethod
    def _rep_max_weight(pr: Optional[ExercisePersonalRecordDTO], rep_max: int) -> Optional[float]:
        if pr is None:
            return None
        return {
            1: pr.one_rep_max, 3: pr.three_rep_max, 5: pr.five_rep_max,
            8: pr.eight_rep_max, 10: pr.ten_rep_max, 12: pr.twelve_rep_max,
        }.get(rep_max)

    @staticmethod
    def _rep_max_date(pr: Optional[ExercisePersonalRecordDTO], rep_max: int) -> Optional[datetime]:
        if pr is None:
            return None
        return {
            1: pr.one_rm_date, 3: pr.three_rm_date, 5: pr.five_rm_date,
            8: pr.eight_rm_date, 10: pr.ten_rm_date, 12: pr.twelve_rm_date,
        }.get(rep_max)

    def _check_rep_max_prs(
        self,
        exercise_id: int,
        pr: Optional[ExercisePersonalRecordDTO],
        sets: List[ExerciseSetDTO],
        session_date: datetime,
    ) -> List[Dict]:
        """Check for rep-max PRs (1RM, 3RM, 5RM, ...)."""
        updates = []
        for rep_max, (min_reps, max_reps) in self.REP_RANGES.items():
            matching_sets = [s for s in sets if min_reps <= s.reps <= max_reps]
            if not matching_sets:
                continue
            best_set = max(matching_sets, key=lambda s: s.weight)
            current_weight = self._rep_max_weight(pr, rep_max)
            if current_weight is None or best_set.weight > current_weight:
                updates.append({
                    "exercise_id": exercise_id,
                    "pr_type": f"{rep_max}RM",
                    "rep_max": rep_max,
                    "old_value": current_weight,
                    "new_value": best_set.weight,
                    "improvement": best_set.weight - (current_weight or 0),
                    "reps": best_set.reps,
                    "date": session_date,
                    "is_new_pr": True,
                })
        return updates

    def _check_volume_prs(
        self,
        exercise_id: int,
        pr: Optional[ExercisePersonalRecordDTO],
        sets: List[ExerciseSetDTO],
        session_date: datetime,
    ) -> List[Dict]:
        """Check for volume PRs (total volume, total reps)."""
        updates = []
        total_volume = sum(s.weight * s.reps for s in sets)
        total_reps = sum(s.reps for s in sets)

        current_volume = pr.max_volume_session if pr else None
        if current_volume is None or total_volume > current_volume:
            updates.append({
                "exercise_id": exercise_id,
                "pr_type": "volume",
                "old_value": current_volume or 0,
                "new_value": total_volume,
                "improvement": total_volume - (current_volume or 0),
                "date": session_date,
                "is_new_pr": True,
            })

        current_reps = pr.max_total_reps if pr else None
        if current_reps is None or total_reps > current_reps:
            updates.append({
                "exercise_id": exercise_id,
                "pr_type": "total_reps",
                "old_value": current_reps or 0,
                "new_value": total_reps,
                "improvement": total_reps - (current_reps or 0),
                "date": session_date,
                "is_new_pr": True,
            })
        return updates

    def _format_achievement(self, update: Dict) -> str:
        """Format a PR achievement message."""
        pr_type = update["pr_type"]
        new_value = update["new_value"]
        improvement = update["improvement"]
        if pr_type == "volume":
            return f"🎉 Volume PR! {new_value:.1f}kg total (up {improvement:.1f}kg)"
        elif pr_type == "total_reps":
            return f"🎉 Rep PR! {int(new_value)} total reps (up {int(improvement)})"
        return f"🎉 New {pr_type} PR! {new_value:.1f}kg (up {improvement:.1f}kg)"

    def get_pr_for_rep_range(
        self,
        pr: Optional[ExercisePersonalRecordDTO],
        target_reps: float,
    ) -> Optional[Dict]:
        """Get the most relevant PR for a target rep range, from the context's PR DTO."""
        if pr is None:
            return None
        target_rep_int = int(round(target_reps))
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

        weight = self._rep_max_weight(pr, rep_max)
        if weight is None:
            return None
        return {
            "weight": weight,
            "reps": rep_max,
            "date": self._rep_max_date(pr, rep_max),
            "rep_max": rep_max,
        }

    def compare_to_pr(
        self,
        pr: Optional[ExercisePersonalRecordDTO],
        best_set: Dict,
    ) -> Dict:
        """Compare a set to the relevant PR (from the context's PR DTO)."""
        pr_data = self.get_pr_for_rep_range(pr, best_set["reps"])
        if not pr_data:
            return {"is_pr": False, "diff_kg": None, "weeks_since": None, "pr_trend": "unknown"}

        pr_weight = pr_data["weight"]
        current_weight = best_set["weight"]
        diff_kg = current_weight - pr_weight
        is_pr = current_weight > pr_weight

        weeks_since = None
        if pr_data["date"]:
            pr_date = pr_data["date"]
            if pr_date.tzinfo is None:
                pr_date = pr_date.replace(tzinfo=timezone.utc)
            weeks_since = (datetime.now(timezone.utc) - pr_date).days / 7

        if is_pr:
            pr_trend = "improving"
        elif diff_kg >= -2.5:
            pr_trend = "maintaining"
        elif diff_kg >= -5.0:
            pr_trend = "slight_regression"
        else:
            pr_trend = "regressing"

        return {
            "is_pr": is_pr,
            "diff_kg": round(diff_kg, 1),
            "weeks_since": round(weeks_since, 1) if weeks_since else None,
            "pr_trend": pr_trend,
            "pr_weight": pr_weight,
            "pr_reps": pr_data["reps"],
        }

    def calculate_training_percentage(
        self, week_number: int, phase: str, is_deload: bool = False
    ) -> float:
        """Calculate training percentage of PR based on week and phase (pure)."""
        from app.utils.constants import (
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
        week_adjustment = min(PR_WEEK_ADJUSTMENT_CAP, (week_number - 1) * PR_WEEK_ADJUSTMENT_RATE)
        return min(PR_MAX_PERCENTAGE, base_pct + week_adjustment)
