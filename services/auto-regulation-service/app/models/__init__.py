"""
SQLAlchemy models for the application.
"""
from autoregulation.models.athlete import Athlete
from autoregulation.models.exercise import Exercise
from autoregulation.models.muscle_group import MuscleGroupModel, ExerciseMuscle
from autoregulation.models.workout import (
    WorkoutPlan,
    PlanEntry,
    WorkoutDay,
    WorkoutDayExercise,
    WorkoutSession,
    ExerciseSet,
)
from autoregulation.models.recovery import RecoveryMetrics
from autoregulation.models.rpe_calibration import AthleteRPECalibration
from autoregulation.models.performance_trends import PerformanceTrend
from autoregulation.models.exercise_progression import ExerciseProgressionTracking
from autoregulation.models.form_tracking import FormQualityTrend
from autoregulation.models.personal_records import ExercisePersonalRecord
from autoregulation.models.workout_prescription_history import WorkoutPrescriptionHistory
from autoregulation.models.training_job import MLTrainingJob, MLJobStatus

__all__ = [
    "Athlete",
    "Exercise",
    "MuscleGroupModel",
    "ExerciseMuscle",
    "WorkoutPlan",
    "PlanEntry",
    "WorkoutDay",
    "WorkoutDayExercise",
    "WorkoutSession",
    "ExerciseSet",
    "RecoveryMetrics",
    "AthleteRPECalibration",
    "PerformanceTrend",
    "ExerciseProgressionTracking",
    "FormQualityTrend",
    "ExercisePersonalRecord",
    "WorkoutPrescriptionHistory",
    "MLTrainingJob",
    "MLJobStatus",
]


