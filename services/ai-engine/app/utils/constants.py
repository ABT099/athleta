"""
Training constants and reference data.
"""
from enum import Enum
from typing import Dict, List


class TrainingExperience(str, Enum):
    """Training experience levels."""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class Gender(str, Enum):
    """Biological sex for training considerations."""
    MALE = "male"
    FEMALE = "female"


class TrainingType(str, Enum):
    """Training goal types."""
    HYPERTROPHY = "hypertrophy"
    STRENGTH = "strength"
    HYBRID = "hybrid"


class PeriodizationModel(str, Enum):
    """Periodization approaches."""
    LINEAR = "linear"
    UNDULATING = "undulating"  # DUP
    BLOCK = "block"


class TrainingPhase(str, Enum):
    """Training phases within a mesocycle."""
    ACCUMULATION = "accumulation"  # Volume focus
    INTENSIFICATION = "intensification"  # Load focus
    REALIZATION = "realization"  # Peaking/testing


class SleepQuality(str, Enum):
    """Sleep quality levels."""
    POOR = "poor"
    NOT_BAD = "not_bad"
    GOOD = "good"
    EXCELLENT = "excellent"


class MuscleGroup(str, Enum):
    """Major muscle groups."""
    CHEST = "chest"
    BACK = "back"
    SHOULDERS = "shoulders"
    BICEPS = "biceps"
    TRICEPS = "triceps"
    FOREARMS = "forearms"
    QUADRICEPS = "quadriceps"
    HAMSTRINGS = "hamstrings"
    GLUTES = "glutes"
    CALVES = "calves"
    ABS = "abs"
    LOWER_BACK = "lower_back"


class FocusArea(str, Enum):
    """Simplified focus areas for athlete preferences."""
    CHEST = "chest"
    BACK = "back"
    SHOULDERS = "shoulders"
    ARMS = "arms"
    LEGS = "legs"
    CORE = "core"


FOCUS_AREA_TO_MUSCLE_GROUPS: Dict[FocusArea, List[MuscleGroup]] = {
    FocusArea.CHEST: [MuscleGroup.CHEST],
    FocusArea.BACK: [MuscleGroup.BACK],
    FocusArea.SHOULDERS: [MuscleGroup.SHOULDERS],
    FocusArea.ARMS: [MuscleGroup.BICEPS, MuscleGroup.TRICEPS, MuscleGroup.FOREARMS],
    FocusArea.LEGS: [MuscleGroup.QUADRICEPS, MuscleGroup.HAMSTRINGS, MuscleGroup.GLUTES],
    FocusArea.CORE: [MuscleGroup.ABS, MuscleGroup.LOWER_BACK],
}


class MuscleSize(str, Enum):
    """Relative muscle size for recovery considerations."""
    SMALL = "small"  # Biceps, triceps, calves, forearms
    MEDIUM = "medium"  # Shoulders, abs
    LARGE = "large"  # Chest, back, quads, hamstrings, glutes


# Muscle group to size mapping
MUSCLE_SIZE_MAP: Dict[MuscleGroup, MuscleSize] = {
    MuscleGroup.CHEST: MuscleSize.LARGE,
    MuscleGroup.BACK: MuscleSize.LARGE,
    MuscleGroup.SHOULDERS: MuscleSize.MEDIUM,
    MuscleGroup.BICEPS: MuscleSize.SMALL,
    MuscleGroup.TRICEPS: MuscleSize.SMALL,
    MuscleGroup.FOREARMS: MuscleSize.SMALL,
    MuscleGroup.QUADRICEPS: MuscleSize.LARGE,
    MuscleGroup.HAMSTRINGS: MuscleSize.LARGE,
    MuscleGroup.GLUTES: MuscleSize.LARGE,
    MuscleGroup.CALVES: MuscleSize.SMALL,
    MuscleGroup.ABS: MuscleSize.MEDIUM,
    MuscleGroup.LOWER_BACK: MuscleSize.MEDIUM,
}

# Recovery time in hours by muscle size
RECOVERY_TIME_HOURS: Dict[MuscleSize, int] = {
    MuscleSize.SMALL: 48,
    MuscleSize.MEDIUM: 60,
    MuscleSize.LARGE: 72,
}

# Sleep quality multipliers for recovery
SLEEP_QUALITY_MULTIPLIERS: Dict[SleepQuality, float] = {
    SleepQuality.POOR: 0.7,
    SleepQuality.NOT_BAD: 0.85,
    SleepQuality.GOOD: 0.95,
    SleepQuality.EXCELLENT: 1.0,
}

