"""
Application configuration settings.
"""
from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import List
import warnings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
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
    
    # JWT - already present in env vars
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ISSUER: str = "athleta-api"
    
    # CORS
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:8000"
    
    @property
    def allowed_origins_list(self) -> List[str]:
        """Parse ALLOWED_ORIGINS into a list."""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()


