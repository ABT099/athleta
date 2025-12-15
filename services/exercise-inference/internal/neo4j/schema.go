package neo4j

import (
	"context"
	"fmt"

	"github.com/neo4j/neo4j-go-driver/v5/neo4j"
)

// InitializeSchema creates the movement pattern hierarchy and modifier system in Neo4j
func InitializeSchema(ctx context.Context, driver neo4j.DriverWithContext) error {
	session := driver.NewSession(ctx, neo4j.SessionConfig{AccessMode: neo4j.AccessModeWrite})
	defer session.Close(ctx)

	// Create constraints and indexes
	if err := createConstraints(ctx, session); err != nil {
		return fmt.Errorf("failed to create constraints: %w", err)
	}

	// Create movement pattern hierarchy
	if err := createMovementPatterns(ctx, session); err != nil {
		return fmt.Errorf("failed to create movement patterns: %w", err)
	}

	// Create modifier system
	if err := createModifierSystem(ctx, session); err != nil {
		return fmt.Errorf("failed to create modifier system: %w", err)
	}

	return nil
}

func createConstraints(ctx context.Context, session neo4j.SessionWithContext) error {
	constraints := []string{
		"CREATE CONSTRAINT IF NOT EXISTS FOR (p:Pattern) REQUIRE p.name IS UNIQUE",
		"CREATE CONSTRAINT IF NOT EXISTS FOR (e:Exercise) REQUIRE e.name IS UNIQUE",
		"CREATE CONSTRAINT IF NOT EXISTS FOR (m:Muscle) REQUIRE m.name IS UNIQUE",
		"CREATE CONSTRAINT IF NOT EXISTS FOR (mc:ModifierCategory) REQUIRE mc.name IS UNIQUE",
	}

	for _, constraint := range constraints {
		_, err := session.Run(ctx, constraint, nil)
		if err != nil {
			return fmt.Errorf("failed to create constraint: %w", err)
		}
	}

	// Create indexes for performance
	indexes := []string{
		"CREATE INDEX IF NOT EXISTS FOR (e:Exercise) ON (e.postgres_id)",
		"CREATE INDEX IF NOT EXISTS FOR (e:Exercise) ON (e.archetypal)",
	}

	for _, index := range indexes {
		_, err := session.Run(ctx, index, nil)
		if err != nil {
			return fmt.Errorf("failed to create index: %w", err)
		}
	}

	return nil
}

func createMovementPatterns(ctx context.Context, session neo4j.SessionWithContext) error {
	query := `
		// Create root node
		MERGE (root:MovementRoot {name: 'Human Movement'})
		
		// Create 7 primal movement patterns
		MERGE (squat:Pattern {name: 'Squat', type: 'knee_dominant', description: 'Knee-dominant lower body movements'})
		MERGE (hinge:Pattern {name: 'Hinge', type: 'hip_dominant', description: 'Hip-dominant lower body movements'})
		MERGE (push:Pattern {name: 'Push', type: 'pressing', description: 'Horizontal and vertical pressing movements'})
		MERGE (pull:Pattern {name: 'Pull', type: 'pulling', description: 'Horizontal and vertical pulling movements'})
		MERGE (lunge:Pattern {name: 'Lunge', type: 'unilateral_leg', description: 'Unilateral leg movements'})
		MERGE (carry:Pattern {name: 'Carry', type: 'locomotion', description: 'Loaded carries and locomotion'})
		MERGE (rotation:Pattern {name: 'Rotation', type: 'core_stability', description: 'Core stability and rotational movements'})
		
		// Link patterns to root
		MERGE (root)-[:HAS_PATTERN]->(squat)
		MERGE (root)-[:HAS_PATTERN]->(hinge)
		MERGE (root)-[:HAS_PATTERN]->(push)
		MERGE (root)-[:HAS_PATTERN]->(pull)
		MERGE (root)-[:HAS_PATTERN]->(lunge)
		MERGE (root)-[:HAS_PATTERN]->(carry)
		MERGE (root)-[:HAS_PATTERN]->(rotation)
		
		RETURN root
	`

	_, err := session.Run(ctx, query, nil)
	return err
}

