package inference

import (
	"github.com/athleta/exercise-service/internal/domain"
)

// RulesEngine derives muscle targets from a parsed exercise.
type RulesEngine struct{}

// NewRulesEngine creates a new rules engine.
func NewRulesEngine() *RulesEngine {
	return &RulesEngine{}
}

// InferMuscleTargets infers muscle targets from the movement classification
// and modifiers. Display names and activation percentages are filled in
// later from the graph's muscle metadata.
func (r *RulesEngine) InferMuscleTargets(parsed *ParsedExercise) []domain.MuscleTarget {
	var targets []domain.MuscleTarget

	if parsed.ExerciseType == domain.TypeIsolation {
		targets = isolationMuscles(parsed.IsolationTarget)
	} else {
		switch parsed.MovementPattern {
		case domain.PatternPush:
			targets = pushMuscles(parsed)
		case domain.PatternPull:
			targets = pullMuscles(parsed)
		case domain.PatternSquat:
			targets = squatMuscles()
		case domain.PatternHinge:
			targets = hingeMuscles()
		case domain.PatternLunge:
			targets = lungeMuscles()
		case domain.PatternCarry:
			targets = carryMuscles()
		case domain.PatternRotation:
			targets = rotationMuscles()
		}
	}

	return r.applyModifierAdjustments(targets, parsed.Modifiers)
}

func t(name, role string) domain.MuscleTarget {
	return domain.MuscleTarget{Name: name, Role: role, ActivationPercent: domain.ActivationForRole(role)}
}

func pushMuscles(parsed *ParsedExercise) []domain.MuscleTarget {
	var targets []domain.MuscleTarget

	if parsed.Modifiers.ForceVector == domain.VectorVertical {
		targets = []domain.MuscleTarget{
			t("anterior_delt", domain.RolePrimeMover),
			t("lateral_delt", domain.RolePrimeMover),
			t("triceps", domain.RoleSynergist),
			t("upper_chest", domain.RoleSynergist),
		}
	} else {
		switch parsed.Modifiers.Angle {
		case "incline":
			targets = []domain.MuscleTarget{
				t("upper_chest", domain.RolePrimeMover),
				t("anterior_delt", domain.RolePrimeMover),
				t("mid_chest", domain.RoleSynergist),
				t("triceps", domain.RoleSynergist),
			}
		case "decline":
			targets = []domain.MuscleTarget{
				t("lower_chest", domain.RolePrimeMover),
				t("mid_chest", domain.RoleSynergist),
				t("triceps", domain.RoleSynergist),
				t("anterior_delt", domain.RoleSynergist),
			}
		default:
			targets = []domain.MuscleTarget{
				t("mid_chest", domain.RolePrimeMover),
				t("anterior_delt", domain.RoleSynergist),
				t("triceps", domain.RoleSynergist),
				t("upper_chest", domain.RoleStabilizer),
			}
		}
	}

	return append(targets, t("abs", domain.RoleStabilizer))
}

func pullMuscles(parsed *ParsedExercise) []domain.MuscleTarget {
	var targets []domain.MuscleTarget

	if parsed.Modifiers.ForceVector == domain.VectorVertical {
		targets = []domain.MuscleTarget{
			t("lats", domain.RolePrimeMover),
			t("biceps", domain.RoleSynergist),
			t("mid_back", domain.RoleSynergist),
			t("posterior_delt", domain.RoleSynergist),
		}
	} else {
		targets = []domain.MuscleTarget{
			t("mid_back", domain.RolePrimeMover),
			t("lats", domain.RolePrimeMover),
			t("posterior_delt", domain.RoleSynergist),
			t("biceps", domain.RoleSynergist),
		}
	}

	return append(targets,
		t("erector_spinae", domain.RoleStabilizer),
		t("abs", domain.RoleStabilizer),
	)
}

func squatMuscles() []domain.MuscleTarget {
	return []domain.MuscleTarget{
		t("quadriceps", domain.RolePrimeMover),
		t("glutes", domain.RolePrimeMover),
		t("hamstrings", domain.RoleSynergist),
		t("erector_spinae", domain.RoleStabilizer),
		t("abs", domain.RoleStabilizer),
		t("calves", domain.RoleStabilizer),
	}
}

