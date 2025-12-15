package inference

import (
	"github.com/athleta/exercise-inference/internal/models"
)

// RulesEngine applies biomechanical inference rules
type RulesEngine struct {
	parser *Parser
}

// NewRulesEngine creates a new rules engine
func NewRulesEngine() *RulesEngine {
	return &RulesEngine{
		parser: NewParser(),
	}
}

// InferMuscleTargets infers muscle targets based on movement pattern and modifiers
func (r *RulesEngine) InferMuscleTargets(pattern string, modifiers models.ExerciseModifiers) []models.MuscleTarget {
	targets := []models.MuscleTarget{}
	
	switch pattern {
	case "push":
		targets = r.inferPushMuscles(modifiers)
	case "pull":
		targets = r.inferPullMuscles(modifiers)
	case "squat":
		targets = r.inferSquatMuscles(modifiers)
	case "hinge":
		targets = r.inferHingeMuscles(modifiers)
	case "lunge":
		targets = r.inferLungeMuscles(modifiers)
	case "carry":
		targets = r.inferCarryMuscles(modifiers)
	case "rotation":
		targets = r.inferRotationMuscles(modifiers)
	default:
		// Unknown pattern - return empty
		return targets
	}
	
	// Apply modifier-based adjustments
	targets = r.applyModifierAdjustments(targets, modifiers)
	
	return targets
}

func (r *RulesEngine) inferPushMuscles(modifiers models.ExerciseModifiers) []models.MuscleTarget {
	targets := []models.MuscleTarget{}
	
	// Determine if horizontal or vertical push
	isVertical := modifiers.Angle == "overhead"
	
	if isVertical {
		// Vertical push (overhead press)
		targets = append(targets,
			models.MuscleTarget{MuscleName: "anterior_delt", Role: "prime_mover"},
			models.MuscleTarget{MuscleName: "lateral_delt", Role: "prime_mover"},
			models.MuscleTarget{MuscleName: "triceps", Role: "synergist"},
			models.MuscleTarget{MuscleName: "upper_chest", Role: "synergist"},
		)
	} else {
		// Horizontal push (bench press variations)
		if modifiers.Angle == "incline" {
			targets = append(targets,
				models.MuscleTarget{MuscleName: "upper_chest", Role: "prime_mover"},
				models.MuscleTarget{MuscleName: "anterior_delt", Role: "prime_mover"},
				models.MuscleTarget{MuscleName: "mid_chest", Role: "synergist"},
				models.MuscleTarget{MuscleName: "triceps", Role: "synergist"},
			)
		} else if modifiers.Angle == "decline" {
			targets = append(targets,
				models.MuscleTarget{MuscleName: "lower_chest", Role: "prime_mover"},
				models.MuscleTarget{MuscleName: "mid_chest", Role: "synergist"},
				models.MuscleTarget{MuscleName: "triceps", Role: "synergist"},
				models.MuscleTarget{MuscleName: "anterior_delt", Role: "synergist"},
			)
		} else {
			// Flat press
			targets = append(targets,
				models.MuscleTarget{MuscleName: "mid_chest", Role: "prime_mover"},
				models.MuscleTarget{MuscleName: "anterior_delt", Role: "synergist"},
				models.MuscleTarget{MuscleName: "triceps", Role: "synergist"},
				models.MuscleTarget{MuscleName: "upper_chest", Role: "stabilizer"},
			)
		}
	}
	
	// Always add core stabilizers for push movements
	targets = append(targets, models.MuscleTarget{MuscleName: "abs", Role: "stabilizer"})
	
	return targets
}

func (r *RulesEngine) inferPullMuscles(modifiers models.ExerciseModifiers) []models.MuscleTarget {
	targets := []models.MuscleTarget{}
	
	// Determine if horizontal or vertical pull
	isVertical := modifiers.Angle == "overhead" || modifiers.Implement == "pullup" || modifiers.Implement == "chinup"
	
	if isVertical {
		// Vertical pull (pull-ups, lat pulldowns)
		targets = append(targets,
			models.MuscleTarget{MuscleName: "lats", Role: "prime_mover"},
			models.MuscleTarget{MuscleName: "biceps", Role: "synergist"},
			models.MuscleTarget{MuscleName: "mid_back", Role: "synergist"},
			models.MuscleTarget{MuscleName: "posterior_delt", Role: "synergist"},
		)
	} else {
		// Horizontal pull (rows)
		targets = append(targets,
			models.MuscleTarget{MuscleName: "mid_back", Role: "prime_mover"},
			models.MuscleTarget{MuscleName: "lats", Role: "prime_mover"},
			models.MuscleTarget{MuscleName: "posterior_delt", Role: "synergist"},
			models.MuscleTarget{MuscleName: "biceps", Role: "synergist"},
		)
	}
	
	// Add stabilizers
	targets = append(targets,
		models.MuscleTarget{MuscleName: "erector_spinae", Role: "stabilizer"},
		models.MuscleTarget{MuscleName: "abs", Role: "stabilizer"},
	)
	
	return targets
}

