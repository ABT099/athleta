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


class FocusArea(str, Enum):
    """Simplified focus areas for athlete preferences."""
    CHEST = "chest"
    BACK = "back"
    SHOULDERS = "shoulders"
    ARMS = "arms"
    LEGS = "legs"
    CORE = "core"


class MuscleSize(str, Enum):
    """Relative muscle size for recovery considerations (used for type hints)."""
    SMALL = "small"  # Biceps, triceps, calves, forearms
    MEDIUM = "medium"  # Shoulders, abs
    LARGE = "large"  # Chest, back, quads, hamstrings, glutes

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


# ==============================
# INTENSITY TECHNIQUES
# ==============================

class SetType(str, Enum):
    """How the set is structured - defines rest/weight changes within a set."""
    STRAIGHT = "straight"              # Standard sets (default)
    DROP_SET = "drop_set"            # Reduce weight, continue reps
    REST_PAUSE = "rest_pause"        # Brief rest (10-20s), continue to failure
    MYO_REPS = "myo_reps"            # Activation set + mini-sets (3-5 reps)
    CLUSTER_SET = "cluster_set"      # Intra-set rest (15-30s between clusters)
    SUPERSET_ANTAGONIST = "superset_antagonist"  # Paired with antagonist exercise
    PRE_EXHAUST = "pre_exhaust"      # Isolation before compound (same muscle)


class RepStyle(str, Enum):
    """How individual reps are performed - tempo/ROM modifications."""
    NORMAL = "normal"                        # Standard full ROM reps (default)
    LENGTHENED_PARTIALS = "lengthened_partials"  # Partials in stretched position
    TEMPO_ECCENTRIC = "tempo_eccentric"      # Slow eccentric (3-5 sec)
    TEMPO_PAUSED = "tempo_paused"            # 1-2 sec pause at stretched position
    ECCENTRIC_OVERLOAD = "eccentric_overload"  # Supramaximal eccentric loading


# Set Type Configuration
# Defines when and how each set type should be used
SET_TYPE_CONFIG: Dict[SetType, Dict] = {
    SetType.STRAIGHT: {
        "applicable_training_types": [TrainingType.HYPERTROPHY, TrainingType.STRENGTH, TrainingType.HYBRID],
        "applicable_exercise_types": [ExerciseType.COMPOUND, ExerciseType.ISOLATION],
        "min_experience": TrainingExperience.BEGINNER,
        "applicable_phases": [TrainingPhase.ACCUMULATION, TrainingPhase.INTENSIFICATION, TrainingPhase.REALIZATION],
        "volume_multiplier": 1.0,
        "fatigue_multiplier": 1.0,
        "default_params": {},
    },
    SetType.DROP_SET: {
        "applicable_training_types": [TrainingType.HYPERTROPHY, TrainingType.HYBRID],
        "applicable_exercise_types": [ExerciseType.ISOLATION],  # Safer on isolation
        "min_experience": TrainingExperience.INTERMEDIATE,
        "applicable_phases": [TrainingPhase.ACCUMULATION],
        "volume_multiplier": 1.3,  # Increases effective volume
        "fatigue_multiplier": 1.2,
        "default_params": {
            "drop_percentage": 0.20,  # 20% weight reduction
            "drops_count": 1,  # Single drop (can be 1-2)
        },
    },
    SetType.REST_PAUSE: {
        "applicable_training_types": [TrainingType.HYPERTROPHY, TrainingType.STRENGTH, TrainingType.HYBRID],
        "applicable_exercise_types": [ExerciseType.COMPOUND, ExerciseType.ISOLATION],
        "min_experience": TrainingExperience.INTERMEDIATE,
        "applicable_phases": [TrainingPhase.ACCUMULATION, TrainingPhase.INTENSIFICATION],
        "volume_multiplier": 1.25,
        "fatigue_multiplier": 1.15,
        "default_params": {
            "rest_seconds": 15,  # 15-20 seconds
            "mini_sets_count": 2,  # 2-3 mini-sets after initial set
        },
    },
    SetType.MYO_REPS: {
        "applicable_training_types": [TrainingType.HYPERTROPHY],
        "applicable_exercise_types": [ExerciseType.ISOLATION],
        "min_experience": TrainingExperience.INTERMEDIATE,
        "applicable_phases": [TrainingPhase.ACCUMULATION],
        "volume_multiplier": 1.4,  # Very efficient volume accumulation
        "fatigue_multiplier": 1.1,  # Lower fatigue per rep than straight sets
        "default_params": {
            "activation_reps": 5,  # Initial activation set
            "rest_seconds": 5,  # Very brief rest
            "mini_sets_reps": 3,  # 3-5 reps per mini-set
            "target_total_reps": 20,  # Total reps across all mini-sets
        },
    },
    SetType.CLUSTER_SET: {
        "applicable_training_types": [TrainingType.STRENGTH, TrainingType.HYBRID],
        "applicable_exercise_types": [ExerciseType.COMPOUND],
        "min_experience": TrainingExperience.ADVANCED,
        "applicable_phases": [TrainingPhase.INTENSIFICATION, TrainingPhase.REALIZATION],
        "volume_multiplier": 1.0,  # Same volume, better quality
        "fatigue_multiplier": 0.9,  # Less fatigue due to intra-set rest
        "default_params": {
            "reps_per_cluster": 3,  # 2-5 reps per cluster
            "rest_seconds": 20,  # 15-30 seconds between clusters
            "clusters_count": 3,  # 3-5 clusters per set
        },
    },
    SetType.SUPERSET_ANTAGONIST: {
        "applicable_training_types": [TrainingType.HYPERTROPHY, TrainingType.HYBRID],
        "applicable_exercise_types": [ExerciseType.COMPOUND, ExerciseType.ISOLATION],
        "min_experience": TrainingExperience.BEGINNER,
        "applicable_phases": [TrainingPhase.ACCUMULATION],
        "volume_multiplier": 1.0,  # Same volume, time-efficient
        "fatigue_multiplier": 1.05,
        "default_params": {
            "rest_between_exercises": 0,  # No rest between exercises
            "rest_after_pair": 60,  # Rest after completing both exercises
        },
    },
    SetType.PRE_EXHAUST: {
        "applicable_training_types": [TrainingType.HYPERTROPHY],
        "applicable_exercise_types": [ExerciseType.ISOLATION],  # First exercise is isolation
        "min_experience": TrainingExperience.INTERMEDIATE,
        "applicable_phases": [TrainingPhase.ACCUMULATION],
        "volume_multiplier": 1.1,
        "fatigue_multiplier": 1.15,
        "default_params": {
            "isolation_sets": 1,  # 1-2 sets of isolation first
            "rest_between": 30,  # Short rest before compound
        },
    },
}

