"""
Machine Learning module for workout prediction and optimization.
"""
from app.modules.ml.base_model import BaseMLModel
from app.modules.ml.model_manager import ModelManager
from app.modules.ml.feature_engineering import FeatureEngineer

__all__ = [
    "BaseMLModel",
    "ModelManager",
    "FeatureEngineer",
]

