"""
Volume module — volume management (MEV/MAV/MRV) and recovery modelling.

Public interface:
    VolumeManager    — volume-landmark tracking and volume prescription
    RecoveryAnalyzer — readiness/recovery scoring from athlete-reported metrics

Internal helpers (manager, recovery modules) must not be imported directly
from outside this package.
"""
from app.modules.volume.manager import VolumeManager
from app.modules.volume.recovery import RecoveryAnalyzer

__all__ = ["VolumeManager", "RecoveryAnalyzer"]
