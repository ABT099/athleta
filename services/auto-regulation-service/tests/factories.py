"""
Test factories.

api-owned data (athlete, plan, days, exercises, sessions, sets, recovery, PRs) is
built as DTOs — the same shapes api pushes in the analyze request. Algo data
(performance trends, …) is seeded into auto-regulation's own test DB. Exercises
are registered in the fake exercise-service.

The api-owned factories accept an optional leading ``db`` argument (ignored) for
call-site compatibility with the old DB-backed factories.
"""
import itertools
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List

from sqlalchemy.orm import Session

from app.clients.api_client import (
    AthleteDTO, PlanDTO, WorkoutDayDTO, WorkoutDayExerciseDTO,
    WorkoutSessionDTO, ExerciseSetDTO, RecoveryMetricsDTO, ExercisePersonalRecordDTO,
)
from app.modules.analysis import AnalysisRequest
from app.models import PerformanceTrend
from app.utils.constants import (
    Gender, TrainingExperience, TrainingType, PeriodizationModel,
)
from tests.fake_exercise_service import FAKE

_ids = itertools.count(1)


def _next_id() -> int:
    return next(_ids)


class AthleteFactory:
    @staticmethod
    def create(
        db=None,
        age: int = 25,
        gender: Gender = Gender.MALE,
        training_experience: TrainingExperience = TrainingExperience.INTERMEDIATE,
        rpe_calibration_factor: float = 1.0,
        body_weight_kg: float = 80.0,
        id: Optional[int] = None,
        **kwargs,
    ) -> AthleteDTO:
        return AthleteDTO(
            id=id or _next_id(),
            age=age,
            gender=gender,
            training_experience=training_experience,
            rpe_calibration_factor=rpe_calibration_factor,
            body_weight_kg=body_weight_kg,
        )

    @staticmethod
    def create_beginner(db=None, **kwargs) -> AthleteDTO:
        return AthleteFactory.create(age=20, training_experience=TrainingExperience.BEGINNER, **kwargs)

    @staticmethod
    def create_advanced(db=None, **kwargs) -> AthleteDTO:
        return AthleteFactory.create(age=30, training_experience=TrainingExperience.ADVANCED, **kwargs)


class ExerciseFactory:
    """Registers an exercise in the fake exercise-service (read over gRPC)."""

    @staticmethod
    def create(
        db: Optional[Session] = None,
        name: str = "Test Exercise",
        muscles: Optional[List[tuple]] = None,
        exercise_type: str = "compound",
        complexity_score: float = 1.0,
        injury_risk_level: float = 0.5,
        movement_pattern: Optional[str] = None,
        intensity_category: Optional[str] = None,
        joint_stress_areas: Optional[List[str]] = None,
        **kwargs,
    ):
        if muscles is None:
            muscles = [("mid_chest", 90)]
        return FAKE.add_exercise(
            name=name, muscles=muscles, exercise_type=exercise_type,
            intensity_category=intensity_category, movement_pattern=movement_pattern or "",
            complexity_score=complexity_score, injury_risk_level=injury_risk_level,
            joint_stress_areas=joint_stress_areas,
        )

    @staticmethod
    def create_compound(db=None, name: str = "Bench Press", muscles=None, **kwargs):
        if muscles is None:
            muscles = [("mid_chest", 90), ("anterior_delt", 60), ("triceps", 50)]
        kwargs.setdefault("movement_pattern", "push")
        return ExerciseFactory.create(name=name, muscles=muscles, exercise_type="compound",
                                      complexity_score=1.2, injury_risk_level=0.5, **kwargs)

    @staticmethod
    def create_isolation(db=None, name: str = "Bicep Curl", muscles=None, **kwargs):
        if muscles is None:
            muscles = [("biceps", 95), ("forearms", 30)]
        kwargs.setdefault("movement_pattern", "pull")
        return ExerciseFactory.create(name=name, muscles=muscles, exercise_type="isolation",
                                      complexity_score=0.7, injury_risk_level=0.2, **kwargs)


