"""
Workout rotation helper.

Determines the next workout in rotation from the plan's day order. The plan is
api-owned and arrives in the Analysis Context, so this is pure logic over the
plan's days — no database access.
"""
from typing import Optional

from app.clients.api_client import PlanDTO


class WorkoutScheduler:
    """Pure rotation logic over an api-owned plan's days."""

    @staticmethod
    def get_next_workout_in_rotation(
        completed_workout_day_id: int,
        plan: Optional[PlanDTO],
    ) -> Optional[int]:
        """
        Get the next workout day id in rotation (wraps around), or None.

        Args:
            completed_workout_day_id: the workout day that was just completed
            plan: the athlete's active plan (with its days), from the context
        """
        if plan is None or not plan.days:
            return None

        sorted_days = sorted(plan.days, key=lambda d: d.order_in_week)

        current_idx = next(
            (i for i, d in enumerate(sorted_days) if d.id == completed_workout_day_id),
            None,
        )
        if current_idx is None:
            # Completed day not in this plan — start from the first day.
            return sorted_days[0].id

        next_idx = (current_idx + 1) % len(sorted_days)
        return sorted_days[next_idx].id
