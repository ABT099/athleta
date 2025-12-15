package inference

import (
	"context"
	"fmt"

	"github.com/athleta/exercise-inference/internal/models"
	"github.com/athleta/exercise-inference/internal/neo4j"
)

// Engine is the main inference engine that coordinates parsing, rules, and safety analysis
type Engine struct {
	parser         *Parser
	rules          *RulesEngine
	safety         *SafetyAnalyzer
	neo4jRepo      *neo4j.Repository
}

// NewEngine creates a new inference engine
func NewEngine(neo4jRepo *neo4j.Repository) *Engine {
	return &Engine{
		parser:    NewParser(),
		rules:     NewRulesEngine(),
		safety:    NewSafetyAnalyzer(),
		neo4jRepo: neo4jRepo,
	}
}

// InferExercise performs complete inference on an exercise name
func (e *Engine) InferExercise(ctx context.Context, name string) (*models.ExerciseData, error) {
	// Step 1: Parse the exercise name
	parsed := e.parser.ParseExerciseName(name)
	
	// Step 2: Determine exercise type
	exerciseType := e.parser.DetermineExerciseType(parsed.MovementPattern, parsed.Modifiers)
	
	// Step 3: Try to find archetypal exercise in Neo4j for better accuracy
	var muscles []models.MuscleTarget
	if archetypal, err := e.neo4jRepo.FindArchetypalExercise(ctx, parsed.MovementPattern, map[string]string{
		"implement":   parsed.Modifiers.Implement,
		"laterality":  parsed.Modifiers.Laterality,
		"angle":       parsed.Modifiers.Angle,
	}); err == nil && archetypal != nil {
		// Use muscles from archetypal exercise as base
		muscles = archetypal.MuscleTargets
		// Apply modifier-based adjustments
		muscles = e.rules.ApplyModifierAdjustments(muscles, parsed.Modifiers)
	} else {
		// Fall back to pure rule-based inference if no archetypal found
		muscles = e.rules.InferMuscleTargets(parsed.MovementPattern, parsed.Modifiers)
	}
	
	// Step 5: Generate safety metrics
	safetyMetrics := e.safety.GenerateSafetyMetrics(parsed.MovementPattern, parsed.Modifiers, exerciseType)
	
	// Step 6: Extract equipment
	equipment := e.extractEquipment(parsed.Modifiers)
	
	// Build complete exercise data
	exerciseData := &models.ExerciseData{
		Name:              name,
		Equipment:         equipment,
		MovementPattern:   parsed.MovementPattern,
		ExerciseType:      exerciseType,
		InjuryRiskLevel:   safetyMetrics.InjuryRiskLevel,
		ComplexityScore:   safetyMetrics.ComplexityScore,
		JointStressAreas:  safetyMetrics.JointStressAreas,
		IntensityCategory: safetyMetrics.IntensityCategory,
		MuscleTargets:     muscles,
		Modifiers:         parsed.Modifiers,
	}
	
	return exerciseData, nil
}

// BatchInferExercises performs inference on multiple exercises
func (e *Engine) BatchInferExercises(ctx context.Context, names []string) ([]*models.ExerciseData, error) {
	results := make([]*models.ExerciseData, 0, len(names))
	
	for _, name := range names {
		data, err := e.InferExercise(ctx, name)
		if err != nil {
			return nil, fmt.Errorf("failed to infer exercise %s: %w", name, err)
		}
		results = append(results, data)
	}
	
	return results, nil
}

// extractEquipment extracts equipment from modifiers
func (e *Engine) extractEquipment(modifiers models.ExerciseModifiers) string {
	if modifiers.Implement != "" && modifiers.Implement != "bodyweight" {
		return modifiers.Implement
	}
	return "bodyweight"
}

// SimilarityFilters contains filters for finding similar exercises
type SimilarityFilters struct {
	SameEquipment  bool
	SameLaterality bool
	SameAngle      bool
	Limit          int32
}

// FindSimilarExercises finds exercises with similar movement patterns and modifiers
func (e *Engine) FindSimilarExercises(ctx context.Context, exerciseName string, filters SimilarityFilters) ([]string, error) {
	// Convert filters to neo4j filters
	neo4jFilters := neo4j.SimilarityFilters{
		SameEquipment:  filters.SameEquipment,
		SameLaterality: filters.SameLaterality,
		SameAngle:      filters.SameAngle,
		Limit:          filters.Limit,
	}
	
	// Query Neo4j for similar exercises
	similarExercises, err := e.neo4jRepo.FindSimilarExercises(ctx, exerciseName, neo4jFilters)
	if err != nil {
		return nil, fmt.Errorf("failed to find similar exercises: %w", err)
	}
	
	return similarExercises, nil
}