# Rep Style Configuration
# Defines when and how each rep style should be used
REP_STYLE_CONFIG: Dict[RepStyle, Dict] = {
    RepStyle.NORMAL: {
        "applicable_training_types": [TrainingType.HYPERTROPHY, TrainingType.STRENGTH, TrainingType.HYBRID],
        "applicable_exercise_types": [ExerciseType.COMPOUND, ExerciseType.ISOLATION],
        "min_experience": TrainingExperience.BEGINNER,
        "applicable_phases": [TrainingPhase.ACCUMULATION, TrainingPhase.INTENSIFICATION, TrainingPhase.REALIZATION],
        "volume_multiplier": 1.0,
        "fatigue_multiplier": 1.0,
        "default_params": {},
    },
    RepStyle.LENGTHENED_PARTIALS: {
        "applicable_training_types": [TrainingType.HYPERTROPHY],
        "applicable_exercise_types": [ExerciseType.ISOLATION],
        "min_experience": TrainingExperience.INTERMEDIATE,
        "applicable_phases": [TrainingPhase.ACCUMULATION],
        "volume_multiplier": 1.15,  # Slightly more volume due to time under tension
        "fatigue_multiplier": 1.1,
        "default_params": {
            "partial_rom_percent": 0.5,  # 50% ROM in stretched position
            "full_rom_reps": 0,  # 0 = all partials, or mix with full ROM
        },
    },
    RepStyle.TEMPO_ECCENTRIC: {
        "applicable_training_types": [TrainingType.HYPERTROPHY, TrainingType.HYBRID],
        "applicable_exercise_types": [ExerciseType.COMPOUND, ExerciseType.ISOLATION],
        "min_experience": TrainingExperience.BEGINNER,
        "applicable_phases": [TrainingPhase.ACCUMULATION],
        "volume_multiplier": 1.1,
        "fatigue_multiplier": 1.15,  # Higher fatigue due to time under tension
        "default_params": {
            "eccentric_seconds": 3,  # 3-5 seconds
            "concentric_seconds": 1,  # Normal speed
            "pause_bottom": 0,  # Optional pause
        },
    },
    RepStyle.TEMPO_PAUSED: {
        "applicable_training_types": [TrainingType.HYPERTROPHY, TrainingType.HYBRID],
        "applicable_exercise_types": [ExerciseType.COMPOUND, ExerciseType.ISOLATION],
        "min_experience": TrainingExperience.BEGINNER,
        "applicable_phases": [TrainingPhase.ACCUMULATION],
        "volume_multiplier": 1.05,
        "fatigue_multiplier": 1.1,
        "default_params": {
            "pause_seconds": 1,  # 1-2 seconds at stretched position
            "pause_position": "stretched",  # "stretched" or "mid"
        },
    },
    RepStyle.ECCENTRIC_OVERLOAD: {
        "applicable_training_types": [TrainingType.STRENGTH, TrainingType.HYBRID],
        "applicable_exercise_types": [ExerciseType.COMPOUND],
        "min_experience": TrainingExperience.ADVANCED,
        "applicable_phases": [TrainingPhase.INTENSIFICATION, TrainingPhase.REALIZATION],
        "volume_multiplier": 0.9,  # Lower volume due to intensity
        "fatigue_multiplier": 1.3,  # High fatigue
        "default_params": {
            "overload_percentage": 0.10,  # 10% above concentric max
            "eccentric_seconds": 3,  # 3-5 seconds
            "assisted_concentric": True,  # Need assistance for concentric
        },
    },
}

# Valid combinations of Set Types and Rep Styles
# Some combinations don't make sense or are unsafe
VALID_TECHNIQUE_COMBINATIONS: Dict[SetType, List[RepStyle]] = {
    SetType.STRAIGHT: [RepStyle.NORMAL, RepStyle.LENGTHENED_PARTIALS, RepStyle.TEMPO_ECCENTRIC, RepStyle.TEMPO_PAUSED, RepStyle.ECCENTRIC_OVERLOAD],
    SetType.DROP_SET: [RepStyle.NORMAL, RepStyle.LENGTHENED_PARTIALS, RepStyle.TEMPO_ECCENTRIC],  # No eccentric overload on drops
    SetType.REST_PAUSE: [RepStyle.NORMAL, RepStyle.TEMPO_ECCENTRIC],  # Keep it simple
    SetType.MYO_REPS: [RepStyle.NORMAL],  # Myo-reps work best with normal tempo
    SetType.CLUSTER_SET: [RepStyle.NORMAL, RepStyle.TEMPO_ECCENTRIC, RepStyle.ECCENTRIC_OVERLOAD],  # Power/strength focus
    SetType.SUPERSET_ANTAGONIST: [RepStyle.NORMAL, RepStyle.TEMPO_ECCENTRIC, RepStyle.TEMPO_PAUSED],
    SetType.PRE_EXHAUST: [RepStyle.NORMAL, RepStyle.TEMPO_ECCENTRIC],  # Keep compound movement clean
}

