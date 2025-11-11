"""
Pytest configuration and fixtures.
"""
import os
import pytest
import json
from sqlalchemy import create_engine, event, String, Text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects import sqlite

# Set test database URL before importing app modules
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from app.database import Base


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


@pytest.fixture(scope="function")
def db_session():
    """
    Create a test database session.
    
    Uses in-memory SQLite for testing with PostgreSQL ARRAY compatibility.
    """
    # Patch ARRAY type for SQLite compatibility
    from sqlalchemy.dialects.postgresql import ARRAY
    
    # Override ARRAY compilation for SQLite
    @event.listens_for(Base.metadata, "before_create")
    def receive_before_create(target, connection, **kw):
        """Handle ARRAY types in SQLite."""
        if connection.dialect.name == 'sqlite':
            for table in Base.metadata.tables.values():
                for column in table.columns:
                    if hasattr(column.type, '__class__'):
                        if column.type.__class__.__name__ == 'ARRAY':
                            # Replace ARRAY with Text for SQLite
                            column.type = Text()
    
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

