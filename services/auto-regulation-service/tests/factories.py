"""
Test factories for creating test data.

Provides factory functions to generate realistic test data for models,
reducing boilerplate in tests and improving maintainability.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session

from app.models import (
    Athlete, WorkoutPlan, WorkoutDay, WorkoutDayExercise,
    WorkoutSession, ExerciseSet, RecoveryMetrics
)
from app.utils.constants import (
    Gender, TrainingExperience, TrainingType, PeriodizationModel,
    TrainingPhase
)
from tests.fake_exercise_service import FAKE


class AthleteFactory:
    """Factory for creating Athlete test instances."""
    
    @staticmethod
    def create(
        db: Session,
        age: int = 25,
        gender: Gender = Gender.MALE,
        training_experience: TrainingExperience = TrainingExperience.INTERMEDIATE,
        rpe_calibration_factor: float = 1.0,
        **kwargs
    ) -> Athlete:
        """
        Create an Athlete instance.
        
        Args:
            db: Database session
            age: Athlete age
            gender: Gender enum
            training_experience: Training experience level
            rpe_calibration_factor: RPE calibration factor
            **kwargs: Additional fields to set
            
        Returns:
            Created Athlete instance
        """
        athlete = Athlete(
            age=age,
            gender=gender,
            training_experience=training_experience,
            rpe_calibration_factor=rpe_calibration_factor,
            **kwargs
        )
        db.add(athlete)
        db.flush()
        return athlete
    
    @staticmethod
    def create_beginner(db: Session, **kwargs) -> Athlete:
        """Create a beginner athlete."""
        return AthleteFactory.create(
            db,
            age=20,
            training_experience=TrainingExperience.BEGINNER,
            **kwargs
        )
    
    @staticmethod
    def create_advanced(db: Session, **kwargs) -> Athlete:
        """Create an advanced athlete."""
        return AthleteFactory.create(
            db,
            age=30,
            training_experience=TrainingExperience.ADVANCED,
            **kwargs
        )


class ExerciseFactory:
    """
    Factory for registering exercises in the fake exercise-service.

    Exercises now live in exercise-service and are read over gRPC, so this no
    longer writes to the local DB. It registers an exercise in the in-memory
    fake (returned by the patched ExerciseClient) and returns the protobuf
    Exercise, whose ``.id`` callers use for ExerciseSet / WorkoutDayExercise.
    The ``db`` argument is accepted for call-site compatibility and ignored.
    """

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
        """
        Register an exercise. ``muscles`` is a list of (muscle_name, value)
        tuples where value is a role string or an activation percentage.
        """
        if muscles is None:
            muscles = [("mid_chest", 90)]
        return FAKE.add_exercise(
            name=name,
            muscles=muscles,
            exercise_type=exercise_type,
            intensity_category=intensity_category,
            movement_pattern=movement_pattern or "",
            complexity_score=complexity_score,
            injury_risk_level=injury_risk_level,
            joint_stress_areas=joint_stress_areas,
        )

    @staticmethod
    def create_compound(db: Optional[Session] = None, name: str = "Bench Press",
                        muscles: Optional[List[tuple]] = None, **kwargs):
        """Create a compound exercise with a typical activation pattern."""
        if muscles is None:
            muscles = [("mid_chest", 90), ("anterior_delt", 60), ("triceps", 50)]
        kwargs.setdefault("movement_pattern", "push")
        return ExerciseFactory.create(
            db, name=name, muscles=muscles, exercise_type="compound",
            complexity_score=1.2, injury_risk_level=0.5, **kwargs,
        )

    @staticmethod
    def create_isolation(db: Optional[Session] = None, name: str = "Bicep Curl",
                         muscles: Optional[List[tuple]] = None, **kwargs):
        """Create an isolation exercise with a typical activation pattern."""
        if muscles is None:
            muscles = [("biceps", 95), ("forearms", 30)]
        kwargs.setdefault("movement_pattern", "pull")
        return ExerciseFactory.create(
            db, name=name, muscles=muscles, exercise_type="isolation",
            complexity_score=0.7, injury_risk_level=0.2, **kwargs,
        )


class WorkoutPlanFactory:
    """Factory for creating WorkoutPlan test instances."""
    
    @staticmethod
    def create(
        db: Session,
        athlete_id: int,
        name: str = "Test Plan",
        training_type: TrainingType = TrainingType.HYPERTROPHY,
        periodization_model: PeriodizationModel = PeriodizationModel.LINEAR,
        frequency: int = 3,
        duration_weeks: int = 12,
        start_date: Optional[datetime] = None,
        **kwargs
    ) -> WorkoutPlan:
        """
        Create a WorkoutPlan instance.
        
        Args:
            db: Database session
            athlete_id: Athlete ID
            name: Plan name
            training_type: Training type enum
            periodization_model: Periodization model enum
            frequency: Workouts per week
            duration_weeks: Total program length in weeks
            start_date: Plan start date (defaults to 30 days ago)
            **kwargs: Additional fields to set
            
        Returns:
            Created WorkoutPlan instance
        """
        if start_date is None:
            start_date = datetime.now(timezone.utc) - timedelta(days=30)
        
        plan = WorkoutPlan(
            athlete_id=athlete_id,
            name=name,
            training_type=training_type,
            periodization_model=periodization_model,
            frequency=frequency,
            duration_weeks=duration_weeks,
            start_date=start_date,
            **kwargs
        )
        db.add(plan)
        db.flush()
        return plan


class WorkoutDayFactory:
    """Factory for creating WorkoutDay test instances."""
    
    @staticmethod
    def create(
        db: Session,
        workout_plan_id: int,
        name: str = "Test Day",
        day_of_week: int = 0,
        order_in_week: int = 1,
        **kwargs
    ) -> WorkoutDay:
        """
        Create a WorkoutDay instance.
        
        Args:
            db: Database session
            workout_plan_id: Workout plan ID
            name: Day name
            day_of_week: Day of week (0=Monday, 6=Sunday)
            order_in_week: Order in weekly split
            **kwargs: Additional fields to set
            
        Returns:
            Created WorkoutDay instance
        """
        workout_day = WorkoutDay(
            workout_plan_id=workout_plan_id,
            name=name,
            day_of_week=day_of_week,
            order_in_week=order_in_week,
            **kwargs
        )
        db.add(workout_day)
        db.flush()
        return workout_day


class WorkoutSessionFactory:
    """Factory for creating WorkoutSession test instances."""
    
    @staticmethod
    def create(
        db: Session,
        athlete_id: int,
        workout_day_id: int,
        session_date: Optional[datetime] = None,
        duration_minutes: Optional[int] = None,
        overall_rpe: Optional[float] = None,
        total_volume: Optional[float] = None,
        **kwargs
    ) -> WorkoutSession:
        """
        Create a WorkoutSession instance.
        
        Args:
            db: Database session
            athlete_id: Athlete ID
            workout_day_id: Workout day ID
            session_date: Session date (defaults to now)
            duration_minutes: Session duration in minutes
            overall_rpe: Overall RPE for session
            total_volume: Total volume lifted (kg)
            **kwargs: Additional fields to set
            
        Returns:
            Created WorkoutSession instance
        """
        if session_date is None:
            session_date = datetime.now(timezone.utc)
        
        session = WorkoutSession(
            athlete_id=athlete_id,
            workout_day_id=workout_day_id,
            session_date=session_date,
            duration_minutes=duration_minutes,
            overall_rpe=overall_rpe,
            total_volume=total_volume,
            **kwargs
        )
        db.add(session)
        db.flush()
        return session
    
    @staticmethod
    def create_with_sets(
        db: Session,
        athlete_id: int,
        workout_day_id: int,
        exercise_id: int,
        sets_data: Optional[List[Dict[str, Any]]] = None,
        session_date: Optional[datetime] = None,
        **kwargs
    ) -> WorkoutSession:
        """
        Create a WorkoutSession with exercise sets.
        
        Args:
            db: Database session
            athlete_id: Athlete ID
            workout_day_id: Workout day ID
            exercise_id: Exercise ID for sets
            sets_data: List of set data dicts with weight, reps, rpe
            session_date: Session date
            **kwargs: Additional session fields
            
        Returns:
            Created WorkoutSession with sets
        """
        session = WorkoutSessionFactory.create(
            db, athlete_id, workout_day_id, session_date, **kwargs
        )
        
        if sets_data is None:
            sets_data = [
                {"weight": 100.0, "reps": 5, "rpe": 8.0},
                {"weight": 100.0, "reps": 5, "rpe": 8.5},
                {"weight": 100.0, "reps": 5, "rpe": 9.0},
            ]
        
        for idx, set_data in enumerate(sets_data, start=1):
            ExerciseSetFactory.create(
                db,
                workout_session_id=session.id,
                exercise_id=exercise_id,
                set_number=idx,
                **set_data
            )
        
        db.flush()
        return session


class ExerciseSetFactory:
    """Factory for creating ExerciseSet test instances."""
    
    @staticmethod
    def create(
        db: Session,
        workout_session_id: int,
        exercise_id: int,
        set_number: int = 1,
        weight: float = 100.0,
        reps: int = 5,
        rpe: Optional[float] = 8.0,
        **kwargs
    ) -> ExerciseSet:
        """
        Create an ExerciseSet instance.
        
        Args:
            db: Database session
            workout_session_id: Workout session ID
            exercise_id: Exercise ID
            set_number: Set number (1-based)
            weight: Weight in kg
            reps: Number of reps
            rpe: RPE value
            **kwargs: Additional fields to set
            
        Returns:
            Created ExerciseSet instance
        """
        exercise_set = ExerciseSet(
            workout_session_id=workout_session_id,
            exercise_id=exercise_id,
            set_number=set_number,
            weight=weight,
            reps=reps,
            rpe=rpe,
            **kwargs
        )
        db.add(exercise_set)
        db.flush()
        return exercise_set


class RecoveryMetricsFactory:
    """Factory for creating RecoveryMetrics test instances."""
    
    @staticmethod
    def create(
        db: Session,
        athlete_id: int,
        date: Optional[datetime] = None,
        sleep_quality: Optional[str] = "good",
        sleep_hours: Optional[float] = 7.5,
        overall_soreness: Optional[int] = 3,
        stress_level: Optional[int] = 4,
        energy_level: Optional[int] = 7,
        **kwargs
    ) -> RecoveryMetrics:
        """
        Create a RecoveryMetrics instance.
        
        Args:
            db: Database session
            athlete_id: Athlete ID
            date: Metrics date (defaults to today)
            sleep_quality: Sleep quality ("excellent", "good", "fair", "poor")
            sleep_hours: Hours of sleep
            overall_soreness: Soreness level (1-10)
            stress_level: Stress level (1-10)
            energy_level: Energy level (1-10)
            **kwargs: Additional fields to set
            
        Returns:
            Created RecoveryMetrics instance
        """
        if date is None:
            date = datetime.now(timezone.utc)
        
        recovery = RecoveryMetrics(
            athlete_id=athlete_id,
            date=date,
            sleep_quality=sleep_quality,
            sleep_hours=sleep_hours,
            overall_soreness=overall_soreness,
            stress_level=stress_level,
            energy_level=energy_level,
            **kwargs
        )
        db.add(recovery)
        db.flush()
        return recovery

