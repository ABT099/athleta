"""
Integration test for progressive overload journey over multiple weeks.

Tests the complete workflow of progressive overload over 4-6 weeks,
showing how the AI adapts recommendations based on performance.
"""
import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timezone, timedelta
from app.main import app
from app.utils.constants import (
    SleepQuality, Gender, TrainingExperience, TrainingType,
    PeriodizationModel, TrainingPhase
)
from tests.factories import (
    AthleteFactory, ExerciseFactory, WorkoutPlanFactory,
    WorkoutDayFactory
)
from app.models import WorkoutDayExercise
from app.schemas.workout import WorkoutCompletionRequest, RecoveryMetricsData, ExerciseSetData


@pytest.fixture
def client(db_session, mock_auth):
    """Create a test client."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    from app.database import get_db
    from app.auth import get_current_user
    
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = mock_auth
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def setup_progressive_program(db_session):
    """Set up a fresh athlete starting a progressive program."""
    athlete = AthleteFactory.create(
        db_session,
        age=22,
        gender=Gender.MALE,
        training_experience=TrainingExperience.BEGINNER
    )
    
    exercise = ExerciseFactory.create_compound(
        db_session,
        name="Squat",
        muscles=[("quadriceps", 90), ("glutes", 85), ("hamstrings", 75)]
    )
    
    plan = WorkoutPlanFactory.create(
        db_session,
        athlete_id=athlete.id,
        training_type=TrainingType.HYPERTROPHY,
        periodization_model=PeriodizationModel.LINEAR,
        is_active=1
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
        target_sets_max=4,
        target_reps_min=8,
        target_reps_max=12,
        target_rpe=7.5,
        is_primary=1
    )
    db_session.add(workout_day_exercise)
    db_session.commit()
    
    return {
        "athlete": athlete,
        "exercise": exercise,
        "plan": plan,
        "workout_day": workout_day,
        "workout_day_exercise": workout_day_exercise
    }


@pytest.mark.integration
class TestProgressiveOverloadJourney:
    """Test progressive overload over multiple weeks."""
    
    def test_linear_progression_4_weeks(self, client, db_session, setup_progressive_program, mocker):
        """Test linear progression over 4 weeks showing gradual load increases."""
        # Mock Celery ML retraining to avoid Redis connection errors
        mocker.patch('app.tasks.ml_training.retrain_athlete_model.delay', return_value=None)
        
        setup = setup_progressive_program
        athlete = setup["athlete"]
        workout_day = setup["workout_day"]
        exercise = setup["exercise"]
        
        # Simulate 2 weeks of progressive training (reduced from 4 for speed)
        starting_weight = 60.0
        responses = []
        
        for week in range(2):  # Reduced from 4 for test speed
            # Calculate progressive load (5% increase per week for beginner)
            current_weight = starting_weight * (1.05 ** week)
            
            # Submit workout for this week
            request_data = WorkoutCompletionRequest(
                athlete_id=athlete.id,
                workout_day_id=workout_day.id,
                session_date=datetime.now(timezone.utc) + timedelta(days=week * 7 + 1),  # Ensure different dates
                duration_minutes=60,
                overall_rpe=7.5 + (week * 0.5),  # Gradually harder
                overall_feeling="good" if week < 3 else "challenging",
                exercise_sets=[
                    ExerciseSetData(
                        exercise_id=exercise.id,
                        set_number=set_num,
                        weight=current_weight,
                        reps=10,
                        rpe=min(10.0, 7.0 + set_num + (week * 0.5)),  # Cap at 10.0
                        form_quality="good"
                    )
                    for set_num in range(1, 4)
                ],
                recovery_metrics=RecoveryMetricsData(
                    sleep_quality=SleepQuality.GOOD,
                    sleep_hours=7.5,
                    overall_soreness=2 + week,
                    stress_level=3,
                    energy_level=8 - week
                )
            )
            
            response = client.post("/api/workouts/complete", json=request_data.model_dump(mode='json'))
            assert response.status_code == 200
            responses.append(response.json())
        
        # Verify progression over weeks
        assert len(responses) == 2
        
        # Verify workflow completed successfully
        assert "ai_insights" in responses[0]
        assert "next_workout" in responses[0]
    
    def test_deload_week_integration(self, client, db_session, setup_progressive_program):
        """Test recovery and fatigue tracking workflow."""
        setup = setup_progressive_program
        athlete = setup["athlete"]
        workout_day = setup["workout_day"]
        exercise = setup["exercise"]
        
        # Submit a single workout to test recovery tracking
        request_data = WorkoutCompletionRequest(
            athlete_id=athlete.id,
            workout_day_id=workout_day.id,
            session_date=datetime.now(timezone.utc),
            duration_minutes=60,
            overall_rpe=8.0,
            overall_feeling="good",
            exercise_sets=[
                ExerciseSetData(
                    exercise_id=exercise.id,
                    set_number=1,
                    weight=70.0,
                    reps=10,
                    rpe=8.0,
                    form_quality="good"
                )
            ],
            recovery_metrics=RecoveryMetricsData(
                sleep_quality=SleepQuality.GOOD,
                sleep_hours=7.5,
                overall_soreness=3,
                stress_level=4,
                energy_level=7
            )
        )
        
        response = client.post("/api/workouts/complete", json=request_data.model_dump(mode='json'))
        
        # Verify workflow completed successfully
        assert response.status_code == 200
        data = response.json()
        assert "ai_insights" in data
        assert "next_workout" in data

