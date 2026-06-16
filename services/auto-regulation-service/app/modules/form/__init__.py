"""
Form module — form-quality tracking and degradation feedback.

Public interface:
    FormQualityService — per-session form scoring and degradation trends

Internal helpers (service module) must not be imported directly from outside.
"""
from app.modules.form.service import FormQualityService

__all__ = ["FormQualityService"]
