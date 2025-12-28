"""
Unit tests for workouts API endpoints.
"""
import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timezone
from app.main import app
from app.utils.constants import SleepQuality, Gender, TrainingExperience, TrainingType, PeriodizationModel
from tests.factories import (
    AthleteFactory, ExerciseFactory, WorkoutPlanFactory, 
    WorkoutDayFactory
)


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


class TestWorkoutsAPI:
    """Test suite for workouts API endpoints."""
    
    def test_complete_workout_athlete_not_found(self, client, db_session):
        """Test that completing workout with non-existent athlete returns 404."""
        from app.schemas.workout import WorkoutCompletionRequest, RecoveryMetricsData, ExerciseSetData
        
        request_data = WorkoutCompletionRequest(
            athlete_id=99999,  # Non-existent
            workout_day_id=1,
            session_date=datetime.now(timezone.utc),
            exercise_sets=[
                ExerciseSetData(
                    exercise_id=1,
                    set_number=1,
                    weight=100.0,
                    reps=5,
                    rpe=8.0
                )
            ],
            recovery_metrics=RecoveryMetricsData(
                sleep_quality=SleepQuality.GOOD,
                sleep_hours=7.5
            )
        )
        
        response = client.post("/api/workouts/complete", json=request_data.model_dump(mode='json'))
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    def test_complete_workout_workout_day_not_found(self, client, db_session):
        """Test that completing workout with non-existent workout day returns 404."""
        from app.schemas.workout import WorkoutCompletionRequest, RecoveryMetricsData, ExerciseSetData
        
        # Create athlete
        athlete = AthleteFactory.create(db_session)
        db_session.commit()
        
        request_data = WorkoutCompletionRequest(
            athlete_id=athlete.id,
            workout_day_id=99999,  # Non-existent
            session_date=datetime.now(timezone.utc),
            exercise_sets=[
                ExerciseSetData(
                    exercise_id=1,
                    set_number=1,
                    weight=100.0,
                    reps=5,
                    rpe=8.0
                )
            ],
            recovery_metrics=RecoveryMetricsData(
                sleep_quality=SleepQuality.GOOD,
                sleep_hours=7.5
            )
        )
        
        response = client.post("/api/workouts/complete", json=request_data.model_dump(mode='json'))
        assert response.status_code == 404
        assert "workout day" in response.json()["detail"].lower()
    
    def test_complete_workout_validation_errors(self, client, db_session):
        """Test that invalid request data returns validation errors."""
        # Test with missing required fields
        invalid_data = {
            "athlete_id": 1,
            # Missing workout_day_id, session_date, etc.
        }
        
        response = client.post("/api/workouts/complete", json=invalid_data)
        assert response.status_code == 422  # Validation error
    
    def test_complete_workout_invalid_rpe(self, client, db_session):
        """Test that RPE outside valid range (1-10) returns validation error."""
        from app.schemas.workout import WorkoutCompletionRequest, RecoveryMetricsData, ExerciseSetData
        
        athlete = AthleteFactory.create(db_session)
        db_session.commit()
        
        # RPE > 10 should fail validation
        request_data = {
            "athlete_id": athlete.id,
            "workout_day_id": 1,
            "session_date": datetime.now(timezone.utc).isoformat(),
            "exercise_sets": [
                {
                    "exercise_id": 1,
                    "set_number": 1,
                    "weight": 100.0,
                    "reps": 5,
                    "rpe": 11.0  # Invalid: > 10
                }
            ],
            "recovery_metrics": {
                "sleep_quality": "good",
                "sleep_hours": 7.5
            }
        }
        
        response = client.post("/api/workouts/complete", json=request_data)
        assert response.status_code == 422  # Validation error
    
    def test_get_athlete_analytics_athlete_not_found(self, client, db_session):
        """Test that getting analytics for non-existent athlete returns 404."""
        response = client.get("/api/athletes/99999/analytics")
        assert response.status_code == 404
    
    def test_get_athlete_analytics_no_data(self, client, db_session):
        """Test that getting analytics for athlete with no data returns empty result."""
        athlete = AthleteFactory.create(db_session)
        db_session.commit()
        
        response = client.get(f"/api/athletes/{athlete.id}/analytics")
        assert response.status_code == 200
        data = response.json()
        assert data["athlete_id"] == athlete.id
        assert "message" in data
        assert len(data.get("trends", [])) == 0