# Training experience progression rates (% increase per session when appropriate)
PROGRESSION_RATES: Dict[TrainingExperience, Dict[str, float]] = {
    TrainingExperience.BEGINNER: {
        "load_increase": 0.05,  # 5% per session
        "volume_increase": 0.10,  # 10% per week
        "max_weekly_volume_increase": 0.15,
    },
    TrainingExperience.INTERMEDIATE: {
        "load_increase": 0.025,  # 2.5% per session
        "volume_increase": 0.05,  # 5% per week
        "max_weekly_volume_increase": 0.10,
    },
    TrainingExperience.ADVANCED: {
        "load_increase": 0.01,  # 1% per session
        "volume_increase": 0.025,  # 2.5% per week
        "max_weekly_volume_increase": 0.10,
    },
}

# Minimum Effective Volume (MEV) sets per muscle per week by experience
MEV_SETS_PER_WEEK: Dict[TrainingExperience, int] = {
    TrainingExperience.BEGINNER: 8,
    TrainingExperience.INTERMEDIATE: 10,
    TrainingExperience.ADVANCED: 12,
}

# Maximum Recoverable Volume (MRV) sets per muscle per week by experience
MRV_SETS_PER_WEEK: Dict[TrainingExperience, int] = {
    TrainingExperience.BEGINNER: 15,
    TrainingExperience.INTERMEDIATE: 20,
    TrainingExperience.ADVANCED: 25,
}

# RPE to %1RM mapping (Zourdos et al., 2016)
# Reference: Zourdos et al. (2016). Novel Resistance Training-Specific Rating of Perceived Exertion Scale
RPE_TO_INTENSITY: Dict[float, float] = {
    10.0: 1.00,  # Maximal effort
    9.5: 0.98,
    9.0: 0.96,
    8.5: 0.94,
    8.0: 0.92,
    7.5: 0.89,
    7.0: 0.86,
    6.5: 0.84,
    6.0: 0.82,
    5.5: 0.80,
    5.0: 0.77
}

# RPE to RIR conversion (Rate of Perceived Exertion to Reps in Reserve)
RPE_TO_RIR: Dict[float, int] = {
    10.0: 0,
    9.5: 0,
    9.0: 1,
    8.5: 1,
    8.0: 2,
    7.5: 2,
    7.0: 3,
    6.5: 3,
    6.0: 4,
    5.5: 4,
    5.0: 5,
}

# Rep ranges by training goal
REP_RANGES: Dict[TrainingType, Dict[str, int]] = {
    TrainingType.STRENGTH: {"min": 1, "max": 6, "optimal": 3},
    TrainingType.HYPERTROPHY: {"min": 6, "max": 15, "optimal": 10},
    TrainingType.HYBRID: {"min": 3, "max": 12, "optimal": 6},
}

# Intensity zones (% of 1RM) by training goal
INTENSITY_ZONES: Dict[TrainingType, Dict[str, float]] = {
    TrainingType.STRENGTH: {"min": 0.85, "max": 1.0, "optimal": 0.90},
    TrainingType.HYPERTROPHY: {"min": 0.60, "max": 0.85, "optimal": 0.70},
    TrainingType.HYBRID: {"min": 0.70, "max": 0.90, "optimal": 0.80},
}

# ==============================
# ADVANCED TRAINING FEATURES
# ==============================

# Exercise types for progression rate differentiation
class ExerciseType(str, Enum):
    """Exercise categorization for progression logic."""
    COMPOUND = "compound"
    ISOLATION = "isolation"

# Age-based progression modifiers
# Format: (min_age, max_age): multiplier
# Note: These are starting points - individual variability is large
# Well-trained older athletes may progress similar to younger novices
AGE_PROGRESSION_MODIFIERS: Dict[tuple, float] = {
    (18, 25): 1.10,   # Peak recovery capacity (softened from 1.15)
    (26, 35): 1.0,    # Baseline
    (36, 45): 0.90,   # Reduced recovery (softened from 0.85)
    (46, 55): 0.80,   # Further reduction (softened from 0.70)
    (56, 65): 0.70,   # Masters athletes (softened from 0.60)
    (66, 100): 0.65,  # Senior masters (new bracket)
}