# ==============================
# PRESCRIPTION GENERATION
# ==============================

class ExerciseIntensityCategory(str, Enum):
    """Categorizes exercises by CNS demand - stored in database."""
    COMPOUND_HEAVY = "compound_heavy"      # Squats, Deadlifts, Bench Press
    COMPOUND_MODERATE = "compound_moderate" # Rows, Lunges, OHP
    ISOLATION = "isolation"                # Curls, Extensions, Raises

# Base RPE ranges by training type and exercise category
# References: Zourdos et al. (2016), Schoenfeld et al. (2016)
BASE_RPE_RANGES: Dict[TrainingType, Dict[ExerciseIntensityCategory, Dict[str, float]]] = {
    TrainingType.STRENGTH: {
        ExerciseIntensityCategory.COMPOUND_HEAVY: {"min": 7.0, "max": 8.0},
        ExerciseIntensityCategory.COMPOUND_MODERATE: {"min": 7.0, "max": 9.0},
        ExerciseIntensityCategory.ISOLATION: {"min": 8.0, "max": 9.0},
    },
    TrainingType.HYPERTROPHY: {
        ExerciseIntensityCategory.COMPOUND_HEAVY: {"min": 7.0, "max": 8.0},
        ExerciseIntensityCategory.COMPOUND_MODERATE: {"min": 7.0, "max": 9.0},
        ExerciseIntensityCategory.ISOLATION: {"min": 8.0, "max": 10.0},
    },
    TrainingType.HYBRID: {
        # Hybrid: compounds use strength rules, isolations use hypertrophy rules
        ExerciseIntensityCategory.COMPOUND_HEAVY: {"min": 7.0, "max": 8.0},
        ExerciseIntensityCategory.COMPOUND_MODERATE: {"min": 7.0, "max": 9.0},
        ExerciseIntensityCategory.ISOLATION: {"min": 8.0, "max": 10.0},
    },
}

# Rest periods in seconds
# References: Grgic et al. (2018), Schoenfeld et al. (2016)
BASE_REST_PERIODS: Dict[TrainingType, Dict[ExerciseIntensityCategory, Dict[str, int]]] = {
    TrainingType.STRENGTH: {
        ExerciseIntensityCategory.COMPOUND_HEAVY: {"min": 180, "max": 300},
        ExerciseIntensityCategory.COMPOUND_MODERATE: {"min": 150, "max": 240},
        ExerciseIntensityCategory.ISOLATION: {"min": 90, "max": 120},
    },
    TrainingType.HYPERTROPHY: {
        ExerciseIntensityCategory.COMPOUND_HEAVY: {"min": 120, "max": 180},
        ExerciseIntensityCategory.COMPOUND_MODERATE: {"min": 90, "max": 150},
        ExerciseIntensityCategory.ISOLATION: {"min": 60, "max": 90},
    },
    TrainingType.HYBRID: {
        # Hybrid: compounds use strength rest, isolations use hypertrophy rest
        ExerciseIntensityCategory.COMPOUND_HEAVY: {"min": 180, "max": 300},
        ExerciseIntensityCategory.COMPOUND_MODERATE: {"min": 150, "max": 240},
        ExerciseIntensityCategory.ISOLATION: {"min": 60, "max": 90},
    },
}

# For hybrid training: route to appropriate base type based on exercise category
# Compounds follow strength rules, isolations follow hypertrophy rules
HYBRID_CATEGORY_MAPPING: Dict[ExerciseIntensityCategory, TrainingType] = {
    ExerciseIntensityCategory.COMPOUND_HEAVY: TrainingType.STRENGTH,
    ExerciseIntensityCategory.COMPOUND_MODERATE: TrainingType.STRENGTH,
    ExerciseIntensityCategory.ISOLATION: TrainingType.HYPERTROPHY,
}

# Phase-based modifiers (RPE adjustment, rest multiplier)
PHASE_MODIFIERS: Dict[str, Dict[str, float]] = {
    "accumulation": {"rpe": -0.5, "rest": 0.9},
    "intensification": {"rpe": 0.5, "rest": 1.0},
    "realization": {"rpe": 1.0, "rest": 1.1},
    "deload": {"rpe": -2.0, "rest": 0.75},  # Critical safety phase
}

# Week-in-phase progressive overload modifiers
MICROCYCLE_RPE_MODIFIERS: Dict[int, float] = {
    1: -0.5,   # Ramp-up week
    2: 0.0,    # Baseline
    3: 0.25,   # Building
    4: 0.5,    # Peak (typically before deload)
}

# Safety constants
COMPOUND_RPE_SAFETY_CAP = 9.0   # Max RPE for any compound movement (CNS Tax Rule)
DELOAD_RPE_FLOOR = 5.0          # Min RPE during deload (maintains training stimulus)
ABSOLUTE_RPE_FLOOR = 5.0        # Never prescribe below this
ABSOLUTE_RPE_CEILING = 10.0     # Never prescribe above this

# ==============================
# PLAN ANALYZER CONSTANTS
# ==============================

# Push/Pull muscle group names for balance analysis
# References: Contreras, Helms - Push/pull balance for shoulder health
# Note: These are now queried from the database instead of hardcoded
PUSH_MUSCLE_NAMES = [
    "upper_chest", "mid_chest", "lower_chest",
    "anterior_delt", "lateral_delt",
    "triceps",
]

PULL_MUSCLE_NAMES = [
    "lats", "upper_traps", "mid_back", "lower_traps",
    "posterior_delt",
    "biceps",
    "forearms",
]

