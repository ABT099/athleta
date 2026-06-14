"""
Prescription module — workout prescription generation, intensity techniques,
and warm-up set generation.

Public interface (the only symbols other modules may import):
    PrescriptionGeneratorService — target RPE/RIR/rest generation
    IntensityTechniqueService    — drop sets, rest-pause, myo-reps, ... selection
    WarmupGenerator              — warm-up set prescription
    router                       — FastAPI router for /prescriptions endpoints

Internal helpers (generator, intensity, warmup, schemas modules) must not be
imported directly from outside this package.
"""
from app.modules.prescription.generator import PrescriptionGeneratorService
from app.modules.prescription.intensity import IntensityTechniqueService
from app.modules.prescription.warmup import WarmupGenerator
from app.modules.prescription.router import router

__all__ = [
    "PrescriptionGeneratorService",
    "IntensityTechniqueService",
    "WarmupGenerator",
    "router",
]
