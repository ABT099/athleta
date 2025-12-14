"""
Test factories for creating test data.

Provides factory functions to generate realistic test data for models,
reducing boilerplate in tests and improving maintainability.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session

from app.models import (
    Athlete, Exercise, WorkoutPlan, WorkoutDay, WorkoutDayExercise,
    WorkoutSession, ExerciseSet, RecoveryMetrics, MuscleGroupModel, ExerciseMuscle
)
from app.utils.constants import (
    Gender, TrainingExperience, TrainingType, PeriodizationModel,
    TrainingPhase
)


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
    """Factory for creating Exercise test instances."""
    
    @staticmethod
    def create(
        db: Session,
        name: str = "Test Exercise",
        muscles: List[tuple[str, int]] = None,
        exercise_type: str = "compound",
        complexity_score: float = 1.0,
        injury_risk_level: float = 0.5,
        movement_pattern: Optional[str] = None,
        **kwargs
    ) -> Exercise:
        """
        Create an Exercise instance with muscle activations.
        
        Args:
            db: Database session
            name: Exercise name
            muscles: List of (muscle_name, activation_percent) tuples
            exercise_type: "compound" or "isolation"
            complexity_score: Complexity score (0.0-2.0)
            injury_risk_level: Injury risk level (0.0-1.0)
            movement_pattern: Movement pattern (squat, hinge, push, pull, etc.)
            **kwargs: Additional fields to set
            
        Returns:
            Created Exercise instance with muscle links
        """
        if muscles is None:
            # Default to mid_chest with high activation
            muscles = [("mid_chest", 90)]
        
        exercise = Exercise(
            name=name,
            exercise_type=exercise_type,
            complexity_score=complexity_score,
            injury_risk_level=injury_risk_level,
            movement_pattern=movement_pattern,
            **kwargs
        )
        db.add(exercise)
        db.flush()
        
        # Create muscle links
        for muscle_name, activation_percent in muscles:
            # Get or query muscle from database
            muscle = db.query(MuscleGroupModel).filter(
                MuscleGroupModel.name == muscle_name
            ).first()
            
            if muscle:
                link = ExerciseMuscle(
                    exercise_id=exercise.id,
                    muscle_group_id=muscle.id,
                    activation_percent=activation_percent
                )
                db.add(link)
            else:
                # Warn when muscle is not found to help catch typos and missing data
                import warnings
                warnings.warn(
                    f"Muscle '{muscle_name}' not found in database for exercise '{name}'. "
                    f"Muscle link will not be created. Check if muscle name is correct or if muscle groups are seeded.",
                    UserWarning
                )
        
        db.flush()
        return exercise
    
    @staticmethod
    def create_compound(
        db: Session,
        name: str = "Bench Press",
        muscles: List[tuple[str, int]] = None,
        **kwargs
    ) -> Exercise:
        """Create a compound exercise with typical activation pattern."""
        if muscles is None:
            # Default compound exercise: bench press pattern
            muscles = [
                ("mid_chest", 90),
                ("anterior_delt", 60),
                ("triceps", 50)
            ]
            
        # Set default movement pattern if not provided
        if "movement_pattern" not in kwargs:
            kwargs["movement_pattern"] = "push"
            
        return ExerciseFactory.create(
            db,
            name=name,
            muscles=muscles,
            exercise_type="compound",
            complexity_score=1.2,
            injury_risk_level=0.5,
            **kwargs
        )
    
    @staticmethod
    def create_isolation(
        db: Session,
        name: str = "Bicep Curl",
        muscles: List[tuple[str, int]] = None,
        **kwargs
    ) -> Exercise:
        """Create an isolation exercise with typical activation pattern."""
        if muscles is None:
            # Default isolation exercise: bicep curl pattern
            muscles = [
                ("biceps", 95),
                ("forearms", 30)
            ]
            
        # Set default movement pattern if not provided
        if "movement_pattern" not in kwargs:
            kwargs["movement_pattern"] = "pull"
            
        return ExerciseFactory.create(
            db,
            name=name,
            muscles=muscles,
            exercise_type="isolation",
            complexity_score=0.7,
            injury_risk_level=0.2,
            **kwargs
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
        target_muscle_groups: List[str] = None,
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
            target_muscle_groups: List of target muscle groups
            **kwargs: Additional fields to set
            
        Returns:
            Created WorkoutDay instance
        """
        if target_muscle_groups is None:
            target_muscle_groups = ["mid_chest"]
        
        workout_day = WorkoutDay(
            workout_plan_id=workout_plan_id,
            name=name,
            day_of_week=day_of_week,
            order_in_week=order_in_week,
            target_muscle_groups=target_muscle_groups,
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