class WorkoutDayExerciseFactory:
    @staticmethod
    def create(
        db=None,
        exercise_id: int = 1,
        workout_day_id: int = 1,
        order_in_workout: int = 1,
        target_sets_min: int = 3,
        target_sets_max: int = 4,
        target_reps_min: int = 5,
        target_reps_max: int = 8,
        target_rpe: float = 8.0,
        is_primary: bool = True,
        id: Optional[int] = None,
        **kwargs,
    ) -> WorkoutDayExerciseDTO:
        return WorkoutDayExerciseDTO(
            id=id or _next_id(), workout_day_id=workout_day_id, exercise_id=exercise_id,
            order_in_workout=order_in_workout, target_sets_min=target_sets_min,
            target_sets_max=target_sets_max, target_reps_min=target_reps_min,
            target_reps_max=target_reps_max, target_rpe=target_rpe, is_primary=is_primary,
            **kwargs,
        )


class WorkoutDayFactory:
    @staticmethod
    def create(
        db=None,
        workout_plan_id: int = 1,
        name: str = "Test Day",
        day_of_week: int = 0,
        order_in_week: int = 1,
        exercises: Optional[List[WorkoutDayExerciseDTO]] = None,
        id: Optional[int] = None,
        **kwargs,
    ) -> WorkoutDayDTO:
        day_id = id or _next_id()
        return WorkoutDayDTO(
            id=day_id, workout_plan_id=workout_plan_id, name=name,
            day_of_week=day_of_week, order_in_week=order_in_week,
            exercises=exercises or [],
        )


class WorkoutPlanFactory:
    @staticmethod
    def create(
        db=None,
        athlete_id: int = 1,
        name: str = "Test Plan",
        training_type: TrainingType = TrainingType.HYPERTROPHY,
        periodization_model: PeriodizationModel = PeriodizationModel.LINEAR,
        frequency: int = 3,
        duration_weeks: int = 12,
        start_date: Optional[datetime] = None,
        focus_areas: Optional[List[str]] = None,
        days: Optional[List[WorkoutDayDTO]] = None,
        id: Optional[int] = None,
        **kwargs,
    ) -> PlanDTO:
        return PlanDTO(
            id=id or _next_id(), athlete_id=athlete_id, name=name,
            training_type=training_type, periodization_model=periodization_model,
            focus_areas=focus_areas, frequency=frequency, duration_weeks=duration_weeks,
            start_date=start_date or (datetime.now(timezone.utc) - timedelta(days=30)),
            is_active=True, days=days or [],
        )


class ExerciseSetFactory:
    @staticmethod
    def create(
        db=None,
        exercise_id: int = 1,
        workout_session_id: int = 1,
        set_number: int = 1,
        weight: float = 100.0,
        reps: int = 5,
        rpe: Optional[float] = 8.0,
        form_quality: Optional[str] = "good",
        rir: Optional[int] = 2,
        id: Optional[int] = None,
        **kwargs,
    ) -> ExerciseSetDTO:
        return ExerciseSetDTO(
            id=id or _next_id(), workout_session_id=workout_session_id, exercise_id=exercise_id,
            set_number=set_number, weight=weight, reps=reps, rpe=rpe,
            form_quality=form_quality, rir=rir, **kwargs,
        )


class WorkoutSessionFactory:
    @staticmethod
    def create(
        db=None,
        athlete_id: int = 1,
        workout_day_id: int = 1,
        session_date: Optional[datetime] = None,
        duration_minutes: Optional[int] = 60,
        overall_rpe: Optional[float] = 8.0,
        total_volume: Optional[float] = None,
        sets: Optional[List[ExerciseSetDTO]] = None,
        id: Optional[int] = None,
        **kwargs,
    ) -> WorkoutSessionDTO:
        return WorkoutSessionDTO(
            id=id or _next_id(), athlete_id=athlete_id, workout_day_id=workout_day_id,
            session_date=session_date or datetime.now(timezone.utc),
            duration_minutes=duration_minutes, overall_rpe=overall_rpe,
            total_volume=total_volume, sets=sets or [],
        )

    @staticmethod
    def create_with_sets(
        db=None,
        athlete_id: int = 1,
        workout_day_id: int = 1,
        exercise_id: int = 1,
        sets_data: Optional[List[Dict[str, Any]]] = None,
        session_date: Optional[datetime] = None,
        **kwargs,
    ) -> WorkoutSessionDTO:
        session_id = _next_id()
        if sets_data is None:
            sets_data = [
                {"weight": 100.0, "reps": 5, "rpe": 8.0},
                {"weight": 100.0, "reps": 5, "rpe": 8.5},
                {"weight": 100.0, "reps": 5, "rpe": 9.0},
            ]
        sets = [
            ExerciseSetFactory.create(
                exercise_id=exercise_id, workout_session_id=session_id, set_number=i, **sd
            )
            for i, sd in enumerate(sets_data, start=1)
        ]
        total_volume = sum(s.weight * s.reps for s in sets)
        return WorkoutSessionFactory.create(
            id=session_id, athlete_id=athlete_id, workout_day_id=workout_day_id,
            session_date=session_date, total_volume=total_volume, sets=sets, **kwargs,
        )


