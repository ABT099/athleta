package neo4j

import (
	"context"
	"fmt"

	"github.com/athleta/exercise-inference/internal/models"
	"github.com/neo4j/neo4j-go-driver/v6/neo4j"
)

// Repository handles Neo4j database operations
type Repository struct {
	driver neo4j.Driver
}

// NewRepository creates a new Neo4j repository
func NewRepository(uri, username, password string) (*Repository, error) {
	driver, err := neo4j.NewDriverWithContext(uri, neo4j.BasicAuth(username, password, ""))
	if err != nil {
		return nil, fmt.Errorf("failed to create Neo4j driver: %w", err)
	}

	// Verify connectivity
	ctx := context.Background()
	if err := driver.VerifyConnectivity(ctx); err != nil {
		return nil, fmt.Errorf("failed to verify Neo4j connectivity: %w", err)
	}

	return &Repository{driver: driver}, nil
}

// Close closes the Neo4j driver
func (r *Repository) Close(ctx context.Context) error {
	return r.driver.Close(ctx)
}

// InitSchema initializes the Neo4j schema
func (r *Repository) InitSchema(ctx context.Context) error {
	return InitializeSchema(ctx, r.driver)
}

// CreateArchetypalExercise creates an archetypal exercise node with muscle targets
func (r *Repository) CreateArchetypalExercise(ctx context.Context, exercise *models.ExerciseNode) error {
	session := r.driver.NewSession(ctx, neo4j.SessionConfig{AccessMode: neo4j.AccessModeWrite})
	defer session.Close(ctx)

	query := `
		MATCH (pattern:Pattern {name: $pattern_name})
		MERGE (ex:Exercise {
			name: $name,
			archetypal: true,
			postgres_id: $postgres_id,
			equipment: $equipment,
			movement_pattern: $movement_pattern,
			exercise_type: $exercise_type
		})
		MERGE (pattern)-[:HAS_ARCHETYPE]->(ex)
		RETURN ex
	`

	params := map[string]interface{}{
		"pattern_name":     exercise.MovementPattern,
		"name":             exercise.Name,
		"postgres_id":      exercise.PostgresID,
		"equipment":        exercise.Equipment,
		"movement_pattern": exercise.MovementPattern,
		"exercise_type":    exercise.ExerciseType,
	}

	_, err := session.Run(ctx, query, params)
	if err != nil {
		return fmt.Errorf("failed to create archetypal exercise: %w", err)
	}

	// Link muscles with roles
	for _, muscle := range exercise.MuscleTargets {
		if err := r.linkMuscleToExercise(ctx, session, exercise.Name, muscle); err != nil {
			return err
		}
	}

	return nil
}

// linkMuscleToExercise creates a TARGETS relationship between exercise and muscle
func (r *Repository) linkMuscleToExercise(ctx context.Context, session neo4j.Session, exerciseName string, muscle models.MuscleTarget) error {
	query := `
		MATCH (ex:Exercise {name: $exercise_name})
		MERGE (m:Muscle {name: $muscle_name})
		MERGE (ex)-[:TARGETS {role: $role}]->(m)
	`

	params := map[string]interface{}{
		"exercise_name": exerciseName,
		"muscle_name":   muscle.MuscleName,
		"role":          muscle.Role,
	}

	_, err := session.Run(ctx, query, params)
	if err != nil {
		return fmt.Errorf("failed to link muscle to exercise: %w", err)
	}

	return nil
}

// FindArchetypalExercise finds an archetypal exercise by movement pattern and modifiers
func (r *Repository) FindArchetypalExercise(ctx context.Context, pattern string, modifiers map[string]string) (*models.ExerciseNode, error) {
	session := r.driver.NewSession(ctx, neo4j.SessionConfig{AccessMode: neo4j.AccessModeRead})
	defer session.Close(ctx)

	// Try to find an archetypal exercise that matches the pattern and key modifiers
	// Priority: exact equipment match > same angle > default for pattern
	query := `
		MATCH (pattern:Pattern {name: $pattern})-[:HAS_ARCHETYPE]->(ex:Exercise {archetypal: true})
		OPTIONAL MATCH (ex)-[t:TARGETS]->(m:Muscle)
		
		// Score based on modifier matches
		WITH ex, m, t,
		     CASE 
		       WHEN $equipment <> '' AND toLower(ex.equipment) = toLower($equipment) THEN 10
		       ELSE 0
		     END as equipment_score
		
		// Get the best matching exercise
		WITH ex, equipment_score, collect({muscle: m.name, role: t.role}) as muscles
		ORDER BY equipment_score DESC
		LIMIT 1
		
		RETURN ex.name as name, 
		       ex.equipment as equipment,
		       ex.movement_pattern as movement_pattern,
		       ex.exercise_type as exercise_type,
		       muscles
	`

	equipment := ""
	if val, ok := modifiers["implement"]; ok {
		equipment = val
	}

	params := map[string]interface{}{
		"pattern":   pattern,
		"equipment": equipment,
	}

	result, err := session.Run(ctx, query, params)
	if err != nil {
		return nil, fmt.Errorf("failed to find archetypal exercise: %w", err)
	}

	if !result.Next(ctx) {
		// No archetypal exercise found - this is okay, we'll use rule-based inference
		return nil, nil
	}

	record := result.Record()
	
	name, _ := record.Get("name")
	equipmentVal, _ := record.Get("equipment")
	equipment = equipmentVal.(string)
	movementPattern, _ := record.Get("movement_pattern")
	exerciseType, _ := record.Get("exercise_type")
	musclesRaw, _ := record.Get("muscles")

	exercise := &models.ExerciseNode{
		Name:            name.(string),
		Equipment:       equipment,
		MovementPattern: movementPattern.(string),
		ExerciseType:    exerciseType.(string),
		MuscleTargets:   []models.MuscleTarget{},
	}

	// Parse muscles
	if muscles, ok := musclesRaw.([]interface{}); ok {
		for _, m := range muscles {
			if muscleMap, ok := m.(map[string]interface{}); ok {
				if muscleName, ok := muscleMap["muscle"].(string); ok && muscleName != "" {
					role, _ := muscleMap["role"].(string)
					exercise.MuscleTargets = append(exercise.MuscleTargets, models.MuscleTarget{
						MuscleName: muscleName,
						Role:       role,
					})
				}
			}
		}
	}

	return exercise, nil
}