# Upper/Lower body muscle group names
UPPER_MUSCLE_NAMES = [
    "upper_chest", "mid_chest", "lower_chest",
    "lats", "upper_traps", "mid_back", "lower_traps",
    "anterior_delt", "lateral_delt", "posterior_delt",
    "biceps", "triceps", "forearms",
]

LOWER_MUSCLE_NAMES = [
    "quadriceps", "hamstrings", "glutes", "hip_flexors", "calves",
]

# Movement pattern priority for exercise ordering
# Lower number = higher priority (should come first in workout)
# References: NSCA Essentials of Strength Training and Conditioning
MOVEMENT_PRIORITY: Dict[str, int] = {
    "squat": 1,      # Highest priority - foundational movement
    "hinge": 2,      # Second priority - hip dominant
    "push": 3,       # Upper body push
    "pull": 4,       # Upper body pull
    "carry": 5,      # Loaded carries
    "lunge": 6,      # Unilateral lower body
    "curl": 7,       # Isolation - biceps
    "extension": 8,  # Isolation - triceps
    "raise": 9,      # Isolation - shoulders
    "fly": 10,       # Isolation - chest
    "crunch": 11,    # Isolation - abs
    "hold": 12,      # Isometric holds
}

# Workout duration thresholds (minutes)
# References: Schoenfeld (2016) - Optimal training duration
WORKOUT_DURATION_OPTIMAL = (45, 75)      # Optimal range
WORKOUT_DURATION_ACCEPTABLE = (30, 90)   # Acceptable but suboptimal
WORKOUT_DURATION_EXCESSIVE = 90          # Excessive - diminishing returns

# Set execution and transition times (seconds) for duration estimation
SET_EXECUTION_SECONDS = 45  # Average time to complete a set
TRANSITION_SECONDS = 30      # Time between exercises (setup, walk, etc.)

# Balance ratio targets
# References: Contreras, Helms - Push/pull balance for shoulder health
PUSH_PULL_RATIO_TARGET = 1.0           # 1:1 optimal ratio
PUSH_PULL_RATIO_TOLERANCE = 0.2       # +/- 20% acceptable

# Upper/Lower ratio is context-dependent (can be adjusted for focus)
# Default is 1:1 for balanced training
UPPER_LOWER_RATIO_TARGET = 1.0
UPPER_LOWER_RATIO_TOLERANCE = 0.3     # More flexible than push/pull

# Antagonist muscle pairs are now stored in the database via antagonist_id relationship
# This comment is kept for reference - query MuscleGroupModel.antagonist instead

# ==============================
# ENHANCED PLAN ANALYZER CONSTANTS
# ==============================

# Effective Sets Threshold
# Only sets close to failure (RIR 0-4) count toward MEV/MRV landmarks
# References: Schoenfeld et al. (2017) - Volume landmarks research
EFFECTIVE_SET_RIR_THRESHOLD = 4  # RIR 0-4 = fully effective, RIR 5-6 = partially effective, RIR 7+ = not effective

# CNS Fatigue Tracking
# Movement patterns that cause systemic (CNS) fatigue vs local (muscular) fatigue
# References: Zourdos et al. (2016) - CNS fatigue in resistance training
CNS_HEAVY_PATTERNS: List[str] = ["squat", "hinge"]  # Highest CNS demand
CNS_MODERATE_PATTERNS: List[str] = ["pull", "push"]  # Moderate CNS demand
CNS_LIGHT_PATTERNS: List[str] = ["curl", "extension", "raise", "fly", "crunch"]  # Minimal CNS demand

# CNS Recovery Requirements
CNS_RECOVERY_HOURS_HEAVY = 72      # Minimum hours between heavy CNS-demanding sessions
CNS_RECOVERY_HOURS_MODERATE = 48   # Minimum hours between moderate CNS-demanding sessions

# Systemic Fatigue Accumulation Rates
# These values are per set - CNS fatigue scales with volume
CNS_FATIGUE_PER_HEAVY_COMPOUND = 0.3      # Fatigue units per set of heavy compound exercise
CNS_FATIGUE_PER_MODERATE_COMPOUND = 0.15  # Fatigue units per set of moderate compound exercise
CNS_FATIGUE_RECOVERY_PER_REST_DAY = 0.5   # Fatigue recovery per rest day (50% reduction)

# Training-Type-Specific Exercise Ordering Rules
# Strength: Prioritize neurological freshness (CNS-demanding exercises first)
STRENGTH_ORDER_PRIORITY: Dict[str, int] = {
    "power": 1,              # Explosive movements when CNS is fresh
    "compound_heavy": 2,     # Heavy compounds early (squats, deadlifts)
    "compound_moderate": 3,  # Moderate compounds
    "isolation": 4,          # Isolation work at end
}

# Hypertrophy: Prioritize metabolic stress (allows pre-exhaust, metabolic finishers)
HYPERTROPHY_ORDER_PRIORITY: Dict[str, int] = {
    "compound": 1,           # Compounds first (still important)
    "isolation_pre_exhaust": 2,  # Isolation before compound OK for target muscle
    "isolation_finisher": 3,     # High-rep isolations at end for metabolic stress
}

# Pre-exhaust rules for hypertrophy (isolation before compound for same muscle)
HYPERTROPHY_PRE_EXHAUST_ALLOWED = True  # Allows isolation before compound for same muscle group
STRENGTH_PRE_EXHAUST_ALLOWED = False    # Strength training: compounds must come first

# ==============================
# FOCUS AREA & EXERCISE TIER CONSTANTS
# ==============================

# Maximum focus areas allowed (prevents "select all" scenarios)
MAX_FOCUS_AREAS = 3

