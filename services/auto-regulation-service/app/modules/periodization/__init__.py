"""
Periodization module — periodization-model selection and plan-duration
recommendation (linear / undulating / block).

Public interface:
    PeriodizationService — periodization strategy + duration recommendation
    DUPDay               — daily-undulating-periodization day descriptor
    router               — FastAPI router for /plan/recommend-config

Internal helpers (service module) must not be imported directly from outside.
"""
from app.modules.periodization.service import PeriodizationService, DUPDay
from app.modules.periodization.router import router

__all__ = ["PeriodizationService", "DUPDay", "router"]
