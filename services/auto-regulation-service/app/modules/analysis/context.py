"""
The Analysis Context — auto-regulation's load-once view of the data needed to
analyse one completed workout, and the historical window needed to retrain ML.

Why this exists (the deepening): the engine used to re-query api-owned data
(athlete, sessions, sets, recovery) from ~68 scattered call sites. Here that data
is assembled ONCE — api-owned fields are *pushed in the request* (zero fetches on
the synchronous completion path); historical signal is read locally from
auto-regulation's OWN denormalised tables (`performance_trends`, progression). The
engine then computes as a pure function over an immutable context. Delete this
module and the 68 scattered reads reappear across the call sites.

`db` here is always auto-regulation's OWN session (algo tables only). api-owned
data never touches the DB in this service.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.clients.api_client import (
    AthleteDTO,
    ExercisePersonalRecordDTO,
    PlanDTO,
    RecoveryMetricsDTO,
    WorkoutSessionDTO,
)
from app.models import (
    AthleteRPECalibration,
    ExerciseProgressionTracking,
    FormQualityTrend,
    PerformanceTrend,
    PlanEntry,
)

# How many past sessions of local trend history to load (covers ACWR's 28-day
# chronic window and the ML sequential lookback).
DEFAULT_TREND_WINDOW = 28


class AnalysisRequest(BaseModel):
    """
    Everything api pushes to ``POST /analysis/sessions`` so the synchronous
    completion path makes zero outbound api calls. All fields are api-owned data
    api already has in hand (it just persisted the session).
    """

    athlete: AthleteDTO
    plan: Optional[PlanDTO] = None
    session: WorkoutSessionDTO
    recovery: Optional[RecoveryMetricsDTO] = None
    # The athlete's current PRs for the exercises in this session, so PR detection
    # can compare without a fetch. Empty when the athlete has none yet.
    personal_records: List[ExercisePersonalRecordDTO] = []


@dataclass(frozen=True)
class AnalysisContext:
    """
    Immutable, load-once input for analysing one completion. The engine and every
    service read from this; the algo ``db`` session is used only for *writes*.
    """

    # --- api-owned (pushed in the request; zero fetches) ---
    athlete: AthleteDTO
    plan: Optional[PlanDTO]
    session: WorkoutSessionDTO
    recovery: Optional[RecoveryMetricsDTO]
    personal_records: Dict[int, ExercisePersonalRecordDTO]  # by exercise_id

    # --- algo-owned (read locally from auto-regulation's own DB) ---
    current_plan_entry: Optional[PlanEntry]
    recent_performance_trends: List[PerformanceTrend]  # newest-first
    exercise_progressions: Dict[int, ExerciseProgressionTracking]  # latest per exercise
    rpe_calibrations: Dict[int, AthleteRPECalibration]  # by exercise_id
    form_trends: Dict[int, FormQualityTrend]  # latest per exercise

    @property
    def athlete_id(self) -> int:
        return self.athlete.id

    @property
    def sets(self):
        """The completed sets (api-owned, from the request)."""
        return self.session.sets

    @property
    def exercise_ids(self) -> List[int]:
        return list({s.exercise_id for s in self.session.sets})

    def pr_for(self, exercise_id: int) -> Optional[ExercisePersonalRecordDTO]:
        return self.personal_records.get(exercise_id)


@dataclass(frozen=True)
class TrainingHistory:
    """
    Immutable historical window for ML retraining. Assembled once per job from a
    few bulk api reads (athlete + recovery history + current PRs + active-plan
    focus areas) plus local trend/progression history. ML feature engineering
    computes over this instead of querying.
    """

    athlete: AthleteDTO
    recovery_history: List[RecoveryMetricsDTO]  # newest-first
    performance_trends: List[PerformanceTrend]  # newest-first, full window
    exercise_progressions: List[ExerciseProgressionTracking]
    personal_records: Dict[int, "ExercisePersonalRecordDTO"]  # by exercise_id
    focus_areas: List[str]

    @property
    def athlete_id(self) -> int:
        return self.athlete.id


def _latest_by_exercise(rows) -> Dict[int, object]:
    """Keep the most recent row per exercise_id (rows already newest-first)."""
    out: Dict[int, object] = {}
    for row in rows:
        out.setdefault(row.exercise_id, row)
    return out


def build_analysis_context(
    request: AnalysisRequest,
    db: Session,
    trend_window: int = DEFAULT_TREND_WINDOW,
) -> AnalysisContext:
    """Assemble a context from the pushed request payload + local algo reads."""
    athlete_id = request.athlete.id
    exercise_ids = list({s.exercise_id for s in request.session.sets})

    plan_entry = None
    if request.plan is not None:
        plan_entry = (
            db.query(PlanEntry)
            .filter(PlanEntry.workout_plan_id == request.plan.id)
            .order_by(PlanEntry.week_number.desc())
            .first()
        )

    recent_trends = (
        db.query(PerformanceTrend)
        .filter(PerformanceTrend.athlete_id == athlete_id)
        .order_by(PerformanceTrend.session_date.desc())
        .limit(trend_window)
        .all()
    )

    progressions: Dict[int, ExerciseProgressionTracking] = {}
    rpe_calibrations: Dict[int, AthleteRPECalibration] = {}
    form_trends: Dict[int, FormQualityTrend] = {}
    if exercise_ids:
        progressions = _latest_by_exercise(
            db.query(ExerciseProgressionTracking)
            .filter(
                ExerciseProgressionTracking.athlete_id == athlete_id,
                ExerciseProgressionTracking.exercise_id.in_(exercise_ids),
            )
            .order_by(ExerciseProgressionTracking.session_date.desc())
            .all()
        )
        rpe_calibrations = _latest_by_exercise(
            db.query(AthleteRPECalibration)
            .filter(
                AthleteRPECalibration.athlete_id == athlete_id,
                AthleteRPECalibration.exercise_id.in_(exercise_ids),
            )
            .order_by(AthleteRPECalibration.session_date.desc())
            .all()
        )
        form_trends = _latest_by_exercise(
            db.query(FormQualityTrend)
            .filter(
                FormQualityTrend.athlete_id == athlete_id,
                FormQualityTrend.exercise_id.in_(exercise_ids),
            )
            .order_by(FormQualityTrend.date.desc())
            .all()
        )

    return AnalysisContext(
        athlete=request.athlete,
        plan=request.plan,
        session=request.session,
        recovery=request.recovery,
        personal_records={pr.exercise_id: pr for pr in request.personal_records},
        current_plan_entry=plan_entry,
        recent_performance_trends=recent_trends,
        exercise_progressions=progressions,
        rpe_calibrations=rpe_calibrations,
        form_trends=form_trends,
    )


def build_training_history(
    athlete: AthleteDTO,
    recovery_history: List[RecoveryMetricsDTO],
    db: Session,
    personal_records: Optional[Dict[int, "ExercisePersonalRecordDTO"]] = None,
    focus_areas: Optional[List[str]] = None,
) -> TrainingHistory:
    """
    Assemble the ML retraining window. ``athlete``, ``recovery_history``,
    ``personal_records`` and ``focus_areas`` are the bulk api reads (fetched by the
    caller via ApiClient); trends/progression are read locally.
    """
    trends = (
        db.query(PerformanceTrend)
        .filter(PerformanceTrend.athlete_id == athlete.id)
        .order_by(PerformanceTrend.session_date.desc())
        .all()
    )
    progressions = (
        db.query(ExerciseProgressionTracking)
        .filter(ExerciseProgressionTracking.athlete_id == athlete.id)
        .order_by(ExerciseProgressionTracking.session_date.desc())
        .all()
    )
    return TrainingHistory(
        athlete=athlete,
        recovery_history=recovery_history,
        performance_trends=trends,
        exercise_progressions=progressions,
        personal_records=personal_records or {},
        focus_areas=focus_areas or [],
    )