# Tier 1: Spinal loading exercises - ALWAYS first (subset of compound_heavy)
# These exercises cause systemic fatigue and injury risk if performed when fatigued
TIER_1_SPINAL_PATTERNS: List[str] = [
    "squat", "deadlift", "clean", "snatch", "jerk", "good morning"
]

# Tier 5: Core/stabilizers - ALWAYS last (subset of isolation)
# Training core first destabilizes the spine for the rest of the workout
# Even if core is a focus area, it should be trained last
TIER_5_CORE_PATTERNS: List[str] = [
    "plank", "crunch", "ab", "core", "twist", "pallof", "dead bug", "bird dog"
]

# Tier mapping from intensityCategory (when not edge case)
# Uses existing database field: compound_heavy, compound_moderate, isolation
INTENSITY_CATEGORY_TIER_MAP: Dict[ExerciseIntensityCategory, int] = {
    ExerciseIntensityCategory.COMPOUND_HEAVY: 2,    # Primary compounds (unless Tier 1 pattern)
    ExerciseIntensityCategory.COMPOUND_MODERATE: 3, # Secondary compounds
    ExerciseIntensityCategory.ISOLATION: 4,         # Standard isolation (unless Tier 5 pattern)
}

# Focus bonus (subtracted from score for within-tier priority)
# Lower score = earlier in workout
FOCUS_TIER_BONUS = 10  # Focus exercises sort earlier within same tier

# Focus area modifiers for recovery and prescription
FOCUS_AREA_RECOVERY_BONUS = 12  # Additional recovery hours for focus muscles
FOCUS_AREA_RPE_BONUS = 0.5  # Allow +0.5 RPE for focus muscle exercises

# ==============================
# PLATEAU DETECTION CONSTANTS
# ==============================

# Plateau detection thresholds
PLATEAU_VOLUME_IMPROVEMENT_THRESHOLD = 0.02  # <2% improvement = plateau
PLATEAU_RPE_INCREASE_THRESHOLD = 0.5  # RPE increase >0.5 with same/lower volume = struggling
PLATEAU_MIN_SESSIONS = 3  # Minimum sessions needed to detect plateau

# Volume cycling (overreach) parameters
OVERREACH_VOLUME_MULTIPLIER = 1.15  # 115% of MRV for overreach
OVERREACH_DURATION_WEEKS_BEGINNER = 1
OVERREACH_DURATION_WEEKS_ADVANCED = 2

# Constraint-based optimization limits
CONSTRAINT_ACWR_MIN = 0.8
CONSTRAINT_ACWR_MAX = 1.3
CONSTRAINT_CNS_FATIGUE_MAX = 0.8  # Max CNS fatigue before constraint violation
CONSTRAINT_MIN_VOLUME_MULT = 0.7  # Minimum volume multiplier
CONSTRAINT_MIN_INTENSITY_MULT = 0.8  # Minimum intensity multiplier

# ==============================
# RECOVERY AND READINESS THRESHOLDS
# ==============================

# Readiness score thresholds
LOW_READINESS_THRESHOLD = 0.7  # Below this = poor recovery
EXCELLENT_READINESS_THRESHOLD = 0.85  # Above this = excellent recovery
CRITICAL_READINESS_THRESHOLD = 0.4  # Below this = critical, immediate deload needed
READINESS_DELOAD_THRESHOLD = 0.5  # Below this for consecutive days triggers deload

# Recovery-based adjustment multipliers
POOR_RECOVERY_VOLUME_REDUCTION = 0.95  # Reduce volume by 5% when recovery is poor
POOR_RECOVERY_INTENSITY_REDUCTION = 0.98  # Reduce intensity by 2% when recovery is poor
EXCELLENT_RECOVERY_VOLUME_INCREASE = 1.02  # Increase volume by 2% when recovery is excellent

# ==============================
# ACWR (ACUTE:CHRONIC WORKLOAD RATIO) THRESHOLDS
# ==============================

# ACWR safe zone (Gabbett, 2016)
ACWR_SAFE_ZONE_MIN = 0.8  # Minimum safe ACWR
ACWR_SAFE_ZONE_MAX = 1.3  # Maximum safe ACWR
ACWR_HIGH_RISK_THRESHOLD = 1.5  # Above this = high injury risk, deload recommended
ACWR_UNDERTRAINING_THRESHOLD = 0.8  # Below this = undertraining (not a deload trigger)

# ==============================
# DELOAD MULTIPLIERS
# ==============================

# Deload week multipliers
DELOAD_VOLUME_MULTIPLIER = 0.5  # 50% volume during deload
DELOAD_INTENSITY_MULTIPLIER = 0.9  # 90% intensity during deload

# Extended break detraining multipliers
EXTENDED_BREAK_7_13_DAYS_VOLUME = 0.85  # 15% reduction for 7-13 day breaks
EXTENDED_BREAK_7_13_DAYS_INTENSITY = 0.85
EXTENDED_BREAK_14_20_DAYS_VOLUME = 0.75  # 25% reduction for 14-20 day breaks
EXTENDED_BREAK_14_20_DAYS_INTENSITY = 0.75
EXTENDED_BREAK_21_PLUS_DAYS_VOLUME = 0.60  # 40% reduction for 21+ day breaks
EXTENDED_BREAK_21_PLUS_DAYS_INTENSITY = 0.60

# ==============================
# ML CONFIDENCE THRESHOLDS
# ==============================

# ML prediction confidence thresholds
ML_HIGH_CONFIDENCE_THRESHOLD = 0.7  # High confidence threshold
ML_MEDIUM_CONFIDENCE_THRESHOLD = 0.5  # Medium confidence threshold
ML_LOW_CONFIDENCE_THRESHOLD = 0.3  # Low confidence threshold

