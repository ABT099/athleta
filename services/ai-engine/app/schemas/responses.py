"""
Generic response schemas.
"""
from pydantic import BaseModel
from typing import Optional, Any


class ErrorResponse(BaseModel):
    """Schema for error responses."""
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None


class SuccessResponse(BaseModel):
    """Schema for generic success responses."""
    message: str
    data: Optional[Any] = None


class HealthResponse(BaseModel):
    """Schema for health check response."""
    status: str
    version: Optional[str] = None


