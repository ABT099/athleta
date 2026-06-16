package graph

import (
	"context"
	"fmt"

	"github.com/neo4j/neo4j-go-driver/v6/neo4j"
)

// InitSchema creates constraints, indexes, and the static taxonomy
// (movement patterns, muscles, equipment, joints). Idempotent.
func (r *Repository) InitSchema(ctx context.Context) error {
	session := r.driver.NewSession(ctx, neo4j.SessionConfig{AccessMode: neo4j.AccessModeWrite})
	defer session.Close(ctx)

	constraints := []string{
		"CREATE CONSTRAINT IF NOT EXISTS FOR (e:Exercise) REQUIRE e.id IS UNIQUE",
		"CREATE CONSTRAINT IF NOT EXISTS FOR (e:Exercise) REQUIRE e.name IS UNIQUE",
		"CREATE CONSTRAINT IF NOT EXISTS FOR (p:MovementPattern) REQUIRE p.name IS UNIQUE",
		"CREATE CONSTRAINT IF NOT EXISTS FOR (m:Muscle) REQUIRE m.name IS UNIQUE",
		"CREATE CONSTRAINT IF NOT EXISTS FOR (eq:Equipment) REQUIRE eq.name IS UNIQUE",
		"CREATE CONSTRAINT IF NOT EXISTS FOR (j:Joint) REQUIRE j.name IS UNIQUE",
		"CREATE CONSTRAINT IF NOT EXISTS FOR (c:Counter) REQUIRE c.name IS UNIQUE",
	}
	for _, constraint := range constraints {
		if _, err := session.Run(ctx, constraint, nil); err != nil {
			return fmt.Errorf("failed to create constraint: %w", err)
		}
	}

	if err := seedTaxonomy(ctx, session); err != nil {
		return fmt.Errorf("failed to seed taxonomy: %w", err)
	}

	return nil
}

func seedTaxonomy(ctx context.Context, session neo4j.Session) error {
	patterns := make([]map[string]any, 0, len(Patterns))
	for _, p := range Patterns {
		patterns = append(patterns, map[string]any{"name": p.Name, "description": p.Description})
	}
	if _, err := session.Run(ctx, `
		UNWIND $patterns AS p
		MERGE (n:MovementPattern {name: p.name})
		SET n.description = p.description
	`, map[string]any{"patterns": patterns}); err != nil {
		return err
	}

	relations := make([]map[string]any, 0, len(PatternRelations))
	for _, rel := range PatternRelations {
		relations = append(relations, map[string]any{"from": rel.From, "to": rel.To, "weight": rel.Weight})
	}
	if _, err := session.Run(ctx, `
		UNWIND $relations AS r
		MATCH (a:MovementPattern {name: r.from}), (b:MovementPattern {name: r.to})
		MERGE (a)-[rel:RELATED_TO]->(b)
		SET rel.weight = r.weight
	`, map[string]any{"relations": relations}); err != nil {
		return err
	}

	muscles := make([]map[string]any, 0, len(Muscles))
	for _, m := range Muscles {
		muscles = append(muscles, map[string]any{
			"name": m.Name, "display_name": m.DisplayName,
			"size": m.Size, "recovery_hours": m.RecoveryHours,
			"is_compound_target": m.IsCompoundTarget,
		})
	}
	if _, err := session.Run(ctx, `
		UNWIND $muscles AS m
		MERGE (n:Muscle {name: m.name})
		SET n.display_name = m.display_name, n.size = m.size,
		    n.recovery_hours = m.recovery_hours, n.is_compound_target = m.is_compound_target
	`, map[string]any{"muscles": muscles}); err != nil {
		return err
	}

	antagonists := make([]map[string]any, 0)
	for _, m := range Muscles {
		if m.Antagonist != "" {
			antagonists = append(antagonists, map[string]any{"from": m.Name, "to": m.Antagonist})
		}
	}
	if _, err := session.Run(ctx, `
		UNWIND $pairs AS p
		MATCH (a:Muscle {name: p.from}), (b:Muscle {name: p.to})
		MERGE (a)-[:ANTAGONIST_OF]->(b)
	`, map[string]any{"pairs": antagonists}); err != nil {
		return err
	}

	equipment := make([]map[string]any, 0, len(Equipment))
	for _, e := range Equipment {
		equipment = append(equipment, map[string]any{"name": e.Name, "category": e.Category})
	}
	if _, err := session.Run(ctx, `
		UNWIND $equipment AS e
		MERGE (n:Equipment {name: e.name})
		SET n.category = e.category
	`, map[string]any{"equipment": equipment}); err != nil {
		return err
	}

	equipmentRelations := make([]map[string]any, 0, len(EquipmentRelations))
	for _, rel := range EquipmentRelations {
		equipmentRelations = append(equipmentRelations, map[string]any{"from": rel.From, "to": rel.To})
	}
	if _, err := session.Run(ctx, `
		UNWIND $relations AS r
		MATCH (a:Equipment {name: r.from}), (b:Equipment {name: r.to})
		MERGE (a)-[:SIMILAR_TO]->(b)
	`, map[string]any{"relations": equipmentRelations}); err != nil {
		return err
	}

	if _, err := session.Run(ctx, `
		UNWIND $joints AS j
		MERGE (:Joint {name: j})
	`, map[string]any{"joints": Joints}); err != nil {
		return err
	}

	return nil
}