// GetAllMovementPatterns returns all movement patterns
func (r *Repository) GetAllMovementPatterns(ctx context.Context) ([]string, error) {
	session := r.driver.NewSession(ctx, neo4j.SessionConfig{AccessMode: neo4j.AccessModeRead})
	defer session.Close(ctx)

	query := `
		MATCH (p:Pattern)
		RETURN p.name as name
		ORDER BY p.name
	`

	result, err := session.Run(ctx, query, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to get movement patterns: %w", err)
	}

	var patterns []string
	for result.Next(ctx) {
		record := result.Record()
		if name, ok := record.Get("name"); ok {
			patterns = append(patterns, name.(string))
		}
	}

	return patterns, nil
}

// SimilarityFilters contains filters for finding similar exercises
type SimilarityFilters struct {
	SameEquipment  bool
	SameLaterality bool
	SameAngle      bool
	Limit          int32
}

// FindSimilarExercises finds exercises with similar movement patterns and modifiers
func (r *Repository) FindSimilarExercises(ctx context.Context, exerciseName string, filters SimilarityFilters) ([]string, error) {
	session := r.driver.NewSession(ctx, neo4j.SessionConfig{AccessMode: neo4j.AccessModeRead})
	defer session.Close(ctx)

	// Set default limit
	limit := filters.Limit
	if limit <= 0 {
		limit = 20
	}

	// Build the query dynamically based on filters
	query := `
		// Find the source exercise
		MATCH (source:Exercise {name: $exercise_name})
		
		// Find exercises with the same movement pattern
		// Pattern -[:HAS_ARCHETYPE]-> Exercise (relationship direction)
		MATCH (pattern:Pattern)-[:HAS_ARCHETYPE]->(source)
		MATCH (pattern)-[:HAS_ARCHETYPE]->(candidate:Exercise)
		WHERE candidate.name <> source.name
		
		// Calculate similarity score based on shared modifiers
		WITH source, candidate,
		     // Equipment match
		     CASE WHEN toLower(source.equipment) = toLower(candidate.equipment) THEN 0.3 ELSE 0.0 END as equipment_score,
		     // Exercise type match (compound/isolation)
		     CASE WHEN source.exercise_type = candidate.exercise_type THEN 0.2 ELSE 0.0 END as type_score
		
		WITH source, candidate, 
		     (equipment_score + type_score + 0.5) as similarity_score
		
		// Apply filters
		WHERE ($same_equipment = false OR toLower(source.equipment) = toLower(candidate.equipment))
	`

	// Note: Laterality and angle are stored as modifiers, not as direct properties
	// For now, we focus on equipment and movement pattern
	// TODO: If laterality/angle become important, store them as properties

	query += `
		// Order by similarity and limit results
		ORDER BY similarity_score DESC
		LIMIT $limit
		
		RETURN candidate.name as name, similarity_score
	`

	params := map[string]interface{}{
		"exercise_name":  exerciseName,
		"same_equipment": filters.SameEquipment,
		"limit":          limit,
	}

	result, err := session.Run(ctx, query, params)
	if err != nil {
		return nil, fmt.Errorf("failed to find similar exercises: %w", err)
	}

	var similarExercises []string
	for result.Next(ctx) {
		record := result.Record()
		if name, ok := record.Get("name"); ok {
			if nameStr, ok := name.(string); ok {
				similarExercises = append(similarExercises, nameStr)
			}
		}
	}

	return similarExercises, nil
}