class RecoveryMetricsFactory:
    @staticmethod
    def create(
        db=None,
        athlete_id: int = 1,
        date: Optional[datetime] = None,
        sleep_quality: str = "good",
        sleep_hours: Optional[float] = 7.5,
        overall_soreness: Optional[int] = 3,
        stress_level: Optional[int] = 4,
        energy_level: Optional[int] = 7,
        id: Optional[int] = None,
        **kwargs,
    ) -> RecoveryMetricsDTO:
        return RecoveryMetricsDTO(
            id=id or _next_id(), athlete_id=athlete_id,
            date=date or datetime.now(timezone.utc), sleep_quality=sleep_quality,
            sleep_hours=sleep_hours, overall_soreness=overall_soreness,
            stress_level=stress_level, energy_level=energy_level, **kwargs,
        )


class PersonalRecordFactory:
    @staticmethod
    def create(db=None, exercise_id: int = 1, **kwargs) -> ExercisePersonalRecordDTO:
        return ExercisePersonalRecordDTO(exercise_id=exercise_id, **kwargs)


class AnalysisRequestFactory:
    """Build a full AnalysisRequest (what api pushes to /analysis/sessions)."""

    @staticmethod
    def create(
        athlete: Optional[AthleteDTO] = None,
        plan: Optional[PlanDTO] = None,
        session: Optional[WorkoutSessionDTO] = None,
        recovery: Optional[RecoveryMetricsDTO] = None,
        personal_records: Optional[List[ExercisePersonalRecordDTO]] = None,
    ) -> AnalysisRequest:
        athlete = athlete or AthleteFactory.create()
        if session is None:
            session = WorkoutSessionFactory.create(athlete_id=athlete.id)
        if recovery is None:
            recovery = RecoveryMetricsFactory.create(athlete_id=athlete.id, date=session.session_date)
        return AnalysisRequest(
            athlete=athlete, plan=plan, session=session, recovery=recovery,
            personal_records=personal_records or [],
        )


class PerformanceTrendFactory:
    """Seed a local performance_trend row (auto-regulation's own DB)."""

    @staticmethod
    def create(
        db: Session,
        athlete_id: int = 1,
        workout_session_id: Optional[int] = None,
        session_date: Optional[datetime] = None,
        total_volume: float = 5000.0,
        average_intensity: float = 0.75,
        average_rpe: float = 8.0,
        readiness_score: float = 0.7,
        performance_score: float = 0.8,
        fatigue_index: float = 0.3,
        volume_load: float = 3750.0,
        acwr: Optional[float] = 1.0,
        cns_load: Optional[float] = 2.0,
        duration_minutes: Optional[int] = 60,
        **kwargs,
    ) -> PerformanceTrend:
        trend = PerformanceTrend(
            athlete_id=athlete_id,
            workout_session_id=workout_session_id or _next_id(),
            session_date=session_date or datetime.now(timezone.utc),
            total_volume=total_volume, average_intensity=average_intensity,
            average_rpe=average_rpe, readiness_score=readiness_score,
            performance_score=performance_score, fatigue_index=fatigue_index,
            volume_load=volume_load, acwr=acwr, cns_load=cns_load,
            duration_minutes=duration_minutes, deload_triggered=False, **kwargs,
        )
        db.add(trend)
        db.flush()
        return trend
