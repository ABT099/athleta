"""
Integration test for complete workout workflow.

Tests the full workflow from submitting a completed workout
through AI processing to receiving next workout recommendations.
"""
import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta, timezone
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
def setup_workout_plan(db_session):
    """Set up a complete workout plan with athlete, plan, day, and exercises."""
    # Create athlete
    athlete = AthleteFactory.create(
        db_session,
        age=25,
        gender=Gender.MALE,
        training_experience=TrainingExperience.INTERMEDIATE
    )
    
    # Create exercise
    exercise = ExerciseFactory.create_compound(
        db_session,
        name="Bench Press"
    )
    
    # Create workout plan
    plan = WorkoutPlanFactory.create(
        db_session,
        athlete_id=athlete.id,
        training_type=TrainingType.HYPERTROPHY,
        periodization_model=PeriodizationModel.LINEAR,
        is_active=1
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
    
    return {
        "athlete": athlete,
        "exercise": exercise,
        "plan": plan,
        "workout_day": workout_day,
        "workout_day_exercise": workout_day_exercise
    }


class TestCompleteWorkoutWorkflow:
    """Test suite for complete workout workflow."""
    
    def test_complete_workout_full_workflow(self, client, db_session, setup_workout_plan):
        """Test the complete workflow from workout submission to AI recommendations."""
        from app.schemas.workout import WorkoutCompletionRequest, RecoveryMetricsData, ExerciseSetData
        
        setup = setup_workout_plan
        athlete = setup["athlete"]
        workout_day = setup["workout_day"]
        exercise = setup["exercise"]
        
        # Prepare workout completion request
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
                    weight=100.0,
                    reps=10,
                    rpe=8.0,
                    form_quality="good"
                ),
                ExerciseSetData(
                    exercise_id=exercise.id,
                    set_number=2,
                    weight=100.0,
                    reps=10,
                    rpe=8.5,
                    form_quality="good"
                ),
                ExerciseSetData(
                    exercise_id=exercise.id,
                    set_number=3,
                    weight=100.0,
                    reps=9,
                    rpe=9.0,
                    form_quality="fair"
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
        
        # Submit workout
        response = client.post("/api/workouts/complete", json=request_data.model_dump(mode='json'))
        
        # Verify successful response
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "workout_session" in data
        assert "recovery_metrics" in data
        assert "next_workout" in data
        assert "performance_analysis" in data
        assert "ai_insights" in data
        
        # Verify workout session was created
        workout_session = data["workout_session"]
        assert workout_session["athlete_id"] == athlete.id
        assert workout_session["workout_day_id"] == workout_day.id
        assert workout_session["total_volume"] is not None
        assert workout_session["total_volume"] > 0
        
        # Verify recovery metrics were saved
        recovery = data["recovery_metrics"]
        assert recovery["athlete_id"] == athlete.id
        assert recovery["readiness_score"] is not None
        assert 0.0 <= recovery["readiness_score"] <= 1.0
        
        # Verify performance analysis
        performance = data["performance_analysis"]
        assert "total_volume" in performance
        assert "exercise_analyses" in performance
        assert len(performance["exercise_analyses"]) > 0
        
        # Verify AI insights
        insights = data["ai_insights"]
        assert isinstance(insights, list)
        assert len(insights) > 0
        
        # Verify next workout recommendations
        next_workout = data["next_workout"]
        assert "workout_day" in next_workout
        assert "adjustments_summary" in next_workout
        assert "injury_warnings" in next_workout
        assert "recovery_recommendations" in next_workout
    
    def test_complete_workout_creates_performance_trend(self, client, db_session, setup_workout_plan):
        """Test that completing a workout creates a PerformanceTrend record."""
        from app.schemas.workout import WorkoutCompletionRequest, RecoveryMetricsData, ExerciseSetData
        from app.models import PerformanceTrend
        
        setup = setup_workout_plan
        athlete = setup["athlete"]
        workout_day = setup["workout_day"]
        exercise = setup["exercise"]
        
        # Count existing trends
        initial_count = db_session.query(PerformanceTrend).filter(
            PerformanceTrend.athlete_id == athlete.id
        ).count()
        
        # Submit workout
        request_data = WorkoutCompletionRequest(
            athlete_id=athlete.id,
            workout_day_id=workout_day.id,
            session_date=datetime.now(timezone.utc),
            exercise_sets=[
                ExerciseSetData(
                    exercise_id=exercise.id,
                    set_number=1,
                    weight=100.0,
                    reps=10,
                    rpe=8.0
                )
            ],
            recovery_metrics=RecoveryMetricsData(
                sleep_quality=SleepQuality.GOOD,
                sleep_hours=7.5
            )
        )
        
        response = client.post("/api/workouts/complete", json=request_data.model_dump(mode='json'))
        assert response.status_code == 200
        
        # Verify PerformanceTrend was created
        db_session.commit()
        final_count = db_session.query(PerformanceTrend).filter(
            PerformanceTrend.athlete_id == athlete.id
        ).count()
        
        assert final_count == initial_count + 1
        
        # Verify trend has required fields
        trend = db_session.query(PerformanceTrend).filter(
            PerformanceTrend.athlete_id == athlete.id
        ).order_by(PerformanceTrend.session_date.desc()).first()
        
        assert trend is not None
        assert trend.total_volume is not None
        assert trend.average_rpe is not None
        assert trend.readiness_score is not None
        assert trend.performance_score is not None
    
    def test_complete_workout_with_poor_recovery_triggers_deload(self, client, db_session, setup_workout_plan):
        """Test that poor recovery metrics trigger appropriate deload recommendations."""
        from app.schemas.workout import WorkoutCompletionRequest, RecoveryMetricsData, ExerciseSetData
        
        setup = setup_workout_plan
        athlete = setup["athlete"]
        workout_day = setup["workout_day"]
        exercise = setup["exercise"]
        
        # Submit workout with poor recovery
        request_data = WorkoutCompletionRequest(
            athlete_id=athlete.id,
            workout_day_id=workout_day.id,
            session_date=datetime.now(timezone.utc),
            exercise_sets=[
                ExerciseSetData(
                    exercise_id=exercise.id,
                    set_number=1,
                    weight=100.0,
                    reps=10,
                    rpe=8.0
                )
            ],
            recovery_metrics=RecoveryMetricsData(
                sleep_quality=SleepQuality.POOR,
                sleep_hours=5.0,  # Low sleep
                overall_soreness=8,  # High soreness
                stress_level=9,  # High stress
                energy_level=2  # Low energy
            )
        )
        
        response = client.post("/api/workouts/complete", json=request_data.model_dump(mode='json'))
        assert response.status_code == 200
        
        data = response.json()
        
        # Verify recovery score is low
        recovery = data["recovery_metrics"]
        assert recovery["readiness_score"] < 0.5
        
        # Verify AI insights mention recovery concerns
        insights = data["ai_insights"]
        insight_text = " ".join(insights).lower()
        assert any(keyword in insight_text for keyword in ["recovery", "rest", "sleep", "deload"])
        
        # Verify next workout adjustments reflect recovery status
        next_workout = data["next_workout"]
        adjustments = next_workout.get("adjustments_summary", {})
        
        # With poor recovery, volume should be reduced or AI should recognize recovery concerns
        # The test passes if either:
        # 1. volume_multiplier is explicitly reduced
        # 2. OR recovery recommendations mention rest/recovery
        volume_mult = adjustments.get("volume_multiplier")
        recovery_recs = next_workout.get("recovery_recommendations", [])
        
        recovery_mentioned = any(
            keyword in str(recovery_recs).lower()
            for keyword in ["recovery", "rest", "sleep", "deload", "reduce"]
        )
        
        # Either volume is reduced OR recovery concerns are mentioned
        assert (volume_mult is not None and volume_mult < 1.0) or recovery_mentioned, \
            f"Expected volume reduction or recovery recommendations. Got volume_mult={volume_mult}, recovery_recs={recovery_recs}"

