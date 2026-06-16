"""
Analysis module — the seam through which the progressive-overload engine sees
data for a single workout completion.

Public interface:
    AnalysisRequest        — the payload api pushes to /analysis/sessions
    AnalysisContext        — immutable, load-once input the engine computes over
    TrainingHistory        — immutable historical window for ML retraining
    build_analysis_context — assemble a context (request payload + local algo reads)
    build_training_history — assemble a history window (2 bulk api reads + local)
"""
from app.modules.analysis.context import (
    AnalysisContext,
    AnalysisRequest,
    TrainingHistory,
    build_analysis_context,
    build_training_history,
)

__all__ = [
    "AnalysisContext",
    "AnalysisRequest",
    "TrainingHistory",
    "build_analysis_context",
    "build_training_history",
]