# ML uncertainty thresholds
ML_LOW_UNCERTAINTY_THRESHOLD = 0.1  # Low uncertainty threshold
ML_MEDIUM_UNCERTAINTY_THRESHOLD = 0.15  # Medium uncertainty threshold
ML_HIGH_UNCERTAINTY_THRESHOLD = 0.2  # High uncertainty threshold

# ML prediction weights (for hybrid ML + rules)
ML_HIGH_CONFIDENCE_WEIGHT = 0.8  # 80% ML when high confidence
ML_MEDIUM_CONFIDENCE_WEIGHT = 0.5  # 50% ML when medium confidence
ML_LOW_CONFIDENCE_WEIGHT = 0.3  # 30% ML when low confidence

# ==============================
# PROGRESSION MULTIPLIERS
# ==============================

# Volume estimation multiplier
VOLUME_ESTIMATION_MULTIPLIER = 1.05  # Estimate next volume as 105% of current

# Maximum adjustment multipliers (safety caps)
MAX_VOLUME_MULTIPLIER = 1.15  # Maximum volume increase per workout
MAX_INTENSITY_MULTIPLIER = 1.05  # Maximum intensity increase per workout
MIN_VOLUME_MULTIPLIER = 0.80  # Minimum volume multiplier
MIN_INTENSITY_MULTIPLIER = 0.85  # Minimum intensity multiplier

# Session RPE spike threshold
SESSION_RPE_SPIKE_THRESHOLD_PERCENT = 20  # 20% increase in sRPE triggers deload warning

# ==============================
# INJURY RISK ADJUSTMENT MULTIPLIERS
# ==============================

# Injury risk adjustment multipliers
INJURY_RISK_HIGH_VOLUME_MULTIPLIER = 0.5
INJURY_RISK_HIGH_INTENSITY_MULTIPLIER = 0.85
INJURY_RISK_MODERATE_VOLUME_MULTIPLIER = 0.8
INJURY_RISK_MODERATE_INTENSITY_MULTIPLIER = 0.95

# Additional recovery-based adjustment multipliers
POOR_READINESS_VOLUME_MULTIPLIER = 0.7
POOR_READINESS_INTENSITY_MULTIPLIER = 0.9
MODERATE_READINESS_VOLUME_MULTIPLIER = 0.85
MODERATE_READINESS_INTENSITY_MULTIPLIER = 0.95

# ==============================
# MUSCLE ROLE ACTIVATION WEIGHTS
# ==============================

# Muscle activation weights by role (for volume calculations)
# References: Contreras, Helms - Muscle activation research
MUSCLE_ROLE_WEIGHTS = {
    "prime_mover": 0.85,    # Primary muscle activation
    "synergist": 0.55,      # Secondary muscle activation
    "stabilizer": 0.20      # Stabilizing muscle activation
}

# ==============================
# RPE DIFFERENCE THRESHOLDS FOR LOAD ADJUSTMENT
# ==============================

# RPE difference thresholds for optimal load calculation
RPE_DIFF_LARGE_THRESHOLD = 1.5      # Large RPE difference threshold
RPE_DIFF_SMALL_THRESHOLD = 0.5      # Small RPE difference threshold

# Load adjustment multipliers based on RPE difference
RPE_DIFF_LARGE_INCREASE_MULT = 2.0   # Large increase multiplier (too easy)
RPE_DIFF_SMALL_INCREASE_MULT = 0.5   # Small increase multiplier (perfect)
RPE_DIFF_LARGE_DECREASE_MULT = 1.5   # Large decrease multiplier (too hard)
RPE_DIFF_SMALL_DECREASE_MULT = 0.75  # Small decrease multiplier (slightly too hard)

# ==============================
# RECOVERY-BASED SET ADJUSTMENTS
# ==============================

# Recovery score thresholds for set adjustments
POOR_RECOVERY_THRESHOLD = 0.4        # Below this = poor recovery
EXCELLENT_RECOVERY_THRESHOLD = 0.7  # Above this = excellent recovery

# Set adjustment values based on recovery
POOR_RECOVERY_SET_REDUCTION_LARGE = -2  # Large reduction for poor recovery
POOR_RECOVERY_SET_REDUCTION_SMALL = -1  # Small reduction for poor recovery
EXCELLENT_RECOVERY_SET_INCREASE = 1      # Increase for excellent recovery

# ==============================
# FORM QUALITY SCORES AND THRESHOLDS
# ==============================

# Form quality to score mapping
FORM_SCORE_EXCELLENT = 1.0
FORM_SCORE_GOOD = 0.75
FORM_SCORE_FAIR = 0.5
FORM_SCORE_POOR = 0.25

# Form quality thresholds
FORM_DEGRADATION_THRESHOLD = 0.20  # 20% degradation within session
FORM_CHRONIC_ISSUE_THRESHOLD = 0.40  # 40% of sets fair/poor over 2 weeks
FORM_MIN_SCORE_FOR_PROGRESSION = 0.6  # Below "good" blocks progression

# ==============================
# RPE CALIBRATION CONSTANTS
# ==============================

# Calibration factor smoothing weights
RPE_CALIBRATION_NEW_FACTOR_WEIGHT = 0.7  # Weight for new calculation
RPE_CALIBRATION_OLD_FACTOR_WEIGHT = 0.3  # Weight for old factor (smoothing)

# Calibration factor bounds
RPE_CALIBRATION_FACTOR_MIN = 0.7  # Minimum calibration factor
RPE_CALIBRATION_FACTOR_MAX = 1.3  # Maximum calibration factor

# ==============================
# PR TRACKING CONSTANTS
# ==============================

