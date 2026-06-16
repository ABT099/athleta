package inference

import (
	"github.com/athleta/exercise-service/internal/domain"
)

// SafetyAnalyzer derives safety and difficulty metrics from a parsed exercise.
type SafetyAnalyzer struct{}

// NewSafetyAnalyzer creates a new safety analyzer.
func NewSafetyAnalyzer() *SafetyAnalyzer {
	return &SafetyAnalyzer{}
}

// Analyze derives injury risk, complexity, joint stress, and intensity.
func (s *SafetyAnalyzer) Analyze(parsed *ParsedExercise) domain.SafetyProfile {
	return domain.SafetyProfile{
		InjuryRiskLevel:  s.injuryRisk(parsed),
		ComplexityScore:  s.complexity(parsed),
		JointStressAreas: s.jointStress(parsed),
	}
}

// injuryRisk is on a 1.0 (low) to 3.0 (high) scale.
func (s *SafetyAnalyzer) injuryRisk(parsed *ParsedExercise) float32 {
	if parsed.ExerciseType == domain.TypeIsolation {
		risk := float32(1.0)
		if parsed.Modifiers.Angle == "overhead" {
			risk += 0.5
		}
		return risk
	}

	risk := float32(1.0)
	switch parsed.MovementPattern {
	case domain.PatternHinge:
		risk = 3.0 // high spinal load
	case domain.PatternSquat:
		risk = 2.5
	case domain.PatternPush, domain.PatternPull, domain.PatternCarry:
		risk = 2.0
	case domain.PatternLunge, domain.PatternRotation:
		risk = 1.5
	}

	if parsed.Modifiers.Angle == "overhead" || parsed.Modifiers.ForceVector == domain.VectorVertical {
		risk += 0.5 // overhead work increases shoulder risk
	}
	if parsed.Modifiers.Equipment == "barbell" &&
		(parsed.MovementPattern == domain.PatternHinge || parsed.MovementPattern == domain.PatternSquat) {
		risk += 0.5 // heavy barbell compounds
	}
	if parsed.Modifiers.Equipment == "machine" {
		risk -= 0.5 // fixed movement path
	}
	if parsed.Modifiers.Laterality == "unilateral" {
		risk -= 0.3 // lower absolute load
	}

	return clamp(risk, 1.0, 3.0)
}

// complexity is on a 0.0 to 1.0 scale.
func (s *SafetyAnalyzer) complexity(parsed *ParsedExercise) float32 {
	complexity := float32(0.5)

	if parsed.ExerciseType == domain.TypeIsolation {
		complexity = 0.2
	} else {
		switch parsed.MovementPattern {
		case domain.PatternHinge:
			complexity = 0.8
		case domain.PatternSquat:
			complexity = 0.7
		case domain.PatternPush, domain.PatternPull:
			complexity = 0.6
		case domain.PatternLunge:
			complexity = 0.5
		case domain.PatternCarry:
			complexity = 0.4
		case domain.PatternRotation:
			complexity = 0.3
		}
	}

	switch parsed.Modifiers.Equipment {
	case "barbell":
		complexity += 0.2
	case "machine":
		complexity -= 0.2
	case "cable":
		complexity -= 0.1
	}

	if parsed.Modifiers.Laterality == "unilateral" {
		complexity += 0.1
	}
	if parsed.Modifiers.Tempo == "pause" || parsed.Modifiers.Tempo == "tempo" {
		complexity += 0.1
	}

	return clamp(complexity, 0.0, 1.0)
}

func (s *SafetyAnalyzer) jointStress(parsed *ParsedExercise) []string {
	if parsed.ExerciseType == domain.TypeIsolation {
		return isolationJointStress(parsed.IsolationTarget)
	}

	switch parsed.MovementPattern {
	case domain.PatternPush:
		return []string{"shoulder", "elbow"}
	case domain.PatternPull:
		joints := []string{"shoulder", "elbow"}
		// Bent-over free-weight rows load the lower back.
		if parsed.Modifiers.ForceVector == domain.VectorHorizontal &&
			(parsed.Modifiers.Equipment == "barbell" || parsed.Modifiers.Equipment == "dumbbell") {
			joints = append(joints, "lower_back")
		}
		return joints
	case domain.PatternSquat:
		return []string{"knee", "hip", "lower_back"}
	case domain.PatternHinge:
		return []string{"lower_back", "hip", "knee"}
	case domain.PatternLunge:
		return []string{"knee", "hip", "ankle"}
	case domain.PatternCarry:
		return []string{"shoulder", "lower_back", "hip"}
	case domain.PatternRotation:
		return []string{"lower_back"}
	}

	return nil
}

func isolationJointStress(target string) []string {
	switch target {
	case "biceps", "forearms":
		return []string{"elbow", "wrist"}
	case "triceps":
		return []string{"elbow"}
	case "lateral_delt", "anterior_delt", "posterior_delt", "chest", "lats", "upper_traps":
		return []string{"shoulder"}
	case "quadriceps":
		return []string{"knee"}
	case "hamstrings":
		return []string{"knee", "hip"}
	case "calves":
		return []string{"ankle"}
	case "abs":
		return []string{"lower_back"}
	case "erector_spinae":
		return []string{"lower_back", "hip"}
	default:
		return nil
	}
}

// IntensityCategory determines the CNS demand category.
func (s *SafetyAnalyzer) IntensityCategory(parsed *ParsedExercise) string {
	if parsed.ExerciseType == domain.TypeIsolation {
		return domain.IntensityIsolation
	}

	// All barbell-loaded primary compounds are CNS-heavy: squat and hinge
	// for axial load, push and pull for total load moved.
	if parsed.Modifiers.Equipment == "barbell" {
		switch parsed.MovementPattern {
		case domain.PatternSquat, domain.PatternHinge, domain.PatternPush, domain.PatternPull:
			return domain.IntensityCompoundHeavy
		}
	}

	return domain.IntensityCompoundModerate
}

func clamp(v, lo, hi float32) float32 {
	if v < lo {
		return lo
	}
	if v > hi {
		return hi
	}
	return v
}
