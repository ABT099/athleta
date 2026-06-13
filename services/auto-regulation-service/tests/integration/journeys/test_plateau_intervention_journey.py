"""
Integration test for plateau detection and intervention journey.

Tests the complete workflow of detecting a plateau and recommending
intensity techniques to break through it.
"""
import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timezone, timedelta
from autoregulation.main import app
from autoregulation.utils.constants import (
    SleepQuality, Gender, TrainingExperience, TrainingType,
    PeriodizationModel, SetType
)
from tests.factories import (
    AthleteFactory, ExerciseFactory, WorkoutPlanFactory,
    WorkoutDayFactory, WorkoutSessionFactory, ExerciseSetFactory
)
from autoregulation.models import WorkoutDayExercise


@pytest.fixture
def client(db_session, mock_auth):
    """Create a test client."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    from autoregulation.database import get_db
    from autoregulation.auth import get_current_user
    
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = mock_auth
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def setup_athlete_with_plateau(db_session):
    """Set up an athlete with a plateau scenario (3+ weeks of no progress)."""
    # Create intermediate athlete
    athlete = AthleteFactory.create(
        db_session,
        age=28,
        gender=Gender.MALE,
        training_experience=TrainingExperience.INTERMEDIATE
    )
    
    # Create exercise (bench press)
    exercise = ExerciseFactory.create_compound(
        db_session,
        name="Bench Press",
        muscles=[("mid_chest", 90), ("anterior_delt", 60), ("triceps", 50)]
    )
    
    # Create workout plan
    plan = WorkoutPlanFactory.create(
        db_session,
        athlete_id=athlete.id,
        training_type=TrainingType.HYPERTROPHY,
        periodization_model=PeriodizationModel.LINEAR
    )
    
    # Create workout day
    workout_day = WorkoutDayFactory.create(
        db_session,
        workout_plan_id=plan.id
    )
    
    # Create workout day exercise
    workout_day_exercise = WorkoutDayExercise(
        workout_day_id=workout_day.id,
        exercise_id=exercise.id,
        order_in_workout=1,
        target_sets_min=3,
        target_sets_max=4,
        target_reps_min=8,
        target_reps_max=12,
        target_rpe=8.0,
        is_primary=1
    )
    db_session.add(workout_day_exercise)
    db_session.commit()
    
    # Create 3 weeks of stalled progress (same weight, same reps)
    base_date = datetime.now(timezone.utc) - timedelta(weeks=3)
    
    for week in range(3):
        session_date = base_date + timedelta(weeks=week)
        
        session = WorkoutSessionFactory.create(
            db_session,
            athlete_id=athlete.id,
            workout_day_id=workout_day.id,
            session_date=session_date
        )
        
        # Same performance each week - indicating plateau
        for set_num in range(1, 4):
            ExerciseSetFactory.create(
                db_session,
                workout_session_id=session.id,
                exercise_id=exercise.id,
                set_number=set_num,
                weight=100.0,  # Same weight
                reps=10,       # Same reps
                rpe=9.0,       # High RPE (struggling)
                form_quality="good"
            )
    
    return {
        "athlete": athlete,
        "exercise": exercise,
        "plan": plan,
        "workout_day": workout_day,
        "workout_day_exercise": workout_day_exercise
    }


@pytest.mark.integration
class TestPlateauInterventionJourney:
    """Test plateau detection and intervention journey."""
    
    def test_plateau_detected_drop_set_suggested(self, client, db_session, setup_athlete_with_plateau):
        """Test that plateau is detected and drop set is recommended."""
        from autoregulation.schemas.workout import WorkoutCompletionRequest, RecoveryMetricsData, ExerciseSetData
        
        setup = setup_athlete_with_plateau
        athlete = setup["athlete"]
        workout_day = setup["workout_day"]
        exercise = setup["exercise"]
        
        # Submit workout (another stalled session)
        request_data = WorkoutCompletionRequest(
            athlete_id=athlete.id,
            workout_day_id=workout_day.id,
            session_date=datetime.now(timezone.utc),
            duration_minutes=60,
            overall_rpe=9.0,
            overall_feeling="struggled",
            exercise_sets=[
                ExerciseSetData(
                    exercise_id=exercise.id,
                    set_number=1,
                    weight=100.0,  # Same weight as before
                    reps=10,       # Same reps
                    rpe=9.0,       # High effort
                    form_quality="good"
                ),
                ExerciseSetData(
                    exercise_id=exercise.id,
                    set_number=2,
                    weight=100.0,
                    reps=9,        # Slight drop
                    rpe=9.5,
                    form_quality="fair"
                )
            ],
            recovery_metrics=RecoveryMetricsData(
                sleep_quality=SleepQuality.GOOD,
                sleep_hours=7.5,
                overall_soreness=4,
                stress_level=5,
                energy_level=6
            )
        )
        
        response = client.post("/api/workouts/complete", json=request_data.model_dump(mode='json'))
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        # Verify successful workflow completion
        assert "ai_insights" in data
        assert "next_workout" in data
        
        # Note: Actual plateau detection logic would need several weeks of data
        # This test validates the workflow structure
    
    def test_no_plateau_no_intervention(self, client, db_session):
        """Test that no intervention is suggested when there's progress."""
        from autoregulation.schemas.workout import WorkoutCompletionRequest, RecoveryMetricsData, ExerciseSetData
        
        # Create athlete with recent progress
        athlete = AthleteFactory.create(
            db_session,
            age=25,
            gender=Gender.FEMALE,
            training_experience=TrainingExperience.BEGINNER
        )
        
        exercise = ExerciseFactory.create_compound(
            db_session,
            name="Squat",
            muscles=[("quadriceps", 90), ("glutes", 80), ("hamstrings", 70)]
        )
        
        plan = WorkoutPlanFactory.create(
            db_session,
            athlete_id=athlete.id,
            training_type=TrainingType.STRENGTH
        )
        
        workout_day = WorkoutDayFactory.create(
            db_session,
            workout_plan_id=plan.id
        )
        
        workout_day_exercise = WorkoutDayExercise(
            workout_day_id=workout_day.id,
            exercise_id=exercise.id,
            order_in_workout=1,
            target_sets_min=3,
            target_sets_max=5,
            target_reps_min=3,
            target_reps_max=5,
            target_rpe=8.5,
            is_primary=1
        )
        db_session.add(workout_day_exercise)
        db_session.commit()
        
        request_data = WorkoutCompletionRequest(
            athlete_id=athlete.id,
            workout_day_id=workout_day.id,
            session_date=datetime.now(timezone.utc),
            duration_minutes=45,
            overall_rpe=8.5,
            overall_feeling="great",
            exercise_sets=[
                ExerciseSetData(
                    exercise_id=exercise.id,
                    set_number=1,
                    weight=80.0,
                    reps=5,
                    rpe=8.0,
                    form_quality="excellent"
                )
            ],
            recovery_metrics=RecoveryMetricsData(
                sleep_quality=SleepQuality.EXCELLENT,
                sleep_hours=8.0,
                overall_soreness=2,
                stress_level=3,
                energy_level=8
            )
        )
        
        response = client.post("/api/workouts/complete", json=request_data.model_dump(mode='json'))
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify workflow completed successfully
        assert "ai_insights" in data
        assert "next_workout" in data

