package graph

// Static taxonomy seeded into the graph. Each node type earns its place by
// powering a traversal:
//
//   MovementPattern — substitution candidates and "all pressing movements"
//     style queries traverse FOLLOWS_PATTERN; RELATED_TO edges encode
//     cross-pattern affinity (squat<->lunge) so substitution doesn't need a
//     hard-coded similarity table in application code.
//   Muscle — "exercises sharing the same prime mover" is a 2-hop traversal
//     over TARGETS; ANTAGONIST_OF supports antagonist-pairing queries.
//     Size/recovery metadata lives here because it describes the muscle,
//     not any exercise.
//   Equipment — SIMILAR_TO edges make "same or interchangeable equipment"
//     a traversal instead of an application-side lookup table.
//   Joint — STRESSES edges turn athlete injury constraints ("avoid shoulder
//     stress") into a graph filter.
//
// Modifiers that are facts about a single exercise with no useful
// relationships (laterality, angle, grip, tempo, force vector) are plain
// Exercise properties. The old schema modeled them as ModifierCategory/
// Modifier nodes that no query ever traversed — that structure is gone.

// MuscleSeed describes a Muscle node.
type MuscleSeed struct {
	Name             string
	DisplayName      string
	Size             string
	RecoveryHours    int
	Antagonist       string // name of the antagonist muscle ("" when none)
	IsCompoundTarget bool   // primary target of compound lifts
}

// Muscles is the canonical muscle taxonomy (formerly the Postgres
// muscle_groups seed).
var Muscles = []MuscleSeed{
	{"upper_chest", "Upper Chest", "large", 72, "mid_back", true},
	{"mid_chest", "Mid Chest", "large", 72, "mid_back", true},
	{"lower_chest", "Lower Chest", "large", 72, "lats", true},
	{"lats", "Lats", "large", 72, "lower_chest", true},
	{"upper_traps", "Upper Traps", "medium", 60, "", false},
	{"mid_back", "Mid Back", "medium", 60, "mid_chest", true},
	{"lower_traps", "Lower Traps", "medium", 60, "", false},
	{"anterior_delt", "Front Delts", "medium", 60, "posterior_delt", true},
	{"lateral_delt", "Side Delts", "small", 48, "", false},
	{"posterior_delt", "Rear Delts", "small", 48, "anterior_delt", false},
	{"biceps", "Biceps", "small", 48, "triceps", false},
	{"triceps", "Triceps", "small", 48, "biceps", false},
	{"forearms", "Forearms", "small", 48, "", false},
	{"quadriceps", "Quadriceps", "large", 72, "hamstrings", true},
	{"hamstrings", "Hamstrings", "large", 72, "quadriceps", true},
	{"glutes", "Glutes", "large", 72, "hip_flexors", true},
	{"hip_flexors", "Hip Flexors", "medium", 60, "glutes", false},
	{"calves", "Calves", "small", 48, "", false},
	{"abs", "Abs", "medium", 48, "erector_spinae", false},
	{"erector_spinae", "Lower Back", "medium", 60, "abs", true},
}

// PatternSeed describes a MovementPattern node.
type PatternSeed struct {
	Name        string
	Description string
}

// Patterns is the canonical movement pattern taxonomy.
var Patterns = []PatternSeed{
	{"squat", "Knee-dominant lower body movements"},
	{"hinge", "Hip-dominant lower body movements"},
	{"push", "Horizontal and vertical pressing movements"},
	{"pull", "Horizontal and vertical pulling movements"},
	{"lunge", "Unilateral leg movements"},
	{"carry", "Loaded carries and locomotion"},
	{"rotation", "Core stability and rotational movements"},
}

// PatternRelation is a cross-pattern affinity used by substitution scoring.
type PatternRelation struct {
	From, To string
	Weight   float64
}

// PatternRelations encode which patterns can substitute for each other and
// how strongly.
var PatternRelations = []PatternRelation{
	{"squat", "lunge", 0.7},
	{"hinge", "squat", 0.3},
}

// EquipmentSeed describes an Equipment node.
type EquipmentSeed struct {
	Name     string
	Category string // free_weight | cable_machine | bodyweight
}

// Equipment is the canonical equipment taxonomy.
var Equipment = []EquipmentSeed{
	{"barbell", "free_weight"},
	{"dumbbell", "free_weight"},
	{"kettlebell", "free_weight"},
	{"landmine", "free_weight"},
	{"cable", "cable_machine"},
	{"machine", "cable_machine"},
	{"band", "cable_machine"},
	{"bodyweight", "bodyweight"},
}

// EquipmentRelation is an interchangeability edge between equipment types.
type EquipmentRelation struct {
	From, To string
}

// EquipmentRelations encode which equipment can stand in for which.
var EquipmentRelations = []EquipmentRelation{
	{"barbell", "dumbbell"},
	{"barbell", "kettlebell"},
	{"dumbbell", "kettlebell"},
	{"barbell", "landmine"},
	{"cable", "band"},
	{"cable", "machine"},
	{"band", "bodyweight"},
}

// Joints is the canonical joint vocabulary for STRESSES edges.
var Joints = []string{
	"shoulder", "elbow", "wrist", "knee", "hip", "ankle", "lower_back",
}
