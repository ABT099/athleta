"""
Progression module — the progressive-overload orchestrator: load/rep progression,
PR detection, plateau intervention, workout scheduling, plan updates, and the
workout-completion flow.

Public interface:
    ProgressiveOverloadEngine   — core analysis + recommendation engine
    PlanUpdaterService          — applies AI adjustments to upcoming workouts
    PRTrackerService            — personal-record detection
    WorkoutScheduler            — workout rotation scheduling
    ExerciseProgressionService  — exercise-level double-progression state machine
    PlateauInterventionService  — plateau detection + intervention strategy
    PlateauType                 — plateau classification enum
    router                      — FastAPI router for /workouts endpoints

Internal submodules must not be imported directly from outside this package
(tests excepted). Cross-module needs go through this facade.

NOTE: this module currently depends on every other module's facade because it
orchestrates the completion flow inline. Phase 4 replaces that orchestration
with an in-process event bus, after which this module publishes events instead
of calling siblings directly.
"""
from app.modules.progression.exercise_progression import ExerciseProgressionService
from app.modules.progression.pr_tracker import PRTrackerService
from app.modules.progression.workout_scheduler import WorkoutScheduler
from app.modules.progression.plateau_intervention import (
    PlateauInterventionService,
    PlateauType,
)
from app.modules.progression.progressive_overload_engine import ProgressiveOverloadEngine
from app.modules.progression.plan_updater import PlanUpdaterService
from app.modules.progression.router import router

__all__ = [
    "ProgressiveOverloadEngine",
    "PlanUpdaterService",
    "PRTrackerService",
    "WorkoutScheduler",
    "ExerciseProgressionService",
    "PlateauInterventionService",
    "PlateauType",
    "router",
]
