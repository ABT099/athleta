package graph

import (
	"context"
	"fmt"

	"github.com/athleta/exercise-service/internal/domain"
	"github.com/neo4j/neo4j-go-driver/v6/neo4j"
)

// Repository handles all Neo4j operations for the exercise graph.
type Repository struct {
	driver neo4j.Driver
}

// NewRepository creates a new Neo4j repository and verifies connectivity.
func NewRepository(uri, username, password string) (*Repository, error) {
	driver, err := neo4j.NewDriverWithContext(uri, neo4j.BasicAuth(username, password, ""))
	if err != nil {
		return nil, fmt.Errorf("failed to create Neo4j driver: %w", err)
	}

	ctx := context.Background()
	if err := driver.VerifyConnectivity(ctx); err != nil {
		return nil, fmt.Errorf("failed to verify Neo4j connectivity: %w", err)
	}

	return &Repository{driver: driver}, nil
}

// Close closes the Neo4j driver.
func (r *Repository) Close(ctx context.Context) error {
	return r.driver.Close(ctx)
}

// exerciseReturnClause projects an exercise variable plus its gathered
// pattern/equipment/joints/muscles into the flat record shape parsed by
// recordToExercise. The query feeding it must bind: e, pattern, equipment,
// joints, muscles.
const exerciseReturnClause = `
	RETURN e.id AS id, e.name AS name, pattern, equipment, joints, muscles,
	       e.exercise_type AS exercise_type, e.intensity_category AS intensity_category,
	       e.injury_risk_level AS injury_risk_level, e.complexity_score AS complexity_score,
	       e.laterality AS laterality, e.angle AS angle, e.grip AS grip,
	       e.tempo AS tempo, e.force_vector AS force_vector
`

// UpsertExercise creates or updates an exercise by name and (re)builds all of
// its attribute relationships. A new exercise gets a freshly allocated ID;
// an existing one keeps its ID. Returns the exercise ID.
func (r *Repository) UpsertExercise(ctx context.Context, ex *domain.Exercise) (int32, error) {
	session := r.driver.NewSession(ctx, neo4j.SessionConfig{AccessMode: neo4j.AccessModeWrite})
	defer session.Close(ctx)

	id, err := r.allocateID(ctx, session)
	if err != nil {
		return 0, err
	}

	muscles := make([]map[string]any, 0, len(ex.Muscles))
	for _, m := range ex.Muscles {
		muscles = append(muscles, map[string]any{
			"name": m.Name, "role": m.Role, "activation": int64(m.ActivationPercent),
		})
	}

	// MERGE on the unique name makes concurrent inference of the same new
	// name race-safe; the losing allocation just leaves a gap in the ID
	// sequence. ON CREATE keeps existing IDs stable across re-inference.
	query := `
		MERGE (e:Exercise {name: $name})
		ON CREATE SET e.id = $id
		SET e.exercise_type = $exercise_type,
		    e.intensity_category = $intensity_category,
		    e.injury_risk_level = $injury_risk_level,
		    e.complexity_score = $complexity_score,
		    e.laterality = $laterality,
		    e.angle = $angle,
		    e.grip = $grip,
		    e.tempo = $tempo,
		    e.force_vector = $force_vector
		WITH e
		OPTIONAL MATCH (e)-[old:FOLLOWS_PATTERN|USES|STRESSES|TARGETS]->()
		DELETE old
		WITH DISTINCT e
		OPTIONAL MATCH (p:MovementPattern {name: $pattern})
		FOREACH (x IN CASE WHEN p IS NULL THEN [] ELSE [p] END | MERGE (e)-[:FOLLOWS_PATTERN]->(x))
		WITH e
		OPTIONAL MATCH (eq:Equipment {name: $equipment})
		FOREACH (x IN CASE WHEN eq IS NULL THEN [] ELSE [eq] END | MERGE (e)-[:USES]->(x))
		WITH e
		FOREACH (jn IN $joints |
			MERGE (j:Joint {name: jn})
			MERGE (e)-[:STRESSES]->(j))
		FOREACH (mt IN $muscles |
			MERGE (m:Muscle {name: mt.name})
			MERGE (e)-[t:TARGETS]->(m)
			SET t.role = mt.role, t.activation = mt.activation)
		RETURN e.id AS id
	`

	params := map[string]any{
		"name":               ex.Name,
		"id":                 id,
		"exercise_type":      ex.ExerciseType,
		"intensity_category": ex.IntensityCategory,
		"injury_risk_level":  float64(ex.Safety.InjuryRiskLevel),
		"complexity_score":   float64(ex.Safety.ComplexityScore),
		"laterality":         ex.Attributes.Laterality,
		"angle":              ex.Attributes.Angle,
		"grip":               ex.Attributes.Grip,
		"tempo":              ex.Attributes.Tempo,
		"force_vector":       ex.Attributes.ForceVector,
		"pattern":            ex.MovementPattern,
		"equipment":          ex.Attributes.Equipment,
		"joints":             ex.Safety.JointStressAreas,
		"muscles":            muscles,
	}

	result, err := session.Run(ctx, query, params)
	if err != nil {
		return 0, fmt.Errorf("failed to upsert exercise %q: %w", ex.Name, err)
	}
	if !result.Next(ctx) {
		return 0, fmt.Errorf("upsert of exercise %q returned no record", ex.Name)
	}

	storedID, _ := result.Record().Get("id")
	if v, ok := storedID.(int64); ok {
		return int32(v), nil
	}
	return 0, fmt.Errorf("upsert of exercise %q returned non-integer id", ex.Name)
}

