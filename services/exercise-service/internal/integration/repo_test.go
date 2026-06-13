//go:build integration

package integration

import (
	"testing"

	"github.com/neo4j/neo4j-go-driver/v6/neo4j"

	"github.com/athleta/exercise-service/internal/domain"
)

func benchFixture() *domain.Exercise {
	return &domain.Exercise{
		Name:              "Test Bench Press",
		MovementPattern:   domain.PatternPush,
		ExerciseType:      domain.TypeCompound,
		IntensityCategory: domain.IntensityCompoundHeavy,
		Attributes: domain.Attributes{
			Equipment: "barbell", Laterality: "bilateral", Angle: "flat",
			ForceVector: domain.VectorHorizontal,
		},
		Safety: domain.SafetyProfile{
			InjuryRiskLevel: 2.0, ComplexityScore: 0.6,
			JointStressAreas: []string{"shoulder", "elbow"},
		},
		Muscles: []domain.MuscleTarget{
			{Name: "mid_chest", Role: domain.RolePrimeMover, ActivationPercent: 85},
			{Name: "triceps", Role: domain.RoleSynergist, ActivationPercent: 55},
		},
	}
}

func TestUpsertAndGetRoundTrip(t *testing.T) {
	repo := newRepo(t)
	ctx := ctxT(t)

	id, err := repo.UpsertExercise(ctx, benchFixture())
	if err != nil {
		t.Fatalf("upsert: %v", err)
	}
	if id <= 0 {
		t.Fatalf("expected positive id, got %d", id)
	}

	got, err := repo.GetExercisesByIDs(ctx, []int32{id})
	if err != nil {
		t.Fatalf("get by id: %v", err)
	}
	if len(got) != 1 {
		t.Fatalf("got %d exercises, want 1", len(got))
	}
	ex := got[0]

	if ex.Name != "Test Bench Press" || ex.MovementPattern != domain.PatternPush {
		t.Errorf("round-trip mismatch: %+v", ex)
	}
	if ex.Attributes.Equipment != "barbell" || ex.Attributes.ForceVector != domain.VectorHorizontal {
		t.Errorf("attributes lost: %+v", ex.Attributes)
	}
	if len(ex.Safety.JointStressAreas) != 2 {
		t.Errorf("joints = %v, want 2", ex.Safety.JointStressAreas)
	}
	if len(ex.Muscles) != 2 {
		t.Errorf("muscles = %d, want 2", len(ex.Muscles))
	}
	// Display name must be hydrated from the Muscle node, not the relationship.
	for _, m := range ex.Muscles {
		if m.DisplayName == "" {
			t.Errorf("muscle %q missing display name", m.Name)
		}
	}
}

func TestRelationshipTypes(t *testing.T) {
	repo := newRepo(t)
	ctx := ctxT(t)
	if _, err := repo.UpsertExercise(ctx, benchFixture()); err != nil {
		t.Fatalf("upsert: %v", err)
	}

	driver := rawDriver(t)
	session := driver.NewSession(ctx, neo4j.SessionConfig{AccessMode: neo4j.AccessModeRead})
	defer session.Close(ctx)

	scalar := func(query string) int64 {
		res, err := session.Run(ctx, query, nil)
		if err != nil {
			t.Fatalf("query %q: %v", query, err)
		}
		res.Next(ctx)
		v, _ := res.Record().Get("c")
		n, _ := v.(int64)
		return n
	}

	// FOLLOWS_PATTERN -> exactly one push pattern.
	if c := scalar(`MATCH (:Exercise {name:'Test Bench Press'})-[:FOLLOWS_PATTERN]->(p:MovementPattern {name:'push'}) RETURN count(p) AS c`); c != 1 {
		t.Errorf("FOLLOWS_PATTERN count = %d, want 1", c)
	}
	// USES -> barbell.
	if c := scalar(`MATCH (:Exercise {name:'Test Bench Press'})-[:USES]->(e:Equipment {name:'barbell'}) RETURN count(e) AS c`); c != 1 {
		t.Errorf("USES count = %d, want 1", c)
	}
	// STRESSES -> two joints.
	if c := scalar(`MATCH (:Exercise {name:'Test Bench Press'})-[:STRESSES]->(j:Joint) RETURN count(j) AS c`); c != 2 {
		t.Errorf("STRESSES count = %d, want 2", c)
	}
	// TARGETS carries role + activation properties.
	if c := scalar(`MATCH (:Exercise {name:'Test Bench Press'})-[t:TARGETS {role:'prime_mover'}]->(:Muscle {name:'mid_chest'}) WHERE t.activation = 85 RETURN count(t) AS c`); c != 1 {
		t.Errorf("TARGETS prime_mover/activation count = %d, want 1", c)
	}
}

