"""
Pytest configuration and fixtures.
"""
import os
import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer

# Set test environment BEFORE importing any app modules
# This ensures database.py uses PostgreSQL mode, not SQLite
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"  # Placeholder, will be overridden by container

from app.database import Base
from app.utils.constants import (
    Gender, TrainingExperience, TrainingType, PeriodizationModel, TrainingPhase
)


@pytest.fixture(autouse=True)
def fake_exercise_service(monkeypatch):
    """
    Reset the in-memory exercise-service and route every ExerciseClient call to
    it (no real channel). Autouse so all tests run the real service logic with
    the gRPC boundary faked. Tests register exercises via ExerciseFactory or by
    calling methods on the returned fake directly.
    """
    from app.clients.exercise_client import ExerciseClient
    from tests.fake_exercise_service import FAKE

    FAKE.reset()

    monkeypatch.setattr(ExerciseClient, "__init__", lambda self, *a, **k: None)
    monkeypatch.setattr(ExerciseClient, "__enter__", lambda self: self)
    monkeypatch.setattr(ExerciseClient, "__exit__", lambda self, *a: False)
    monkeypatch.setattr(
        ExerciseClient, "get_exercises",
        lambda self, ids: FAKE.get_exercises(ids),
    )
    monkeypatch.setattr(
        ExerciseClient, "get_muscles",
        lambda self, names=None: FAKE.get_muscles(names),
    )
    monkeypatch.setattr(
        ExerciseClient, "find_substitutions",
        lambda self, exercise_id, exclude_joints=None, exclude_ids=None, limit=5:
            FAKE.find_substitutions(exercise_id, exclude_joints, exclude_ids, limit),
    )
    return FAKE


@pytest.fixture(scope="session")
def postgres_container():
    """
    Create a PostgreSQL testcontainer for the entire test session.
    
    Uses the official PostgreSQL 18 image and persists across all tests
    for better performance. The container is automatically cleaned up
    after all tests complete.
    """
    with PostgresContainer("postgres:18-alpine", driver="psycopg2") as postgres:
        # Set the DATABASE_URL for all tests
        os.environ["DATABASE_URL"] = postgres.get_connection_url()
        yield postgres


@pytest.fixture(scope="session")
def redis_container():
    """
    Create a Redis testcontainer for the entire test session.
    
    Used for Celery task queue testing. The container is automatically
    cleaned up after all tests complete.
    """
    with RedisContainer("redis:8-alpine") as redis:
        # Set the REDIS_URL for all tests
        redis_url = f"redis://{redis.get_container_host_ip()}:{redis.get_exposed_port(6379)}/0"
        os.environ["REDIS_URL"] = redis_url
        yield redis


@pytest.fixture(scope="function")
def db_session(postgres_container):
    """
    Create a test database session.
    
    Uses PostgreSQL testcontainer for testing (identical to production).
    Each test gets a fresh database schema that is automatically cleaned up.
    """
    from sqlalchemy import event, text
    
    # Import all models - app.models.__init__.py imports everything
    # This ensures all tables are registered with Base.metadata before create_all
    import app.models  # noqa: F401
    
    # Force evaluation of all model relationships by accessing __tablename__
    # This ensures foreign key references are fully resolved
    for table in Base.metadata.tables.values():
        _ = table.name  # Access to force lazy evaluation
    
    # Create engine from the container's connection URL
    engine = create_engine(postgres_container.get_connection_url(), echo=False)
    
    # Set search_path on each connection (matches production database.py)
    @event.listens_for(engine, "connect")
    def set_search_path(dbapi_conn, connection_record):
        """Set search_path on each connection to include both schemas."""
        cursor = dbapi_conn.cursor()
        cursor.execute("SET search_path TO public, ai_analysis")
        cursor.close()
    
    # Create ai_analysis schema if it doesn't exist
    with engine.connect() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS ai_analysis"))
        conn.commit()
    
    # Create all tables in dependency order
    # SQLAlchemy will automatically sort by foreign key dependencies
    Base.metadata.create_all(engine)
    
    # Create session
    TestingSessionLocal = sessionmaker(bind=engine)
    session = TestingSessionLocal()
    
    # Muscles and exercises now live in exercise-service and are fetched over
    # gRPC, so there is nothing to seed locally. Tests that exercise the
    # gRPC-backed services should mock app.clients.exercise_client.ExerciseClient.
    
    try:
        yield session
        # Commit any pending changes before cleanup
        session.commit()
    except Exception:
        # Rollback on error
        session.rollback()
        raise
    finally:
        # Clean up: drop all tables and dispose engine
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture(scope="function")
def celery_worker(redis_container):
    """
    Provides a Celery app configured with the test Redis container.
    
    Useful for testing Celery tasks in integration tests.
    ML tests can use this to test real task execution.
    """
    from app.celery_app import celery_app
    
    # The celery_app is already configured with REDIS_URL from environment
    # which was set by the redis_container fixture
    return celery_app


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
        'ml_predictor': mocker.patch('app.modules.progression.progressive_overload_engine.ML_AVAILABLE', False),
        'model_manager': mocker.patch('app.modules.ml.model_manager.ModelManager'),
        'workout_predictor': mocker.patch('app.modules.ml.workout_predictor.WorkoutPredictorService'),
    }
    return mocks


@pytest.fixture
def sample_athlete(db_session):
    """Create a sample athlete for testing."""
    from tests.factories import AthleteFactory
    return AthleteFactory.create(db_session)


# NOTE: the former `sample_exercise` fixture (DB-backed Exercise) was removed.
# Exercises now live in exercise-service and are fetched over gRPC; tests that
# need exercise data should mock app.clients.exercise_client.ExerciseClient.


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