# Gender-based recovery modifiers
# Note: Focuses on fatigue resistance in submaximal work rather than blanket "faster recovery"
# Individual variability within genders is often larger than between-gender differences
# Recovery varies significantly by exercise type, volume, and individual factors
GENDER_RECOVERY_MODIFIERS: Dict[Gender, float] = {
    Gender.MALE: 1.0,    # Baseline
    Gender.FEMALE: 1.08,  # Women show ~8% greater fatigue resistance in submaximal work
                          # (slightly reduced from 1.1 to reflect nuance)
}

# Exercise-specific progression rates (% per session)
EXERCISE_PROGRESSION_RATES: Dict[ExerciseType, Dict[TrainingExperience, float]] = {
    ExerciseType.COMPOUND: {
        TrainingExperience.BEGINNER: 0.03,    # 3% per session
        TrainingExperience.INTERMEDIATE: 0.02,  # 2% per session
        TrainingExperience.ADVANCED: 0.01,     # 1% per session
    },
    ExerciseType.ISOLATION: {
        TrainingExperience.BEGINNER: 0.06,    # 6% per session
        TrainingExperience.INTERMEDIATE: 0.05,  # 5% per session
        TrainingExperience.ADVANCED: 0.03,     # 3% per session
    },
}

# New exercise progression rate (slower for unfamiliar movements)
NEW_EXERCISE_PROGRESSION_RATE = 0.01  # 1% per session for first 4-6 weeks

# Double progression thresholds
DOUBLE_PROGRESSION_CONFIG = {
    "rep_increase_per_session": 1,  # Add 1 rep per session
    "weight_increase_percent": 0.05, # 5% weight increase when hitting max reps
}

# Familiarity score progression (0.0 to 1.0)
# Increases each session until exercise is "familiar"
FAMILIARITY_INCREASE_RATE = 0.1  # Increases by 0.1 per session
FAMILIARITY_THRESHOLD = 0.6      # Considered "familiar" at 0.6+

# Autoregulated deload thresholds
DELOAD_THRESHOLDS = {
    "performance_drop_percent": 0.10,        # 10% drop triggers concern
    "consecutive_poor_sessions": 2,          # 2 poor sessions in a row
    "low_readiness_days": 3,                 # 3 days with readiness <0.5
    "low_readiness_threshold": 0.5,          # Readiness score threshold
    "rpe_spike_threshold": 1.5,              # RPE increase >1.5 at same weight
    "volume_spike_threshold": 1.3,           # Volume increase >30% triggers warning
}

# DUP (Daily Undulating Periodization) configuration
DUP_TRAINING_DAYS = {
    "high_volume": {
        "intensity_percent": 0.70,  # 70% of 1RM
        "rep_range": (10, 12),
        "sets_multiplier": 1.2,     # 20% more sets
        "focus": "volume",
    },
    "moderate": {
        "intensity_percent": 0.80,  # 80% of 1RM
        "rep_range": (6, 8),
        "sets_multiplier": 1.0,     # Normal sets
        "focus": "balanced",
    },
    "high_intensity": {
        "intensity_percent": 0.90,  # 90% of 1RM
        "rep_range": (3, 5),
        "sets_multiplier": 0.7,     # 30% fewer sets
        "focus": "intensity",
    },
}

# Block periodization configuration
BLOCK_PERIODIZATION_CONFIG = {
    "accumulation": {
        "duration_weeks": (3, 4),
        "volume_multiplier": 1.2,    # High volume
        "intensity_multiplier": 0.75, # Lower intensity
        "focus": "volume_accumulation",
        "deload_frequency": 4,        # Every 4 weeks
    },
    "intensification": {
        "duration_weeks": (2, 3),
        "volume_multiplier": 0.85,    # Reduced volume
        "intensity_multiplier": 1.1,  # Higher intensity
        "focus": "strength_building",
        "deload_frequency": 3,        # Every 3 weeks
    },
    "realization": {
        "duration_weeks": (1, 2),
        "volume_multiplier": 0.6,     # Low volume
        "intensity_multiplier": 1.15, # Peak intensity
        "focus": "peaking",
        "deload_frequency": 2,        # Every 2 weeks
    },
}

# Progression states for double progression
class ProgressionState(str, Enum):
    """State of exercise progression."""
    REP_PROGRESSION = "rep_progression"      # Adding reps
    WEIGHT_PROGRESSION = "weight_progression" # Adding weight
    MAINTAINING = "maintaining"              # Maintaining current parameters
    DELOADING = "deloading"                  # Reducing load