func (r *Repository) allocateID(ctx context.Context, session neo4j.Session) (int64, error) {
	result, err := session.Run(ctx, `
		MERGE (c:Counter {name: 'exercise_id'})
		ON CREATE SET c.value = 0
		SET c.value = c.value + 1
		RETURN c.value AS id
	`, nil)
	if err != nil {
		return 0, fmt.Errorf("failed to allocate exercise id: %w", err)
	}
	if !result.Next(ctx) {
		return 0, fmt.Errorf("id allocation returned no record")
	}
	id, _ := result.Record().Get("id")
	v, ok := id.(int64)
	if !ok {
		return 0, fmt.Errorf("id allocation returned non-integer value")
	}
	return v, nil
}

// GetExercisesByIDs fetches exercises by ID. Unknown IDs are simply absent
// from the result.
func (r *Repository) GetExercisesByIDs(ctx context.Context, ids []int32) ([]*domain.Exercise, error) {
	session := r.driver.NewSession(ctx, neo4j.SessionConfig{AccessMode: neo4j.AccessModeRead})
	defer session.Close(ctx)

	int64IDs := make([]int64, 0, len(ids))
	for _, id := range ids {
		int64IDs = append(int64IDs, int64(id))
	}

	query := `
		MATCH (e:Exercise) WHERE e.id IN $ids
	` + exerciseCollectClause + exerciseReturnClause

	result, err := session.Run(ctx, query, map[string]any{"ids": int64IDs})
	if err != nil {
		return nil, fmt.Errorf("failed to get exercises by ids: %w", err)
	}

	return collectExercises(ctx, result)
}

// GetExerciseByName fetches a single exercise by exact name.
func (r *Repository) GetExerciseByName(ctx context.Context, name string) (*domain.Exercise, error) {
	session := r.driver.NewSession(ctx, neo4j.SessionConfig{AccessMode: neo4j.AccessModeRead})
	defer session.Close(ctx)

	query := `
		MATCH (e:Exercise {name: $name})
	` + exerciseCollectClause + exerciseReturnClause

	result, err := session.Run(ctx, query, map[string]any{"name": name})
	if err != nil {
		return nil, fmt.Errorf("failed to get exercise by name: %w", err)
	}

	exercises, err := collectExercises(ctx, result)
	if err != nil {
		return nil, err
	}
	if len(exercises) == 0 {
		return nil, nil
	}
	return exercises[0], nil
}

// GetMuscles returns muscle metadata from the taxonomy. Empty names returns
// all muscles (ordered by name) for seeding and validation.
func (r *Repository) GetMuscles(ctx context.Context, names []string) ([]domain.Muscle, error) {
	session := r.driver.NewSession(ctx, neo4j.SessionConfig{AccessMode: neo4j.AccessModeRead})
	defer session.Close(ctx)

	if names == nil {
		names = []string{}
	}

	query := `
		MATCH (m:Muscle)
		WHERE size($names) = 0 OR m.name IN $names
		OPTIONAL MATCH (m)-[:ANTAGONIST_OF]->(a:Muscle)
		RETURN m.name AS name, m.display_name AS display_name, m.size AS size,
		       m.recovery_hours AS recovery_hours, m.is_compound_target AS is_compound_target,
		       head(collect(a.name)) AS antagonist
		ORDER BY m.name
	`

	result, err := session.Run(ctx, query, map[string]any{"names": names})
	if err != nil {
		return nil, fmt.Errorf("failed to get muscles: %w", err)
	}

	muscles := make([]domain.Muscle, 0)
	for result.Next(ctx) {
		record := result.Record()
		muscles = append(muscles, domain.Muscle{
			Name:             getString(record, "name"),
			DisplayName:      getString(record, "display_name"),
			Size:             getString(record, "size"),
			RecoveryHours:    int(getInt(record, "recovery_hours")),
			Antagonist:       getString(record, "antagonist"),
			IsCompoundTarget: getBool(record, "is_compound_target"),
		})
	}

	return muscles, result.Err()
}

