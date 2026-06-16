"""
Database connection and session management.
"""
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from typing import Generator, Dict, Any, Optional

from app.config import settings

# Detect if using SQLite (for tests)
IS_SQLITE = settings.DATABASE_URL.startswith("sqlite")

# Create database engine
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True if not IS_SQLITE else False,
    echo=settings.API_DEBUG
)

# Set search_path to include both public and ai_analysis schemas
# This allows queries to access tables in both schemas
# Only for PostgreSQL
if not IS_SQLITE:
    @event.listens_for(engine, "connect")
    def set_search_path(dbapi_conn, connection_record):
        """Set search_path on each connection to include both schemas."""
        cursor = dbapi_conn.cursor()
        cursor.execute("SET search_path TO public, ai_analysis")
        cursor.close()

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base class for models
Base = declarative_base()


# --- Auto-regulation's OWN database (algo-only state) ------------------------
# Auto-regulation owns only algorithm state (plan entries, performance/form/
# progression trends, RPE calibration, prescription history, ML jobs). It lives
# in a separate database; api-owned data is fetched via ApiClient, not joined.
# Defaults to DATABASE_URL so single-DB setups and tests keep working until the
# data is physically split.
AUTOREG_DATABASE_URL = settings.AUTOREG_DATABASE_URL or settings.DATABASE_URL
AUTOREG_IS_SQLITE = AUTOREG_DATABASE_URL.startswith("sqlite")

autoreg_engine = create_engine(
    AUTOREG_DATABASE_URL,
    pool_pre_ping=not AUTOREG_IS_SQLITE,
    echo=settings.API_DEBUG,
)

if not AUTOREG_IS_SQLITE:
    @event.listens_for(autoreg_engine, "connect")
    def set_autoreg_search_path(dbapi_conn, connection_record):
        """Algo tables live in the ai_analysis schema of auto-regulation's DB."""
        cursor = dbapi_conn.cursor()
        cursor.execute("SET search_path TO ai_analysis, public")
        cursor.close()

AutoregSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=autoreg_engine
)

# Separate declarative registry: auto-reg-owned models map here, never alongside
# api-owned tables (which auto-regulation no longer maps).
AutoregBase = declarative_base()


def get_autoreg_db() -> Generator[Session, None, None]:
    """Dependency function for a session against auto-regulation's own database."""
    db = AutoregSessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_schema_table_args(schema: str = "ai_analysis") -> Dict[str, Any]:
    """
    Get table args with schema for PostgreSQL, empty for SQLite.
    
    Args:
        schema: The schema name (ignored for SQLite)
        
    Returns:
        Dict with table args or empty dict for SQLite
    """
    if IS_SQLITE:
        return {}
    return {"schema": schema}


def get_table_args_with_constraints(*constraints, schema: str = "ai_analysis"):
    """
    Get table args with constraints and optional schema.
    
    Use this when you have UniqueConstraint or other constraints
    combined with schema specification.
    
    Args:
        *constraints: SQLAlchemy constraints (UniqueConstraint, etc.)
        schema: The schema name (ignored for SQLite)
        
    Returns:
        Tuple of constraints with schema dict for PostgreSQL,
        or just tuple of constraints for SQLite
    """
    if IS_SQLITE:
        return tuple(constraints)
    return (*constraints, {"schema": schema})


def get_fk_reference(table_name: str, schema: Optional[str] = "public") -> str:
    """
    Get foreign key reference with schema for PostgreSQL, without for SQLite.
    
    Args:
        table_name: The table name
        schema: The schema name (ignored for SQLite)
        
    Returns:
        String for foreign key reference
    """
    if IS_SQLITE or schema is None:
        return table_name
    return f"{schema}.{table_name}"


# Mapping from broad muscle group names (MuscleGroup enum values) to granular muscle names (database)
MUSCLE_GROUP_TO_GRANULAR: Dict[str, list] = {
    "chest": ["mid_chest", "upper_chest", "lower_chest"],
    "back": ["lats", "mid_back", "upper_traps", "lower_traps"],
    "shoulders": ["anterior_delt", "lateral_delt", "posterior_delt"],
    "biceps": ["biceps"],
    "triceps": ["triceps"],
    "forearms": ["forearms"],
    "quadriceps": ["quadriceps"],
    "hamstrings": ["hamstrings"],
    "glutes": ["glutes"],
    "calves": ["calves"],
    "abs": ["abs"],
    "lower_back": ["erector_spinae"],
}


def get_granular_muscles(muscle_group_name: str) -> list:
    """
    Get granular muscle names for a broad muscle group.
    
    Args:
        muscle_group_name: Broad muscle group name (e.g., "chest")
        
    Returns:
        List of granular muscle names (e.g., ["mid_chest", "upper_chest", "lower_chest"])
    """
    return MUSCLE_GROUP_TO_GRANULAR.get(muscle_group_name.lower(), [muscle_group_name])


def get_db() -> Generator[Session, None, None]:
    """
    Dependency function to get database session.
    
    Yields:
        Database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


