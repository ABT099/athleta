"""
Injury module — joint-stress profiling and injury-aware exercise substitution.

Public interface:
    InjuryPreventionService — weighted joint-stress profile + risk assessment
    ExerciseSubstitutor     — injury-aware substitution (thin exercise-service wrapper)
    router                  — FastAPI router for /injury-prevention endpoints

Internal helpers (service, substitutor, router modules) must not be imported
directly from outside this package.
"""
from app.modules.injury.service import InjuryPreventionService
from app.modules.injury.substitutor import ExerciseSubstitutor
from app.modules.injury.router import router

__all__ = ["InjuryPreventionService", "ExerciseSubstitutor", "router"]
