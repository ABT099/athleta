"""
HTTP client for the api service (NestJS).

The user/workout domain (athletes, workout plans, completed sessions, sets,
recovery metrics) is owned by the api service. Auto-regulation is a stateless
computation engine: it reads that data over HTTP through this client instead of
mapping api-owned tables with SQLAlchemy.

This mirrors the ExerciseClient seam — a context-managed, env-configured client
whose methods tests patch to an in-memory fake:

    with ApiClient() as api:
        athlete = api.get_athlete(athlete_id)
        plan = api.get_active_plan(athlete_id)
        session = api.get_workout_session(session_id)

Endpoints are the internal (service-to-service) surface under ``/internal`` and
authenticate with the shared ``SERVICE_TOKEN``. Calls are synchronous for now;
Phase 3 swaps the transport for ``httpx.AsyncClient`` behind the same interface.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

import httpx
from pydantic import BaseModel

from app.config import settings
from app.utils.constants import (
    Gender,
    PeriodizationModel,
    SleepQuality,
    TrainingExperience,
    TrainingType,
)

DEFAULT_TIMEOUT_SECONDS = 5.0
# Connection-level retries for transient failures (mirrors the gRPC retry intent).
DEFAULT_TRANSPORT_RETRIES = 3


# --- Data transfer objects ---------------------------------------------------
# Plain read models of api-owned data. References to api rows (athlete_id,
# exercise_id, workout_day_id, …) are soft integer references — there are no
# cross-service foreign keys.


class AthleteDTO(BaseModel):
    id: int
    age: int
    gender: Gender
    training_experience: TrainingExperience
    rpe_calibration_factor: float = 1.0
    body_weight_kg: Optional[float] = None


class WorkoutDayExerciseDTO(BaseModel):
    id: int
    workout_day_id: int
    exercise_id: int
    order_in_workout: int
    target_sets_min: int
    target_sets_max: int
    target_reps_min: int
    target_reps_max: int
    target_rpe: Optional[float] = None
    target_rir: Optional[int] = None
    rest_period_seconds: Optional[int] = None
    tempo: Optional[str] = None
    notes: Optional[str] = None
    is_primary: bool = True
    progression_scheme: Optional[str] = None
    warm_up_sets: int = 0
    set_type: str = "straight"
    rep_style: str = "normal"
    set_type_params: Optional[dict[str, Any]] = None
    rep_style_params: Optional[dict[str, Any]] = None


class WorkoutDayDTO(BaseModel):
    id: int
    workout_plan_id: int
    name: Optional[str] = None
    day_of_week: Optional[int] = None
    order_in_week: int
    exercises: List[WorkoutDayExerciseDTO] = []


class PlanDTO(BaseModel):
    id: int
    athlete_id: int
    name: Optional[str] = None
    training_type: TrainingType
    periodization_model: PeriodizationModel
    focus_areas: Optional[list[str]] = None
    frequency: int
    duration_weeks: int
    start_date: datetime
    end_date: Optional[datetime] = None
    is_active: bool = True
    days: List[WorkoutDayDTO] = []


class ExerciseSetDTO(BaseModel):
    id: int
    workout_session_id: int
    exercise_id: int
    set_number: int
    weight: float
    reps: int
    rpe: Optional[float] = None
    rir: Optional[int] = None
    form_quality: Optional[str] = None
    set_type_used: Optional[str] = None
    rep_style_used: Optional[str] = None
    technique_details: Optional[dict[str, Any]] = None
    notes: Optional[str] = None


class WorkoutSessionDTO(BaseModel):
    id: int
    athlete_id: int
    workout_day_id: int
    session_date: datetime
    duration_minutes: Optional[int] = None
    overall_rpe: Optional[float] = None
    overall_feeling: Optional[str] = None
    total_volume: Optional[float] = None
    estimated_fatigue: Optional[float] = None
    notes: Optional[str] = None
    sets: List[ExerciseSetDTO] = []


class ExercisePersonalRecordDTO(BaseModel):
    """An athlete's current PRs for one exercise (api-owned). Pushed in the analyze
    request so PR *detection* can compare against existing records without a fetch."""
    exercise_id: int
    one_rep_max: Optional[float] = None
    one_rm_date: Optional[datetime] = None
    three_rep_max: Optional[float] = None
    three_rm_date: Optional[datetime] = None
    five_rep_max: Optional[float] = None
    five_rm_date: Optional[datetime] = None
    eight_rep_max: Optional[float] = None
    eight_rm_date: Optional[datetime] = None
    ten_rep_max: Optional[float] = None
    ten_rm_date: Optional[datetime] = None
    twelve_rep_max: Optional[float] = None
    twelve_rm_date: Optional[datetime] = None
    max_volume_session: Optional[float] = None
    max_total_reps: Optional[int] = None
    total_pr_count: int = 0
    last_pr_date: Optional[datetime] = None


class RecoveryMetricsDTO(BaseModel):
    id: int
    athlete_id: int
    date: datetime
    sleep_quality: SleepQuality
    sleep_hours: Optional[float] = None
    overall_soreness: Optional[int] = None
    muscle_soreness: Optional[str] = None
    stress_level: Optional[int] = None
    energy_level: Optional[int] = None
    readiness_score: Optional[float] = None
    nutrition_adherence: Optional[str] = None
    hydration_level: Optional[str] = None
    notes: Optional[str] = None


# --- Client ------------------------------------------------------------------


class ApiClient:
    """
    Context-managed HTTP client for api-owned data.

    Opens an ``httpx.Client`` on ``__enter__`` and closes it on ``__exit__``;
    must be used inside a ``with`` block. Base URL and service token come from
    settings (``API_BASE_URL`` / ``SERVICE_TOKEN``). Read methods return ``None``
    / ``[]`` when the resource is absent (HTTP 404) and raise on other errors.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        token: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        self._base_url = (base_url or settings.API_BASE_URL).rstrip("/")
        self._token = token if token is not None else settings.SERVICE_TOKEN
        self._timeout = timeout
        # Injectable transport for tests (e.g. httpx.MockTransport); defaults to a
        # real transport with connection-level retries.
        self._transport = transport or httpx.HTTPTransport(
            retries=DEFAULT_TRANSPORT_RETRIES
        )
        self._client: Optional[httpx.Client] = None

    def __enter__(self) -> "ApiClient":
        headers = {"Accept": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        self._client = httpx.Client(
            base_url=self._base_url,
            headers=headers,
            timeout=self._timeout,
            transport=self._transport,
        )
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.close()
        return False

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def _client_or_raise(self) -> httpx.Client:
        if self._client is None:
            raise RuntimeError(
                "ApiClient must be used as a context manager "
                "(`with ApiClient() as api: ...`)"
            )
        return self._client

    def _get(self, path: str, **params: Any) -> Optional[Any]:
        """GET helper. Returns parsed JSON, or None on 404."""
        clean = {k: v for k, v in params.items() if v is not None}
        resp = self._client_or_raise().get(path, params=clean)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    def get_athlete(self, athlete_id: int) -> Optional[AthleteDTO]:
        data = self._get(f"/internal/athletes/{athlete_id}")
        return AthleteDTO.model_validate(data) if data is not None else None

    def get_active_plan(self, athlete_id: int) -> Optional[PlanDTO]:
        data = self._get(f"/internal/athletes/{athlete_id}/active-plan")
        return PlanDTO.model_validate(data) if data is not None else None

    def get_workout_session(self, session_id: int) -> Optional[WorkoutSessionDTO]:
        data = self._get(f"/internal/workout-sessions/{session_id}")
        return WorkoutSessionDTO.model_validate(data) if data is not None else None

    def list_recent_sessions(
        self,
        athlete_id: int,
        since: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> List[WorkoutSessionDTO]:
        data = self._get(
            f"/internal/athletes/{athlete_id}/workout-sessions",
            since=since.isoformat() if since else None,
            limit=limit,
        )
        return [WorkoutSessionDTO.model_validate(s) for s in (data or [])]

    def list_recovery_metrics(
        self,
        athlete_id: int,
        since: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> List[RecoveryMetricsDTO]:
        data = self._get(
            f"/internal/athletes/{athlete_id}/recovery-metrics",
            since=since.isoformat() if since else None,
            limit=limit,
        )
        return [RecoveryMetricsDTO.model_validate(r) for r in (data or [])]

    def list_personal_records(self, athlete_id: int) -> List[ExercisePersonalRecordDTO]:
        """All current PRs for an athlete (used by ML retraining)."""
        data = self._get(f"/internal/athletes/{athlete_id}/personal-records")
        return [ExercisePersonalRecordDTO.model_validate(r) for r in (data or [])]
