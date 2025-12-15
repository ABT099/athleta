package inference

import (
	"github.com/athleta/exercise-inference/internal/models"
)

// SafetyAnalyzer generates safety and difficulty metrics
type SafetyAnalyzer struct{}

// NewSafetyAnalyzer creates a new safety analyzer
func NewSafetyAnalyzer() *SafetyAnalyzer {
	return &SafetyAnalyzer{}
}

// GenerateSafetyMetrics auto-generates injury risk, complexity, joint stress, and intensity
func (s *SafetyAnalyzer) GenerateSafetyMetrics(pattern string, modifiers models.ExerciseModifiers, exerciseType string) models.SafetyMetrics {
	return models.SafetyMetrics{
		InjuryRiskLevel:   s.calculateInjuryRisk(pattern, modifiers, exerciseType),
		ComplexityScore:   s.calculateComplexity(pattern, modifiers, exerciseType),
		JointStressAreas:  s.inferJointStress(pattern, modifiers),
		IntensityCategory: s.determineIntensity(pattern, modifiers, exerciseType),
	}
}

// calculateInjuryRisk determines injury risk level (1.0 = low, 2.0 = medium, 3.0 = high)
func (s *SafetyAnalyzer) calculateInjuryRisk(pattern string, modifiers models.ExerciseModifiers, exerciseType string) float32 {
	baseRisk := float32(1.0)
	
	// Pattern-based risk
	patternRisk := map[string]float32{
		"hinge":    3.0, // Deadlifts - high spinal load
		"squat":    2.5, // Squats - moderate-high load
		"push":     2.0, // Pressing - shoulder stress
		"pull":     2.0, // Pulling - shoulder/back stress
		"lunge":    1.5, // Lunges - lower risk
		"carry":    2.0, // Loaded carries - spinal load
		"rotation": 1.5, // Core work - lower risk
	}
	
	if risk, ok := patternRisk[pattern]; ok {
		baseRisk = risk
	}
	
	// Modifier adjustments
	if modifiers.Angle == "overhead" {
		baseRisk += 0.5 // Overhead work increases shoulder risk
	}
	
	if modifiers.Implement == "barbell" && (pattern == "hinge" || pattern == "squat") {
		baseRisk += 0.5 // Heavy barbell compounds are higher risk
	}
	
	if modifiers.Implement == "machine" {
		baseRisk -= 0.5 // Machines reduce risk (fixed path)
	}
	
	if modifiers.Laterality == "unilateral" {
		baseRisk -= 0.3 // Unilateral reduces absolute load
	}
	
	// Clamp between 1.0 and 3.0
	if baseRisk < 1.0 {
		baseRisk = 1.0
	}
	if baseRisk > 3.0 {
		baseRisk = 3.0
	}
	
	return baseRisk
}

// calculateComplexity determines complexity score (0.0-1.0)
func (s *SafetyAnalyzer) calculateComplexity(pattern string, modifiers models.ExerciseModifiers, exerciseType string) float32 {
	baseComplexity := float32(0.5)
	
	// Pattern-based complexity
	patternComplexity := map[string]float32{
		"hinge":    0.8, // Deadlifts require technique
		"squat":    0.7, // Squats require coordination
		"push":     0.6, // Pressing moderately complex
		"pull":     0.6, // Pulling moderately complex
		"lunge":    0.5, // Lunges moderate
		"carry":    0.4, // Carries simple
		"rotation": 0.3, // Core work simple
	}
	
	if complexity, ok := patternComplexity[pattern]; ok {
		baseComplexity = complexity
	}
	
	// Implement adjustments
	if modifiers.Implement == "barbell" {
		baseComplexity += 0.2 // Barbell requires more coordination
	} else if modifiers.Implement == "machine" {
		baseComplexity -= 0.2 // Machines simplify movement
	} else if modifiers.Implement == "cable" {
		baseComplexity -= 0.1 // Cables slightly simpler
	}
	
	// Laterality adjustments
	if modifiers.Laterality == "unilateral" {
		baseComplexity += 0.1 // Unilateral requires balance
	}
	
	// Tempo adjustments
	if modifiers.Tempo == "pause" || modifiers.Tempo == "tempo" {
		baseComplexity += 0.1 // Tempo control adds complexity
	}
	
	// Clamp between 0.0 and 1.0
	if baseComplexity < 0.0 {
		baseComplexity = 0.0
	}
	if baseComplexity > 1.0 {
		baseComplexity = 1.0
	}
	
	return baseComplexity
}

// inferJointStress determines which joints are stressed
func (s *SafetyAnalyzer) inferJointStress(pattern string, modifiers models.ExerciseModifiers) []string {
	joints := []string{}
	
	switch pattern {
	case "push":
		joints = append(joints, "shoulder", "elbow")
		if modifiers.Angle == "overhead" {
			// Overhead has more shoulder stress
			joints = []string{"shoulder", "elbow"}
		}
		
	case "pull":
		joints = append(joints, "shoulder", "elbow")
		if pattern == "hinge" {
			joints = append(joints, "lower_back")
		}
		
	case "squat":
		joints = append(joints, "knee", "hip", "lower_back")
		
	case "hinge":
		joints = append(joints, "lower_back", "hip", "knee")
		
	case "lunge":
		joints = append(joints, "knee", "hip", "ankle")
		
	case "carry":
		joints = append(joints, "shoulder", "lower_back", "hip")
		
	case "rotation":
		joints = append(joints, "lower_back")
	}
	
	return joints
}

// determineIntensity determines CNS demand category
func (s *SafetyAnalyzer) determineIntensity(pattern string, modifiers models.ExerciseModifiers, exerciseType string) string {
	// Isolation exercises are always isolation category
	if exerciseType == "isolation" {
		return "isolation"
	}
	
	// Heavy compound lifts
	heavyPatterns := map[string]bool{
		"squat": true,
		"hinge": true,
	}
	
	if heavyPatterns[pattern] && modifiers.Implement == "barbell" {
		return "compound_heavy"
	}
	
	// Moderate compound lifts
	if exerciseType == "compound" {
		// Machine compounds are moderate
		if modifiers.Implement == "machine" {
			return "compound_moderate"
		}
		
		// Dumbbell/kettlebell compounds are moderate
		if modifiers.Implement == "dumbbell" || modifiers.Implement == "kettlebell" {
			return "compound_moderate"
		}
		
		// Push/pull patterns with barbell are moderate (unless squat/hinge)
		if pattern == "push" || pattern == "pull" {
			if modifiers.Implement == "barbell" {
				return "compound_heavy"
			}
			return "compound_moderate"
		}
		
		// Default compound
		return "compound_moderate"
	}
	
	return "isolation"
}

