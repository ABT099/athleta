"""
In-memory fake of the api service for tests.

Auto-regulation reads api-owned data (athletes, plans, sessions, sets, recovery)
over HTTP through ApiClient. Tests resolve that boundary through this fake: the
``fake_api_service`` autouse fixture (conftest) resets the registry and patches
ApiClient's methods to delegate here, returning the same DTOs the real client
would parse from api responses.
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from app.clients.api_client import (
    AthleteDTO,
    PlanDTO,
    RecoveryMetricsDTO,
    WorkoutSessionDTO,
)


class FakeApiService:
    """Mutable in-memory store mirroring ApiClient's read surface."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._athletes: Dict[int, AthleteDTO] = {}
        self._active_plans: Dict[int, PlanDTO] = {}
        self._sessions: Dict[int, WorkoutSessionDTO] = {}
        self._recovery: Dict[int, List[RecoveryMetricsDTO]] = {}

    # --- seeding -------------------------------------------------------------
    def add_athlete(self, athlete: AthleteDTO) -> AthleteDTO:
        self._athletes[athlete.id] = athlete
        return athlete

    def set_active_plan(self, plan: PlanDTO) -> PlanDTO:
        self._active_plans[plan.athlete_id] = plan
        return plan

    def add_session(self, session: WorkoutSessionDTO) -> WorkoutSessionDTO:
        self._sessions[session.id] = session
        return session

    def add_recovery(self, recovery: RecoveryMetricsDTO) -> RecoveryMetricsDTO:
        self._recovery.setdefault(recovery.athlete_id, []).append(recovery)
        return recovery

    # --- ApiClient surface ---------------------------------------------------
    def get_athlete(self, athlete_id: int) -> Optional[AthleteDTO]:
        return self._athletes.get(athlete_id)

    def get_active_plan(self, athlete_id: int) -> Optional[PlanDTO]:
        return self._active_plans.get(athlete_id)

    def get_workout_session(self, session_id: int) -> Optional[WorkoutSessionDTO]:
        return self._sessions.get(session_id)

    def list_recent_sessions(
        self,
        athlete_id: int,
        since: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> List[WorkoutSessionDTO]:
        rows = [s for s in self._sessions.values() if s.athlete_id == athlete_id]
        if since is not None:
            rows = [s for s in rows if s.session_date >= since]
        rows.sort(key=lambda s: s.session_date, reverse=True)
        return rows[:limit] if limit else rows

    def list_recovery_metrics(
        self,
        athlete_id: int,
        since: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> List[RecoveryMetricsDTO]:
        rows = list(self._recovery.get(athlete_id, []))
        if since is not None:
            rows = [r for r in rows if r.date >= since]
        rows.sort(key=lambda r: r.date, reverse=True)
        return rows[:limit] if limit else rows


# Module-level singleton, reset per test by the conftest fixture.
FAKE = FakeApiService()
