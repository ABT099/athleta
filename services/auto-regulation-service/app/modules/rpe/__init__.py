"""
RPE module — RPE calibration accuracy tracking and fatigue estimation.

Public interface:
    RPECalibrationService — per-athlete RPE accuracy calibration

Internal helpers (service module) must not be imported directly from outside.
"""
from app.modules.rpe.service import RPECalibrationService

__all__ = ["RPECalibrationService"]