func createModifierSystem(ctx context.Context, session neo4j.SessionWithContext) error {
	// Implement modifier category
	implementQuery := `
		MERGE (cat:ModifierCategory {name: 'Implement'})
		MERGE (cat)-[:HAS_VALUE]->(:Modifier {value: 'barbell', category: 'implement'})
		MERGE (cat)-[:HAS_VALUE]->(:Modifier {value: 'dumbbell', category: 'implement'})
		MERGE (cat)-[:HAS_VALUE]->(:Modifier {value: 'kettlebell', category: 'implement'})
		MERGE (cat)-[:HAS_VALUE]->(:Modifier {value: 'cable', category: 'implement'})
		MERGE (cat)-[:HAS_VALUE]->(:Modifier {value: 'machine', category: 'implement'})
		MERGE (cat)-[:HAS_VALUE]->(:Modifier {value: 'bodyweight', category: 'implement'})
		MERGE (cat)-[:HAS_VALUE]->(:Modifier {value: 'landmine', category: 'implement'})
		MERGE (cat)-[:HAS_VALUE]->(:Modifier {value: 'band', category: 'implement'})
		MERGE (cat)-[:HAS_VALUE]->(:Modifier {value: 'resistance_band', category: 'implement'})
		RETURN cat
	`

	// Laterality modifier category
	lateralityQuery := `
		MERGE (cat:ModifierCategory {name: 'Laterality'})
		MERGE (cat)-[:HAS_VALUE]->(:Modifier {value: 'bilateral', category: 'laterality'})
		MERGE (cat)-[:HAS_VALUE]->(:Modifier {value: 'unilateral', category: 'laterality'})
		MERGE (cat)-[:HAS_VALUE]->(:Modifier {value: 'alternating', category: 'laterality'})
		MERGE (cat)-[:HAS_VALUE]->(:Modifier {value: 'isometric_hold', category: 'laterality'})
		MERGE (cat)-[:HAS_VALUE]->(:Modifier {value: 'single_arm', category: 'laterality'})
		MERGE (cat)-[:HAS_VALUE]->(:Modifier {value: 'single_leg', category: 'laterality'})
		RETURN cat
	`

	// Angle modifier category
	angleQuery := `
		MERGE (cat:ModifierCategory {name: 'Angle'})
		MERGE (cat)-[:HAS_VALUE]->(:Modifier {value: 'flat', category: 'angle'})
		MERGE (cat)-[:HAS_VALUE]->(:Modifier {value: 'incline', category: 'angle'})
		MERGE (cat)-[:HAS_VALUE]->(:Modifier {value: 'decline', category: 'angle'})
		MERGE (cat)-[:HAS_VALUE]->(:Modifier {value: 'overhead', category: 'angle'})
		MERGE (cat)-[:HAS_VALUE]->(:Modifier {value: 'floor_level', category: 'angle'})
		RETURN cat
	`

	// Grip/Stance modifier category
	gripQuery := `
		MERGE (cat:ModifierCategory {name: 'GripStance'})
		MERGE (cat)-[:HAS_VALUE]->(:Modifier {value: 'neutral', category: 'grip_stance'})
		MERGE (cat)-[:HAS_VALUE]->(:Modifier {value: 'pronated', category: 'grip_stance'})
		MERGE (cat)-[:HAS_VALUE]->(:Modifier {value: 'supinated', category: 'grip_stance'})
		MERGE (cat)-[:HAS_VALUE]->(:Modifier {value: 'wide', category: 'grip_stance'})
		MERGE (cat)-[:HAS_VALUE]->(:Modifier {value: 'narrow', category: 'grip_stance'})
		MERGE (cat)-[:HAS_VALUE]->(:Modifier {value: 'close_grip', category: 'grip_stance'})
		MERGE (cat)-[:HAS_VALUE]->(:Modifier {value: 'staggered', category: 'grip_stance'})
		MERGE (cat)-[:HAS_VALUE]->(:Modifier {value: 'split', category: 'grip_stance'})
		RETURN cat
	`

	// Plane modifier category
	planeQuery := `
		MERGE (cat:ModifierCategory {name: 'Plane'})
		MERGE (cat)-[:HAS_VALUE]->(:Modifier {value: 'sagittal', category: 'plane'})
		MERGE (cat)-[:HAS_VALUE]->(:Modifier {value: 'frontal', category: 'plane'})
		MERGE (cat)-[:HAS_VALUE]->(:Modifier {value: 'transverse', category: 'plane'})
		RETURN cat
	`

	// Tempo modifier category
	tempoQuery := `
		MERGE (cat:ModifierCategory {name: 'Tempo'})
		MERGE (cat)-[:HAS_VALUE]->(:Modifier {value: 'eccentric_focus', category: 'tempo'})
		MERGE (cat)-[:HAS_VALUE]->(:Modifier {value: 'explosive', category: 'tempo'})
		MERGE (cat)-[:HAS_VALUE]->(:Modifier {value: 'tempo', category: 'tempo'})
		MERGE (cat)-[:HAS_VALUE]->(:Modifier {value: 'pause', category: 'tempo'})
		MERGE (cat)-[:HAS_VALUE]->(:Modifier {value: 'paused', category: 'tempo'})
		MERGE (cat)-[:HAS_VALUE]->(:Modifier {value: 'accommodating_resistance', category: 'tempo'})
		MERGE (cat)-[:HAS_VALUE]->(:Modifier {value: 'chains', category: 'tempo'})
		MERGE (cat)-[:HAS_VALUE]->(:Modifier {value: 'bands', category: 'tempo'})
		RETURN cat
	`

	queries := []string{
		implementQuery,
		lateralityQuery,
		angleQuery,
		gripQuery,
		planeQuery,
		tempoQuery,
	}

	for _, query := range queries {
		_, err := session.Run(ctx, query, nil)
		if err != nil {
			return err
		}
	}

	return nil
}

