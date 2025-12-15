package models

// ExerciseNode represents an exercise in Neo4j
type ExerciseNode struct {
	Name            string
	PostgresID      int
	Description     string
	Equipment       string
	MovementPattern string
	ExerciseType    string
	MuscleTargets   []MuscleTarget
	Archetypal      bool
}

// MuscleTarget represents a muscle with its role in an exercise
type MuscleTarget struct {
	MuscleName string
	Role       string // "prime_mover", "synergist", "stabilizer"
}

// ExerciseModifiers contains extracted modifiers from exercise name
type ExerciseModifiers struct {
	Implement   string // barbell, dumbbell, kettlebell, cable, machine, bodyweight, landmine, band
	Laterality  string // bilateral, unilateral, alternating, isometric_hold
	Angle       string // flat, incline, decline, overhead, floor_level
	GripStance  string // neutral, pronated, supinated, wide, narrow, staggered, split
	Plane       string // sagittal, frontal, transverse
	Tempo       string // eccentric_focus, explosive, tempo, pause, accommodating_resistance
}

// ParsedExercise represents the result of parsing an exercise name
type ParsedExercise struct {
	OriginalName    string
	MovementPattern string
	BaseExercise    string
	Modifiers       ExerciseModifiers
}

// ExerciseData represents complete exercise information with auto-generated metadata
type ExerciseData struct {
	Name              string
	Description       string
	Equipment         string
	MovementPattern   string
	ExerciseType      string
	InjuryRiskLevel   float32
	ComplexityScore   float32
	JointStressAreas  []string
	IntensityCategory string
	MuscleTargets     []MuscleTarget
	Modifiers         ExerciseModifiers
}

// SafetyMetrics contains auto-generated safety and difficulty metrics
type SafetyMetrics struct {
	InjuryRiskLevel   float32
	ComplexityScore   float32
	JointStressAreas  []string
	IntensityCategory string
}

