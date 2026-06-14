"""
Application configuration settings.
"""
from pydantic_settings import BaseSettings
from pydantic import field_validator, ConfigDict
from typing import List
import warnings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = ConfigDict(env_file=".env", case_sensitive=True)
    
    # Database - required from environment
    DATABASE_URL: str
    
    # API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_DEBUG: bool = False
    
    # Security
    SECRET_KEY: str = "your-secret-key-here-change-in-production"
    
    @field_validator('SECRET_KEY')
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        """Validate that SECRET_KEY is not the default placeholder."""
        if v == "your-secret-key-here-change-in-production":
            warnings.warn(
                "SECRET_KEY is using the default placeholder value. "
                "This is insecure for production. Please set a secure SECRET_KEY in your environment.",
                UserWarning
            )
        return v

    # Redis & Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_TASK_TIMEOUT: int = 1800  # 30 minutes
    
    # ML Retraining Settings
    RETRAINING_SESSION_THRESHOLD: int = 20  # ~1 mesocycle worth of sessions
    RETRAINING_STALENESS_DAYS: int = 60  # Catches breaks before severe detraining
    
    # CORS
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:8000"
    
    @property
    def allowed_origins_list(self) -> List[str]:
        """Parse ALLOWED_ORIGINS into a list."""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]


settings = Settings()


