"""
Pytest configuration and fixtures.
"""
import os
import pytest
import json
from datetime import datetime
from unittest.mock import Mock, MagicMock
from sqlalchemy import create_engine, event, String, Text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects import sqlite

# Set test database URL before importing app modules
# Use a named in-memory database with shared cache so all connections share the same database
os.environ["DATABASE_URL"] = "sqlite:///file::memory:?cache=shared&uri=true"

from app.database import Base
from app.utils.constants import (
    Gender, TrainingExperience, TrainingType, PeriodizationModel, TrainingPhase
)


# Custom type to handle PostgreSQL ARRAY in SQLite
class SQLiteArray(String):
    """Custom type to serialize/deserialize arrays for SQLite."""
    
    def bind_processor(self, dialect):
        def process(value):
            if value is None:
                return None
            if isinstance(value, list):
                return json.dumps(value)
            return value
        return process
    
    def result_processor(self, dialect, coltype):
        def process(value):
            if value is None:
                return []
            if isinstance(value, str):
                try:
                    return json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    return []
            return value
        return process


# Custom type to handle JSON in SQLite
class SQLiteJSON(Text):
    """Custom type to serialize/deserialize JSON for SQLite."""
    
    def bind_processor(self, dialect):
        def process(value):
            if value is None:
                return None
            if isinstance(value, (list, dict)):
                return json.dumps(value)
            return value
        return process
    
    def result_processor(self, dialect, coltype):
        def process(value):
            if value is None:
                return None
            if isinstance(value, str):
                try:
                    return json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    return value
            return value
        return process


@pytest.fixture(scope="function")
def db_session():
    """
    Create a test database session.
    
    Uses in-memory SQLite for testing with PostgreSQL ARRAY compatibility.
    Each test gets a fresh in-memory database that is automatically cleaned up.
    """
    # Patch ARRAY type for SQLite compatibility
    from sqlalchemy.dialects.postgresql import ARRAY
    
    # Override ARRAY compilation for SQLite
    @event.listens_for(Base.metadata, "before_create")
    def receive_before_create(target, connection, **kw):
        """Handle ARRAY and JSON types in SQLite."""
        if connection.dialect.name == 'sqlite':
            for table in Base.metadata.tables.values():
                for column in table.columns:
                    if hasattr(column.type, '__class__'):
                        type_name = column.type.__class__.__name__
                        if type_name == 'ARRAY':
                            # Replace ARRAY with SQLiteJSON for SQLite (arrays are lists)
                            column.type = SQLiteJSON()
                        elif type_name == 'JSON':
                            # Replace JSON with SQLiteJSON for SQLite
                            column.type = SQLiteJSON()
    
    # Create in-memory SQLite database for testing
    # Using file::memory:?cache=shared&uri=true creates a shared in-memory database
    # that all connections can access (unlike :memory: which is per-connection)
    # check_same_thread=False allows the connection to be used across threads
    # (required for FastAPI TestClient which runs in different threads)
    engine = create_engine(
        "sqlite:///file::memory:?cache=shared&uri=true",
        echo=False,
        connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    
    TestingSessionLocal = sessionmaker(bind=engine)
    session = TestingSessionLocal()
    
    try:
        yield session
        # Commit any pending changes before cleanup
        session.commit()
    except Exception:
        # Rollback on error
        session.rollback()
        raise
    finally:
        # Clean up
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def freeze_time():
    """
    Fixture for freezing time in tests.
    
    Usage:
        def test_something(freeze_time):
            with freeze_time("2024-01-01"):
                # Test code with frozen time
                pass
    """
    try:
        from freezegun import freeze_time as ft
        return ft
    except ImportError:
        pytest.skip("freezegun not installed")


@pytest.fixture
def mock_ml_services(mocker):
    """
    Mock ML services to avoid TensorFlow/LightGBM dependencies in non-ML tests.
    
    Returns:
        Dict with mocked ML service objects
    """
    mocks = {
        'ml_predictor': mocker.patch('app.services.progressive_overload_engine.ML_AVAILABLE', False),
        'model_manager': mocker.patch('app.ml.model_manager.ModelManager'),
        'workout_predictor': mocker.patch('app.ml.workout_predictor.WorkoutPredictorService'),
    }
    return mocks


@pytest.fixture
def sample_athlete(db_session):
    """Create a sample athlete for testing."""
    from tests.factories import AthleteFactory
    return AthleteFactory.create(db_session)


@pytest.fixture
def sample_exercise(db_session):
    """Create a sample exercise for testing."""
    from tests.factories import ExerciseFactory
    return ExerciseFactory.create_compound(db_session, name="Bench Press")


@pytest.fixture
def sample_workout_plan(db_session, sample_athlete):
    """Create a sample workout plan for testing."""
    from tests.factories import WorkoutPlanFactory
    return WorkoutPlanFactory.create(db_session, athlete_id=sample_athlete.id)


@pytest.fixture
def sample_workout_day(db_session, sample_workout_plan):
    """Create a sample workout day for testing."""
    from tests.factories import WorkoutDayFactory
    return WorkoutDayFactory.create(db_session, workout_plan_id=sample_workout_plan.id)


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


# Parametrization helpers
TRAINING_TYPES = list(TrainingType)
PERIODIZATION_MODELS = list(PeriodizationModel)
TRAINING_PHASES = list(TrainingPhase)
GENDERS = list(Gender)
TRAINING_EXPERIENCES = list(TrainingExperience)


@pytest.fixture(params=TRAINING_TYPES)
def training_type(request):
    """Parametrized fixture for training types."""
    return request.param


@pytest.fixture(params=PERIODIZATION_MODELS)
def periodization_model(request):
    """Parametrized fixture for periodization models."""
    return request.param


@pytest.fixture(params=TRAINING_PHASES)
def training_phase(request):
    """Parametrized fixture for training phases."""
    return request.param

