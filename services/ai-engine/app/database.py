"""
Database connection and session management.
"""
from sqlalchemy import create_engine, event, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

from app.config import settings

# Create database engine
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    echo=settings.API_DEBUG
)

# Set search_path to include both public and ai_analysis schemas
# This allows queries to access tables in both schemas
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