func TestUpsertIsUpdateNotDuplicate(t *testing.T) {
	repo := newRepo(t)
	ctx := ctxT(t)

	id1, _ := repo.UpsertExercise(ctx, benchFixture())

	// Re-upsert with changed equipment; same name -> same node, no duplicate.
	mod := benchFixture()
	mod.Attributes.Equipment = "dumbbell"
	id2, err := repo.UpsertExercise(ctx, mod)
	if err != nil {
		t.Fatalf("re-upsert: %v", err)
	}
	if id1 != id2 {
		t.Errorf("id changed on update: %d -> %d", id1, id2)
	}

	driver := rawDriver(t)
	session := driver.NewSession(ctx, neo4j.SessionConfig{AccessMode: neo4j.AccessModeRead})
	defer session.Close(ctx)
	res, _ := session.Run(ctx, `MATCH (e:Exercise {name:'Test Bench Press'}) RETURN count(e) AS c`, nil)
	res.Next(ctx)
	v, _ := res.Record().Get("c")
	if n, _ := v.(int64); n != 1 {
		t.Errorf("exercise node count = %d, want 1 (no duplicate)", n)
	}

	// Old USES edge replaced, not accumulated.
	got, _ := repo.GetExercisesByIDs(ctx, []int32{id2})
	if got[0].Attributes.Equipment != "dumbbell" {
		t.Errorf("equipment = %q, want dumbbell", got[0].Attributes.Equipment)
	}
}

func TestGetMusclesRepo(t *testing.T) {
	repo := newRepo(t)
	ctx := ctxT(t)

	all, err := repo.GetMuscles(ctx, nil)
	if err != nil {
		t.Fatalf("get all muscles: %v", err)
	}
	if len(all) != 20 {
		t.Fatalf("muscle count = %d, want 20", len(all))
	}

	one, err := repo.GetMuscles(ctx, []string{"biceps"})
	if err != nil {
		t.Fatalf("get biceps: %v", err)
	}
	if len(one) != 1 {
		t.Fatalf("biceps query returned %d", len(one))
	}
	b := one[0]
	if b.Size != domain.SizeSmall || b.RecoveryHours != 48 || b.Antagonist != "triceps" {
		t.Errorf("biceps metadata wrong: %+v", b)
	}
}

func TestFindSubstitutionCandidatesRepo(t *testing.T) {
	repo := newRepo(t)
	ctx := ctxT(t)

	origID, _ := repo.UpsertExercise(ctx, benchFixture())

	// A twin push exercise sharing mid_chest -> should surface as candidate.
	twin := benchFixture()
	twin.Name = "Twin Press"
	if _, err := repo.UpsertExercise(ctx, twin); err != nil {
		t.Fatalf("upsert twin: %v", err)
	}

	cands, err := repo.FindSubstitutionCandidates(ctx, origID, nil, nil)
	if err != nil {
		t.Fatalf("find candidates: %v", err)
	}
	if len(cands) != 1 {
		t.Fatalf("candidate count = %d, want 1", len(cands))
	}
	c := cands[0]
	if c.Exercise.Name != "Twin Press" {
		t.Errorf("candidate = %q, want Twin Press", c.Exercise.Name)
	}
	// Twin shares pattern (push) and equipment (barbell) -> exact-match facts.
	if !c.SamePattern || !c.SameEquipment {
		t.Errorf("facts = samePattern %v sameEquipment %v, want both true", c.SamePattern, c.SameEquipment)
	}

	// Joint exclusion: excluding shoulder removes the shoulder-stressing twin.
	excluded, err := repo.FindSubstitutionCandidates(ctx, origID, nil, []string{"shoulder"})
	if err != nil {
		t.Fatalf("find with joint exclusion: %v", err)
	}
	if len(excluded) != 0 {
		t.Errorf("joint exclusion returned %d candidates, want 0", len(excluded))
	}

	// ID exclusion removes the twin too.
	twinID, _ := repo.GetExerciseByName(ctx, "Twin Press")
	idExcluded, _ := repo.FindSubstitutionCandidates(ctx, origID, []int32{twinID.ID}, nil)
	if len(idExcluded) != 0 {
		t.Errorf("id exclusion returned %d, want 0", len(idExcluded))
	}
}
