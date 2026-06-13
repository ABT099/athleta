// Package memgraph is an in-memory adapter for the exercise graph. It
// satisfies the service's Graph seam without a database, so orchestration,
// resolution, seeding, and substitution can be unit-tested in milliseconds.
// The Neo4j repository remains the production adapter; integration tests pin
// the two adapters to the same contract.
package memgraph

import (
	"context"
	"strings"
	"sync"

	"github.com/athleta/exercise-service/internal/domain"
	"github.com/athleta/exercise-service/internal/graph"
)

// MemGraph is a goroutine-safe in-memory implementation of the graph.
type MemGraph struct {
	mu        sync.Mutex
	byID      map[int32]*domain.Exercise
	byName    map[string]int32 // lowercased name -> id
	nextID    int32
	muscles   map[string]graph.MuscleSeed
	patternRel map[[2]string]float64 // unordered pattern pair -> weight
	equipRel   map[[2]string]bool    // unordered equipment pair
}

// New builds a MemGraph preloaded with the static taxonomy (muscles, pattern
// relations, equipment relations) — the same data InitSchema seeds in Neo4j.
func New() *MemGraph {
	m := &MemGraph{
		byID:       map[int32]*domain.Exercise{},
		byName:     map[string]int32{},
		muscles:    map[string]graph.MuscleSeed{},
		patternRel: map[[2]string]float64{},
		equipRel:   map[[2]string]bool{},
	}
	for _, mu := range graph.Muscles {
		m.muscles[mu.Name] = mu
	}
	for _, r := range graph.PatternRelations {
		m.patternRel[pair(r.From, r.To)] = r.Weight
	}
	for _, r := range graph.EquipmentRelations {
		m.equipRel[pair(r.From, r.To)] = true
	}
	return m
}

func pair(a, b string) [2]string {
	if a <= b {
		return [2]string{a, b}
	}
	return [2]string{b, a}
}

// UpsertExercise mirrors the Neo4j MERGE-by-name semantics: an existing name
// keeps its ID and is fully replaced; a new name gets the next ID. Muscle
// display names are hydrated from the taxonomy, as the repository does.
func (m *MemGraph) UpsertExercise(_ context.Context, ex *domain.Exercise) (int32, error) {
	m.mu.Lock()
	defer m.mu.Unlock()

	key := strings.ToLower(ex.Name)
	id, exists := m.byName[key]
	if !exists {
		m.nextID++
		id = m.nextID
		m.byName[key] = id
	}

	stored := *ex
	stored.ID = id
	stored.Muscles = m.hydrateMuscles(ex.Muscles)
	m.byID[id] = &stored

	return id, nil
}

func (m *MemGraph) hydrateMuscles(targets []domain.MuscleTarget) []domain.MuscleTarget {
	out := make([]domain.MuscleTarget, 0, len(targets))
	for _, t := range targets {
		if seed, ok := m.muscles[t.Name]; ok {
			t.DisplayName = seed.DisplayName
		}
		out = append(out, t)
	}
	return out
}

func (m *MemGraph) GetExercisesByIDs(_ context.Context, ids []int32) ([]*domain.Exercise, error) {
	m.mu.Lock()
	defer m.mu.Unlock()

	out := make([]*domain.Exercise, 0, len(ids))
	for _, id := range ids {
		if ex, ok := m.byID[id]; ok {
			clone := *ex
			out = append(out, &clone)
		}
	}
	return out, nil
}

func (m *MemGraph) GetExerciseByName(_ context.Context, name string) (*domain.Exercise, error) {
	m.mu.Lock()
	defer m.mu.Unlock()

	id, ok := m.byName[strings.ToLower(name)]
	if !ok {
		return nil, nil
	}
	clone := *m.byID[id]
	return &clone, nil
}

func (m *MemGraph) GetMuscles(_ context.Context, names []string) ([]domain.Muscle, error) {
	want := map[string]bool{}
	for _, n := range names {
		want[n] = true
	}

	out := make([]domain.Muscle, 0)
	for _, seed := range graph.Muscles { // taxonomy order, deterministic
		if len(names) > 0 && !want[seed.Name] {
			continue
		}
		out = append(out, domain.Muscle{
			Name:             seed.Name,
			DisplayName:      seed.DisplayName,
			Size:             seed.Size,
			RecoveryHours:    seed.RecoveryHours,
			Antagonist:       seed.Antagonist,
			IsCompoundTarget: seed.IsCompoundTarget,
		})
	}
	return out, nil
}

// FindSubstitutionCandidates returns exercises sharing at least one targeted
// muscle, with the same structural facts the Neo4j query computes.
func (m *MemGraph) FindSubstitutionCandidates(
	_ context.Context,
	exerciseID int32,
	excludeIDs []int32,
	excludeJoints []string,
) ([]domain.SubstitutionCandidate, error) {
	m.mu.Lock()
	defer m.mu.Unlock()

	orig, ok := m.byID[exerciseID]
	if !ok {
		return nil, nil
	}

	excludedID := map[int32]bool{}
	for _, id := range excludeIDs {
		excludedID[id] = true
	}
	excludedJoint := map[string]bool{}
	for _, j := range excludeJoints {
		excludedJoint[j] = true
	}
	origMuscles := muscleNameSet(orig.Muscles)

	candidates := make([]domain.SubstitutionCandidate, 0)
	for id, cand := range m.byID {
		if id == exerciseID || excludedID[id] {
			continue
		}
		if !sharesMuscle(origMuscles, cand.Muscles) {
			continue
		}
		if stressesExcludedJoint(cand.Safety.JointStressAreas, excludedJoint) {
			continue
		}

		samePattern := cand.MovementPattern != "" && cand.MovementPattern == orig.MovementPattern
		relatedWeight := 0.0
		if !samePattern {
			relatedWeight = m.patternRel[pair(orig.MovementPattern, cand.MovementPattern)]
		}
		sameEquip := cand.Attributes.Equipment != "" && cand.Attributes.Equipment == orig.Attributes.Equipment
		similarEquip := !sameEquip && m.equipRel[pair(orig.Attributes.Equipment, cand.Attributes.Equipment)]

		clone := *cand
		candidates = append(candidates, domain.SubstitutionCandidate{
			Exercise:             &clone,
			SamePattern:          samePattern,
			RelatedPatternWeight: relatedWeight,
			SameEquipment:        sameEquip,
			SimilarEquipment:     similarEquip,
		})
	}
	return candidates, nil
}

func muscleNameSet(targets []domain.MuscleTarget) map[string]bool {
	set := make(map[string]bool, len(targets))
	for _, t := range targets {
		set[t.Name] = true
	}
	return set
}

func sharesMuscle(origMuscles map[string]bool, candMuscles []domain.MuscleTarget) bool {
	for _, t := range candMuscles {
		if origMuscles[t.Name] {
			return true
		}
	}
	return false
}

func stressesExcludedJoint(joints []string, excluded map[string]bool) bool {
	for _, j := range joints {
		if excluded[j] {
			return true
		}
	}
	return false
}