func hingeMuscles() []domain.MuscleTarget {
	return []domain.MuscleTarget{
		t("glutes", domain.RolePrimeMover),
		t("hamstrings", domain.RolePrimeMover),
		t("erector_spinae", domain.RolePrimeMover),
		t("lats", domain.RoleSynergist),
		t("upper_traps", domain.RoleSynergist),
		t("forearms", domain.RoleSynergist),
		t("abs", domain.RoleStabilizer),
	}
}

func lungeMuscles() []domain.MuscleTarget {
	return []domain.MuscleTarget{
		t("quadriceps", domain.RolePrimeMover),
		t("glutes", domain.RolePrimeMover),
		t("hamstrings", domain.RoleSynergist),
		t("calves", domain.RoleSynergist),
		t("abs", domain.RoleStabilizer),
		t("erector_spinae", domain.RoleStabilizer),
	}
}

func carryMuscles() []domain.MuscleTarget {
	return []domain.MuscleTarget{
		t("forearms", domain.RolePrimeMover),
		t("upper_traps", domain.RolePrimeMover),
		t("abs", domain.RolePrimeMover),
		t("erector_spinae", domain.RoleSynergist),
		t("glutes", domain.RoleSynergist),
		t("quadriceps", domain.RoleStabilizer),
	}
}

func rotationMuscles() []domain.MuscleTarget {
	return []domain.MuscleTarget{
		t("abs", domain.RolePrimeMover),
		t("erector_spinae", domain.RoleSynergist),
		t("glutes", domain.RoleStabilizer),
	}
}

// isolationMuscles maps an isolation target key to its muscle composition.
func isolationMuscles(target string) []domain.MuscleTarget {
	switch target {
	case "biceps":
		return []domain.MuscleTarget{t("biceps", domain.RolePrimeMover), t("forearms", domain.RoleSynergist)}
	case "triceps":
		return []domain.MuscleTarget{t("triceps", domain.RolePrimeMover)}
	case "lateral_delt":
		return []domain.MuscleTarget{t("lateral_delt", domain.RolePrimeMover), t("anterior_delt", domain.RoleSynergist)}
	case "anterior_delt":
		return []domain.MuscleTarget{t("anterior_delt", domain.RolePrimeMover), t("lateral_delt", domain.RoleSynergist)}
	case "posterior_delt":
		return []domain.MuscleTarget{t("posterior_delt", domain.RolePrimeMover), t("mid_back", domain.RoleSynergist)}
	case "chest":
		return []domain.MuscleTarget{t("mid_chest", domain.RolePrimeMover), t("anterior_delt", domain.RoleSynergist)}
	case "quadriceps":
		return []domain.MuscleTarget{t("quadriceps", domain.RolePrimeMover)}
	case "hamstrings":
		return []domain.MuscleTarget{t("hamstrings", domain.RolePrimeMover)}
	case "calves":
		return []domain.MuscleTarget{t("calves", domain.RolePrimeMover)}
	case "upper_traps":
		return []domain.MuscleTarget{t("upper_traps", domain.RolePrimeMover), t("forearms", domain.RoleStabilizer)}
	case "abs":
		return []domain.MuscleTarget{t("abs", domain.RolePrimeMover), t("hip_flexors", domain.RoleSynergist)}
	case "erector_spinae":
		return []domain.MuscleTarget{t("erector_spinae", domain.RolePrimeMover), t("glutes", domain.RoleSynergist), t("hamstrings", domain.RoleSynergist)}
	case "lats":
		return []domain.MuscleTarget{t("lats", domain.RolePrimeMover), t("mid_chest", domain.RoleSynergist), t("triceps", domain.RoleSynergist)}
	case "forearms":
		return []domain.MuscleTarget{t("forearms", domain.RolePrimeMover)}
	default:
		// Unknown isolation movement: no muscles can be stated confidently.
		return nil
	}
}

func (r *RulesEngine) applyModifierAdjustments(targets []domain.MuscleTarget, modifiers domain.Attributes) []domain.MuscleTarget {
	// Unilateral work demands anti-rotation core stability.
	if modifiers.Laterality == "unilateral" {
		hasAbs := false
		for _, target := range targets {
			if target.Name == "abs" {
				hasAbs = true
				break
			}
		}
		if !hasAbs {
			targets = append(targets, t("abs", domain.RoleStabilizer))
		}
	}

	return targets
}
