"""
Pytest configuration and fixtures.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base


@pytest.fixture(scope="function")
def db_session():
    """
    Create a test database session.
    
    Uses in-memory SQLite for testing.
    """
    # Create in-memory SQLite database for testing
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    
    TestingSessionLocal = sessionmaker(bind=engine)
    session = TestingSessionLocal()
    
    yield session
    
    session.close()
    Base.metadata.drop_all(engine)


@pytest.fixture
def sample_athlete_data():
    """Sample athlete data for testing."""
    return {
        "name": "Test Athlete",
        "email": "test@example.com",
        "age": 25,
        "gender": "male",
        "training_experience": "intermediate",
        "injury_history": None
    }


@pytest.fixture
def sample_workout_data():
    """Sample workout completion data for testing."""
    return {
        "athlete_id": 1,
        "workout_day_id": 1,
        "session_date": "2024-01-01T10:00:00",
        "duration_minutes": 60,
        "exercise_sets": [
            {
                "exercise_id": 1,
                "set_number": 1,
                "weight": 100.0,
                "reps": 5,
                "rpe": 8.0,
                "rir": 2,
                "form_quality": "good"
            }
        ],
        "recovery_metrics": {
            "sleep_quality": "good",
            "sleep_hours": 7.5,
            "overall_soreness": 3,
            "stress_level": 4,
            "energy_level": 7
        },
        "overall_rpe": 8.0
    }