// exerciseCollectClause gathers pattern, equipment, joints, and muscles for
// a bound exercise variable `e`.
const exerciseCollectClause = `
	OPTIONAL MATCH (e)-[:FOLLOWS_PATTERN]->(p:MovementPattern)
	OPTIONAL MATCH (e)-[:USES]->(eq:Equipment)
	WITH e, head(collect(DISTINCT p.name)) AS pattern, head(collect(DISTINCT eq.name)) AS equipment
	OPTIONAL MATCH (e)-[:STRESSES]->(j:Joint)
	WITH e, pattern, equipment, collect(DISTINCT j.name) AS joints
	OPTIONAL MATCH (e)-[t:TARGETS]->(m:Muscle)
	WITH e, pattern, equipment, joints,
	     collect(DISTINCT {name: m.name, display_name: m.display_name, role: t.role, activation: t.activation}) AS muscles
`

// FindSubstitutionCandidates returns exercises sharing at least one targeted
// muscle with the original, excluding the given IDs and anything stressing
// the given joints. The graph returns raw structural facts (same/related
// pattern, same/similar equipment); turning those facts into a score is the
// scoring layer's job, not Cypher's.
func (r *Repository) FindSubstitutionCandidates(
	ctx context.Context,
	exerciseID int32,
	excludeIDs []int32,
	excludeJoints []string,
) ([]domain.SubstitutionCandidate, error) {
	session := r.driver.NewSession(ctx, neo4j.SessionConfig{AccessMode: neo4j.AccessModeRead})
	defer session.Close(ctx)

	int64Excludes := make([]int64, 0, len(excludeIDs))
	for _, id := range excludeIDs {
		int64Excludes = append(int64Excludes, int64(id))
	}
	if excludeJoints == nil {
		excludeJoints = []string{}
	}

	query := `
		MATCH (orig:Exercise {id: $id})
		OPTIONAL MATCH (orig)-[:FOLLOWS_PATTERN]->(op:MovementPattern)
		OPTIONAL MATCH (orig)-[:USES]->(oe:Equipment)
		WITH orig, op, oe
		MATCH (orig)-[:TARGETS]->(:Muscle)<-[:TARGETS]-(e:Exercise)
		WHERE e.id <> orig.id AND NOT e.id IN $exclude_ids
		WITH DISTINCT op, oe, e
		WHERE NOT EXISTS {
			MATCH (e)-[:STRESSES]->(xj:Joint) WHERE xj.name IN $exclude_joints
		}
		OPTIONAL MATCH (e)-[:FOLLOWS_PATTERN]->(cp:MovementPattern)
		OPTIONAL MATCH (e)-[:USES]->(ce:Equipment)
		OPTIONAL MATCH (op)-[prel:RELATED_TO]-(cp)
		OPTIONAL MATCH (oe)-[erel:SIMILAR_TO]-(ce)
		WITH e, cp.name AS pattern, ce.name AS equipment,
		     (cp IS NOT NULL AND op IS NOT NULL AND cp.name = op.name) AS same_pattern,
		     (ce IS NOT NULL AND oe IS NOT NULL AND ce.name = oe.name) AS same_equipment,
		     coalesce(prel.weight, 0.0) AS prel_weight,
		     (erel IS NOT NULL) AS has_similar_equipment
		WITH e, pattern, equipment, same_pattern, same_equipment,
		     CASE WHEN same_pattern THEN 0.0 ELSE prel_weight END AS related_pattern_weight,
		     (has_similar_equipment AND NOT same_equipment) AS similar_equipment
		OPTIONAL MATCH (e)-[:STRESSES]->(j:Joint)
		WITH e, pattern, equipment, same_pattern, related_pattern_weight, same_equipment, similar_equipment,
		     collect(DISTINCT j.name) AS joints
		OPTIONAL MATCH (e)-[t:TARGETS]->(m:Muscle)
		WITH e, pattern, equipment, same_pattern, related_pattern_weight, same_equipment, similar_equipment, joints,
		     collect(DISTINCT {name: m.name, display_name: m.display_name, role: t.role, activation: t.activation}) AS muscles
		RETURN e.id AS id, e.name AS name, pattern, equipment, joints, muscles,
		       e.exercise_type AS exercise_type, e.intensity_category AS intensity_category,
		       e.injury_risk_level AS injury_risk_level, e.complexity_score AS complexity_score,
		       e.laterality AS laterality, e.angle AS angle, e.grip AS grip,
		       e.tempo AS tempo, e.force_vector AS force_vector,
		       same_pattern, related_pattern_weight, same_equipment, similar_equipment
	`

	result, err := session.Run(ctx, query, map[string]any{
		"id":             int64(exerciseID),
		"exclude_ids":    int64Excludes,
		"exclude_joints": excludeJoints,
	})
	if err != nil {
		return nil, fmt.Errorf("failed to find substitution candidates: %w", err)
	}

	candidates := make([]domain.SubstitutionCandidate, 0)
	for result.Next(ctx) {
		record := result.Record()
		ex, err := recordToExercise(record)
		if err != nil {
			return nil, err
		}
		candidates = append(candidates, domain.SubstitutionCandidate{
			Exercise:             ex,
			SamePattern:          getBool(record, "same_pattern"),
			RelatedPatternWeight: getFloat(record, "related_pattern_weight"),
			SameEquipment:        getBool(record, "same_equipment"),
			SimilarEquipment:     getBool(record, "similar_equipment"),
		})
	}

	return candidates, result.Err()
}