# PR percentage by context
PR_DELOAD_PERCENTAGE = 0.75  # 75% of PR for deload weeks
PR_MAX_PERCENTAGE = 0.95  # Maximum PR percentage cap
PR_DEFAULT_PERCENTAGE = 0.80  # Default fallback percentage
PR_WEEK_ADJUSTMENT_CAP = 0.05  # Maximum weekly adjustment
PR_WEEK_ADJUSTMENT_RATE = 0.005  # Weekly adjustment increment

# ==============================
# DELOAD RPE CONSTANTS
# ==============================

# Target RPE during deload
DELOAD_TARGET_RPE = 6.0  # Very conservative RPE for deload weeks

# ==============================
# RPE THRESHOLDS FOR PERFORMANCE ANALYSIS
# ==============================

# High RPE thresholds for struggle detection and form quality
HIGH_RPE_THRESHOLD = 9.0  # High RPE threshold for form quality and performance concerns
STRUGGLE_RPE_THRESHOLD = 9.5  # RPE threshold indicating struggle/struggling
LOW_RPE_THRESHOLD = 7.0  # Low RPE threshold (too easy)

# ==============================
# ML RECOMMENDER ADJUSTMENT MULTIPLIERS
# ==============================

# ML recommender adjustment multipliers for high/low RPE
ML_HIGH_RPE_VOLUME_MULT = 0.95  # Volume reduction for high RPE
ML_HIGH_RPE_INTENSITY_MULT = 0.95  # Intensity reduction for high RPE
ML_LOW_RPE_VOLUME_MULT = 1.05  # Volume increase for low RPE
ML_LOW_RPE_INTENSITY_MULT = 1.05  # Intensity increase for low RPE

# Conservative ML adjustments (smaller changes)
ML_CONSERVATIVE_HIGH_RPE_VOLUME_MULT = 0.97  # Conservative volume reduction
ML_CONSERVATIVE_HIGH_RPE_INTENSITY_MULT = 0.97  # Conservative intensity reduction
ML_CONSERVATIVE_LOW_RPE_VOLUME_MULT = 1.03  # Conservative volume increase
ML_CONSERVATIVE_LOW_RPE_INTENSITY_MULT = 1.03  # Conservative intensity increase

# ML default multipliers
ML_DEFAULT_STRENGTH_INTENSITY_MULT = 0.95  # Default intensity multiplier for strength
ML_DEFAULT_HYPERTROPHY_VOLUME_MULT = 0.95  # Default volume multiplier for hypertrophy

# ==============================
# RECOVERY ANALYZER CONSTANTS
# ==============================

# Duration scoring
DURATION_SCORE_DEFAULT = 0.75  # Default duration score
ADVANCED_RECOVERY_MODIFIER = 0.85  # Recovery modifier for advanced athletes

# Training age recovery boosts
TRAINING_AGE_EXPERIENCED_THRESHOLD = 5  # Years to be considered experienced
TRAINING_AGE_VETERAN_THRESHOLD = 10  # Years to be considered veteran
TRAINING_AGE_BOOST_CAP = 0.05  # Maximum training age boost (5%)
TRAINING_AGE_BOOST_RATE = 0.01  # Boost per year of training

# Age offset for experienced athletes
AGE_PENALTY_OFFSET_EXPERIENCED = 0.1  # 10% offset for experienced
AGE_PENALTY_OFFSET_VETERAN = 0.2  # 20% offset for veteran
AGE_PENALTY_OFFSET_RATE_EXPERIENCED = 0.01  # 1% per year over threshold
AGE_PENALTY_OFFSET_RATE_VETERAN = 0.02  # 2% per year over threshold

# Combined modifier clamp
RECOVERY_MODIFIER_MIN = 0.7  # Minimum recovery modifier
RECOVERY_MODIFIER_MAX = 1.2  # Maximum recovery modifier

# ==============================
# WARMUP SET PERCENTAGES
# ==============================

# Warmup intensity adjustment
WARMUP_MAX_WEIGHT_PERCENTAGE = 0.95  # Maximum warmup weight percentage cap
WARMUP_PEAK_INTENSITY_BOOST_MIN = 0.02  # Minimum intensity boost for peak weeks
WARMUP_PEAK_INTENSITY_BOOST_MAX = 0.05  # Maximum intensity boost for peak weeks
WARMUP_EARLY_INTENSITY_REDUCTION_MIN = 0.01  # Minimum reduction for early weeks
WARMUP_EARLY_INTENSITY_REDUCTION_MAX = 0.02  # Maximum reduction for early weeks
WARMUP_PEAK_PHASE_THRESHOLD = 0.8  # Sets range position threshold for peak
WARMUP_EARLY_PHASE_THRESHOLD = 0.2  # Sets range position threshold for early
WARMUP_MIN_WEIGHT_PERCENTAGE = 0.50  # Minimum warmup weight percentage

# ==============================
# PR PERCENTAGE BY PHASE
# ==============================

# Percentage of PR to use by training phase
PR_ACCUMULATION_PERCENTAGE = 0.80  # 80% of PR during accumulation
PR_INTENSIFICATION_PERCENTAGE = 0.85  # 85% of PR during intensification
PR_REALIZATION_PERCENTAGE = 0.90  # 90% of PR during realization (peak week)

# ==============================
# VOLUME MULTIPLIER THRESHOLDS
# ==============================

# Thresholds for volume change detection
VOLUME_MULTIPLIER_INCREASE_THRESHOLD = 1.05  # Threshold for volume increase
VOLUME_MULTIPLIER_DECREASE_THRESHOLD = 0.95  # Threshold for volume decrease
VOLUME_MULTIPLIER_SMALL_CHANGE = 1.03  # Small change threshold
VOLUME_MULTIPLIER_MINOR_DECREASE = 0.97  # Minor decrease threshold

# ==============================
# PERFORMANCE-BASED ADJUSTMENT MULTIPLIERS
# ==============================

