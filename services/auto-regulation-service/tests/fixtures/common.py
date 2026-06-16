"""
Common test fixtures and helpers.

This module provides shared fixtures and helper functions for tests.
"""
from typing import Dict, Any

# Common test data constants
DEFAULT_ATHLETE_AGE = 25
DEFAULT_RPE_CALIBRATION = 1.0
DEFAULT_WORKOUT_DURATION = 60
DEFAULT_SETS_COUNT = 3
DEFAULT_REPS_RANGE = (8, 12)
DEFAULT_RPE = 8.0

# Common assertion helpers
def assert_workout_parameters_valid(adjustments: Dict[str, Any]) -> None:
    """
    Assert that workout parameter adjustments are valid.
    
    Args:
        adjustments: Dictionary with volume_multiplier and intensity_multiplier
    """
    assert "volume_multiplier" in adjustments
    assert "intensity_multiplier" in adjustments
    assert 0.0 <= adjustments["volume_multiplier"] <= 2.0
    assert 0.0 <= adjustments["intensity_multiplier"] <= 2.0
    assert "reasoning" in adjustments
    assert isinstance(adjustments["reasoning"], str)

