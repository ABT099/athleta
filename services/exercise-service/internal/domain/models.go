package domain

// Movement pattern names. These are the vocabulary of MovementPattern nodes
// in the graph; the inference rules branch on them.
const (
	PatternPush     = "push"
	PatternPull     = "pull"
	PatternSquat    = "squat"
	PatternHinge    = "hinge"
	PatternLunge    = "lunge"
	PatternCarry    = "carry"
	PatternRotation = "rotation"
)

// Muscle roles and their relative activation percentages.
const (
	RolePrimeMover = "prime_mover"
	RoleSynergist  = "synergist"
	RoleStabilizer = "stabilizer"
)

// ActivationForRole maps a muscle role to its relative activation percent.
func ActivationForRole(role string) int32 {
	switch role {
	case RolePrimeMover:
		return 85
	case RoleSynergist:
		return 55
	case RoleStabilizer:
		return 25
	default:
		return 0
	}
}

// Exercise types.
const (
	TypeCompound  = "compound"
	TypeIsolation = "isolation"
)

// Intensity (CNS demand) categories.
const (
	IntensityCompoundHeavy    = "compound_heavy"
	IntensityCompoundModerate = "compound_moderate"
	IntensityIsolation        = "isolation"
)

// Force vectors for push/pull patterns.
const (
	VectorHorizontal = "horizontal"
	VectorVertical   = "vertical"
)

// MuscleTarget is a muscle engaged by an exercise with its functional role.
type MuscleTarget struct {
	Name              string
	DisplayName       string
	Role              string
	ActivationPercent int32
}

// Attributes are the atomic modifiers an exercise is composed of.
// Empty string means "not applicable / not determined".
type Attributes struct {
	Equipment   string
	Laterality  string
	Angle       string
	Grip        string
	Tempo       string
	ForceVector string
}

// SafetyProfile holds derived safety/difficulty metrics.
type SafetyProfile struct {
	InjuryRiskLevel  float32
	ComplexityScore  float32
	JointStressAreas []string
}

// Exercise is the full structured representation of an exercise.
type Exercise struct {
	ID                int32
	Name              string
	MovementPattern   string
	ExerciseType      string
	IntensityCategory string
	Attributes        Attributes
	Muscles           []MuscleTarget
	Safety            SafetyProfile
}

// Resolution describes how an input name was resolved.
type Resolution int

const (
	ResolutionMatched Resolution = iota + 1
	ResolutionInferred
)

// InferredExercise pairs a resolved exercise with how it was resolved.
type InferredExercise struct {
	Exercise      *Exercise
	RequestedName string
	Resolution    Resolution
	Confidence    float32
}

// Substitution is a scored replacement candidate for an exercise.
type Substitution struct {
	Exercise *Exercise
	Score    float32
	Reason   string
}

// SubstitutionFilters constrain substitution candidates.
type SubstitutionFilters struct {
	ExcludeJointStress []string
	ExcludeExerciseIDs []int32
	Limit              int
}

// SubstitutionCandidate is an exercise structurally related to another,
// described by raw graph facts. The scoring policy (how facts become a
// number) lives in the scoring layer — neither in the graph adapter nor in
// Cypher — so all weighting is stated in one place.
type SubstitutionCandidate struct {
	Exercise *Exercise
	// SamePattern: candidate follows the same movement pattern.
	SamePattern bool
	// RelatedPatternWeight: RELATED_TO edge weight when patterns differ but
	// relate (e.g. squat<->lunge); 0 when same or unrelated.
	RelatedPatternWeight float64
	// SameEquipment: candidate uses the same equipment.
	SameEquipment bool
	// SimilarEquipment: a SIMILAR_TO equipment edge exists (and equipment differs).
	SimilarEquipment bool
}

// Muscle size classes.
const (
	SizeSmall  = "small"
	SizeMedium = "medium"
	SizeLarge  = "large"
)

// Muscle is a muscle group with its metadata (graph Muscle node).
type Muscle struct {
	Name             string
	DisplayName      string
	Size             string // small | medium | large
	RecoveryHours    int
	Antagonist       string // name of antagonist muscle, if any
	IsCompoundTarget bool   // primary target of compound lifts
}