# Performance level adjustment multipliers
PERFORMANCE_STRUGGLING_VOLUME_MULT = 0.85  # Volume reduction for struggling
PERFORMANCE_STRUGGLING_INTENSITY_MULT = 0.90  # Intensity reduction for struggling
PERFORMANCE_POOR_VOLUME_MULT = 0.98  # Volume reduction for poor performance
PERFORMANCE_POOR_INTENSITY_MULT = 0.98  # Intensity reduction for poor performance

# ==============================
# PROGRESSIVE OVERLOAD FINE-TUNING MULTIPLIERS
# ==============================

# Performance-based fine-tuning
INTENSITY_SMALL_INCREASE_MULT = 1.025  # Small intensity increase (2.5%)
INTENSITY_MEDIUM_INCREASE_MULT = 1.05  # Medium intensity increase (5%)
VOLUME_SMALL_INCREASE_MULT = 1.02  # Small volume increase (2%)
VOLUME_MEDIUM_INCREASE_MULT = 1.05  # Medium volume increase (5%)

INTENSITY_SMALL_DECREASE_MULT = 0.98  # Small intensity decrease (2%)
INTENSITY_MEDIUM_DECREASE_MULT = 0.95  # Medium intensity decrease (5%)
VOLUME_SMALL_DECREASE_MULT = 0.95  # Small volume decrease (5%)
VOLUME_MEDIUM_DECREASE_MULT = 0.90  # Medium volume decrease (10%)

# Phase adjustments
INTENSITY_PHASE_SMALL_INCREASE = 1.01  # Small phase-based intensity increase
VOLUME_PHASE_SMALL_DECREASE = 0.95  # Small phase-based volume decrease

# Form quality gate caps
FORM_GATE_INTENSITY_CAP = 0.95  # Cap intensity at 95% when form is poor
FORM_GATE_VOLUME_CAP = 0.95  # Cap volume at 95% when form is poor

# Conservative adjustment scaling
CONSERVATIVE_ADJUSTMENT_SCALING = 0.8  # Scale down adjustments for primary exercises

# ==============================
# VOLUME MANAGER CONSTANTS
# ==============================

# Volume position percentage calculations
VOLUME_PERCENTAGE_BELOW_MEV_SCALE = 50  # Scale factor for volume below MEV (0-50%)
VOLUME_PERCENTAGE_MEV_TO_MRV_BASE = 50  # Base percentage between MEV and MRV
VOLUME_PERCENTAGE_MEV_TO_MRV_SCALE = 50  # Scale factor for MEV to MRV range
VOLUME_PERCENTAGE_ABOVE_MRV_BASE = 100  # Base percentage above MRV
VOLUME_PERCENTAGE_ABOVE_MRV_SCALE = 50  # Scale factor for volume above MRV

# ==============================
# PERFORMANCE SCORE THRESHOLDS
# ==============================

# Performance score evaluation thresholds
PERFORMANCE_SCORE_POOR_THRESHOLD = 0.6  # Below this = poor performance
PERFORMANCE_SCORE_GOOD_THRESHOLD = 0.8  # Above this = good performance

# Struggle ratio thresholds
STRUGGLE_RATIO_FAILED_THRESHOLD = 0.5  # Above this = failed performance
STRUGGLE_RATIO_STRUGGLING_THRESHOLD = 0.3  # Above this = struggling performance

# Default readiness score
DEFAULT_READINESS_SCORE = 0.5  # Default readiness score when not available

# Hybrid training small adjustments
HYBRID_SMALL_ADJUSTMENT_MULT = 1.015  # Small adjustment multiplier for hybrid training

# Progression rate scaling factor
PROGRESSION_RATE_SCALING_FACTOR = 0.5  # Scale progression rate by this factor for on-target performance

# ==============================
# WAVE LOADING MULTIPLIERS
# ==============================

# Wave loading adjustments by week number
WAVE_WEEK_1_VOLUME_MULT = 1.0  # Baseline volume for week 1
WAVE_WEEK_1_INTENSITY_MULT = 1.0  # Baseline intensity for week 1
WAVE_WEEK_2_VOLUME_MULT = 1.10  # 10% volume increase for week 2
WAVE_WEEK_2_INTENSITY_MULT = 1.05  # 5% intensity increase for week 2
WAVE_WEEK_3_VOLUME_MULT = 1.05  # 5% volume increase for week 3 (step back from week 2)
WAVE_WEEK_3_INTENSITY_MULT = 1.03  # 3% intensity increase for week 3
WAVE_WEEK_4_PLUS_VOLUME_MULT = 1.15  # 15% volume increase for week 4+
WAVE_WEEK_4_PLUS_INTENSITY_MULT = 1.08  # 8% intensity increase for week 4+

# ==============================
# INTENSITY TECHNIQUE SERVICE CONSTANTS
# ==============================

# Plateau detection threshold
PLATEAU_IMPROVEMENT_THRESHOLD = 0.02  # 2% improvement threshold for plateau detection

# Struggling detection RPE threshold (lower than HIGH_RPE_THRESHOLD for early detection)
STRUGGLING_DETECTION_RPE_THRESHOLD = 8.0  # RPE threshold for struggling detection in intensity techniques

# MRV ceiling threshold
MRV_CEILING_THRESHOLD = 0.9  # 90% of MRV considered at ceiling

# Partial effectiveness weight for sets
PARTIAL_EFFECTIVE_SET_WEIGHT = 0.5  # Weight for RIR 5-6 sets (partially effective)

# ==============================
# PRESCRIPTION GENERATOR CONSTANTS
# ==============================

# Default microcycle RPE modifier fallback
MICROCYCLE_RPE_MODIFIER_DEFAULT = 0.5  # Default fallback when week modifier not found