func (r *RulesEngine) inferSquatMuscles(modifiers models.ExerciseModifiers) []models.MuscleTarget {
	return []models.MuscleTarget{
		{MuscleName: "quadriceps", Role: "prime_mover"},
		{MuscleName: "glutes", Role: "prime_mover"},
		{MuscleName: "hamstrings", Role: "synergist"},
		{MuscleName: "erector_spinae", Role: "stabilizer"},
		{MuscleName: "abs", Role: "stabilizer"},
		{MuscleName: "calves", Role: "stabilizer"},
	}
}

func (r *RulesEngine) inferHingeMuscles(modifiers models.ExerciseModifiers) []models.MuscleTarget {
	return []models.MuscleTarget{
		{MuscleName: "glutes", Role: "prime_mover"},
		{MuscleName: "hamstrings", Role: "prime_mover"},
		{MuscleName: "erector_spinae", Role: "prime_mover"},
		{MuscleName: "lats", Role: "synergist"},
		{MuscleName: "upper_traps", Role: "synergist"},
		{MuscleName: "forearms", Role: "synergist"},
		{MuscleName: "abs", Role: "stabilizer"},
	}
}

func (r *RulesEngine) inferLungeMuscles(modifiers models.ExerciseModifiers) []models.MuscleTarget {
	return []models.MuscleTarget{
		{MuscleName: "quadriceps", Role: "prime_mover"},
		{MuscleName: "glutes", Role: "prime_mover"},
		{MuscleName: "hamstrings", Role: "synergist"},
		{MuscleName: "calves", Role: "synergist"},
		{MuscleName: "abs", Role: "stabilizer"},
		{MuscleName: "erector_spinae", Role: "stabilizer"},
	}
}

func (r *RulesEngine) inferCarryMuscles(modifiers models.ExerciseModifiers) []models.MuscleTarget {
	return []models.MuscleTarget{
		{MuscleName: "forearms", Role: "prime_mover"},
		{MuscleName: "upper_traps", Role: "prime_mover"},
		{MuscleName: "abs", Role: "prime_mover"},
		{MuscleName: "erector_spinae", Role: "synergist"},
		{MuscleName: "glutes", Role: "synergist"},
		{MuscleName: "quadriceps", Role: "stabilizer"},
	}
}

func (r *RulesEngine) inferRotationMuscles(modifiers models.ExerciseModifiers) []models.MuscleTarget {
	return []models.MuscleTarget{
		{MuscleName: "abs", Role: "prime_mover"},
		{MuscleName: "erector_spinae", Role: "synergist"},
		{MuscleName: "glutes", Role: "stabilizer"},
	}
}

// ApplyModifierAdjustments applies modifier-based adjustments to muscle targets (exported for engine use)
func (r *RulesEngine) ApplyModifierAdjustments(targets []models.MuscleTarget, modifiers models.ExerciseModifiers) []models.MuscleTarget {
	return r.applyModifierAdjustments(targets, modifiers)
}

// applyModifierAdjustments applies modifier-based adjustments to muscle targets
func (r *RulesEngine) applyModifierAdjustments(targets []models.MuscleTarget, modifiers models.ExerciseModifiers) []models.MuscleTarget {
	// If unilateral, add anti-rotation stabilizers
	if modifiers.Laterality == "unilateral" {
		// Check if obliques already present
		hasObliques := false
		for _, t := range targets {
			if t.MuscleName == "obliques" {
				hasObliques = true
				break
			}
		}
		
		if !hasObliques {
			targets = append(targets, models.MuscleTarget{
				MuscleName: "abs",
				Role:       "stabilizer",
			})
		}
	}
	
	return targets
}