func collectExercises(ctx context.Context, result neo4j.Result) ([]*domain.Exercise, error) {
	exercises := make([]*domain.Exercise, 0)
	for result.Next(ctx) {
		ex, err := recordToExercise(result.Record())
		if err != nil {
			return nil, err
		}
		exercises = append(exercises, ex)
	}
	return exercises, result.Err()
}

func recordToExercise(record *neo4j.Record) (*domain.Exercise, error) {
	idRaw, _ := record.Get("id")
	id, ok := idRaw.(int64)
	if !ok {
		return nil, fmt.Errorf("exercise record has non-integer id: %v", idRaw)
	}

	ex := &domain.Exercise{
		ID:                int32(id),
		Name:              getString(record, "name"),
		MovementPattern:   getString(record, "pattern"),
		ExerciseType:      getString(record, "exercise_type"),
		IntensityCategory: getString(record, "intensity_category"),
		Attributes: domain.Attributes{
			Equipment:   getString(record, "equipment"),
			Laterality:  getString(record, "laterality"),
			Angle:       getString(record, "angle"),
			Grip:        getString(record, "grip"),
			Tempo:       getString(record, "tempo"),
			ForceVector: getString(record, "force_vector"),
		},
		Safety: domain.SafetyProfile{
			InjuryRiskLevel:  float32(getFloat(record, "injury_risk_level")),
			ComplexityScore:  float32(getFloat(record, "complexity_score")),
			JointStressAreas: getStringList(record, "joints"),
		},
	}

	musclesRaw, _ := record.Get("muscles")
	if muscleList, ok := musclesRaw.([]any); ok {
		for _, m := range muscleList {
			muscleMap, ok := m.(map[string]any)
			if !ok {
				continue
			}
			name, _ := muscleMap["name"].(string)
			if name == "" {
				continue
			}
			displayName, _ := muscleMap["display_name"].(string)
			role, _ := muscleMap["role"].(string)
			activation, _ := muscleMap["activation"].(int64)
			ex.Muscles = append(ex.Muscles, domain.MuscleTarget{
				Name:              name,
				DisplayName:       displayName,
				Role:              role,
				ActivationPercent: int32(activation),
			})
		}
	}

	return ex, nil
}

func getString(record *neo4j.Record, key string) string {
	value, _ := record.Get(key)
	if s, ok := value.(string); ok {
		return s
	}
	return ""
}

func getFloat(record *neo4j.Record, key string) float64 {
	value, _ := record.Get(key)
	switch v := value.(type) {
	case float64:
		return v
	case int64:
		return float64(v)
	}
	return 0
}

func getInt(record *neo4j.Record, key string) int64 {
	value, _ := record.Get(key)
	switch v := value.(type) {
	case int64:
		return v
	case float64:
		return int64(v)
	}
	return 0
}

func getBool(record *neo4j.Record, key string) bool {
	value, _ := record.Get(key)
	b, _ := value.(bool)
	return b
}

func getStringList(record *neo4j.Record, key string) []string {
	value, _ := record.Get(key)
	list, ok := value.([]any)
	if !ok {
		return nil
	}
	out := make([]string, 0, len(list))
	for _, item := range list {
		if s, ok := item.(string); ok && s != "" {
			out = append(out, s)
		}
	}
	return out
}
