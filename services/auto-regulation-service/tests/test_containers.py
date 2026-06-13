"""
Test that testcontainers are working correctly.
"""
import pytest
from sqlalchemy import text


@pytest.mark.integration
def test_postgres_container_connection(db_session):
    """Test that PostgreSQL container is working."""
    # Execute a simple query
    result = db_session.execute(text("SELECT version()"))
    version = result.scalar()
    
    # Verify it's PostgreSQL
    assert "PostgreSQL" in version
    assert "18" in version  # PostgreSQL 18


@pytest.mark.integration
def test_redis_container_connection(redis_container):
    """Test that Redis container is working."""
    import redis
    
    # Connect to Redis
    redis_url = f"redis://{redis_container.get_container_host_ip()}:{redis_container.get_exposed_port(6379)}/0"
    r = redis.from_url(redis_url)
    
    # Test basic operations
    r.set("test_key", "test_value")
    assert r.get("test_key") == b"test_value"
    
    # Cleanup
    r.delete("test_key")


@pytest.mark.integration
def test_database_persistence_within_test(db_session):
    """Test that database changes persist within a single test."""
    from autoregulation.models import MuscleGroupModel
    
    # Query muscle groups (should be seeded)
    muscle_groups = db_session.query(MuscleGroupModel).all()
    assert len(muscle_groups) > 0
    
    # Verify specific muscle groups exist
    muscle_names = [mg.name for mg in muscle_groups]
    assert "mid_chest" in muscle_names
    assert "lats" in muscle_names
    assert "quadriceps" in muscle_names

