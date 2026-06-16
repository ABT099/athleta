"""
SQLAlchemy models for auto-regulation's OWN database (algo state only).

All models map onto ``AutoregBase`` in the ai_analysis schema. api-owned data
(athletes, plans, days, exercises, sessions, sets, recovery, PRs) is NOT mapped
here — it is pushed in the analyze request or fetched via ApiClient, and appears
in algo tables only as soft integer references.
"""
from app.models.plan_entry import PlanEntry
from app.models.performance_trends import PerformanceTrend
from app.models.exercise_progression import ExerciseProgressionTracking
from app.models.form_tracking import FormQualityTrend
from app.models.rpe_calibration import AthleteRPECalibration
from app.models.workout_prescription_history import WorkoutPrescriptionHistory
from app.models.muscle_volume_log import MuscleVolumeLog
from app.models.joint_stress_log import JointStressLog
from app.models.training_job import MLTrainingJob, MLJobStatus

__all__ = [
    "PlanEntry",
    "PerformanceTrend",
    "ExerciseProgressionTracking",
    "FormQualityTrend",
    "AthleteRPECalibration",
    "WorkoutPrescriptionHistory",
    "MuscleVolumeLog",
    "JointStressLog",
    "MLTrainingJob",
    "MLJobStatus",
]
