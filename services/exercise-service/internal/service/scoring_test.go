package service

import (
	"strings"
	"testing"

	"github.com/athleta/exercise-service/internal/domain"
)

func mt(name, role string) domain.MuscleTarget {
	return domain.MuscleTarget{Name: name, Role: role, ActivationPercent: domain.ActivationForRole(role)}
}

func TestWeightedMuscleSimilarity(t *testing.T) {
	a := []domain.MuscleTarget{mt("mid_chest", domain.RolePrimeMover), mt("triceps", domain.RoleSynergist)}

	cases := []struct {
		name   string
		b      []domain.MuscleTarget
		expect func(float64) bool
		desc   string
	}{
		{"identical", a, func(s float64) bool { return s == 1.0 }, "==1"},
		{"disjoint", []domain.MuscleTarget{mt("quadriceps", domain.RolePrimeMover)}, func(s float64) bool { return s == 0.0 }, "==0"},
		{"one empty", nil, func(s float64) bool { return s == 0.0 }, "==0"},
		{"partial overlap", []domain.MuscleTarget{mt("mid_chest", domain.RolePrimeMover)}, func(s float64) bool { return s > 0 && s < 1 }, "in (0,1)"},
		{
			"same muscle different role -> lower than identical",
			[]domain.MuscleTarget{mt("mid_chest", domain.RoleStabilizer), mt("triceps", domain.RoleStabilizer)},
			func(s float64) bool { return s > 0 && s < 1 }, "in (0,1)",
		},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			got := weightedMuscleSimilarity(a, c.b)
			if !c.expect(got) {
				t.Errorf("similarity = %v, want %s", got, c.desc)
			}
		})
	}

	// One empty side is zero similarity.
	if s := weightedMuscleSimilarity(a, nil); s != 0.0 {
		t.Errorf("one-empty similarity = %v, want 0", s)
	}
}

func bench() *domain.Exercise {
	return &domain.Exercise{
		MovementPattern: domain.PatternPush,
		ExerciseType:    domain.TypeCompound,
		Attributes:      domain.Attributes{Equipment: "barbell"},
		Safety:          domain.SafetyProfile{ComplexityScore: 0.6},
		Muscles: []domain.MuscleTarget{
			mt("mid_chest", domain.RolePrimeMover),
			mt("triceps", domain.RoleSynergist),
		},
	}
}

// TestAffinityScoring checks the structural-affinity blend: a near-twin
// candidate must outscore a structurally distant one.
func TestAffinityScoring(t *testing.T) {
	original := bench()

	twin := domain.SubstitutionCandidate{
		Exercise:      bench(), // same muscles/pattern/type
		SamePattern:   true,
		SameEquipment: true,
	}
	distant := domain.SubstitutionCandidate{
		Exercise: &domain.Exercise{
			MovementPattern: domain.PatternSquat,
			ExerciseType:    domain.TypeCompound,
			Attributes:      domain.Attributes{Equipment: "machine"},
			Safety:          domain.SafetyProfile{ComplexityScore: 0.1},
			Muscles:         []domain.MuscleTarget{mt("quadriceps", domain.RolePrimeMover)},
		},
		// No pattern/equipment relation -> all structural facts false.
	}

	twinScore, _ := scoreCandidate(original, twin)
	distantScore, _ := scoreCandidate(original, distant)

	if twinScore <= distantScore {
		t.Errorf("twin %.3f should outscore distant %.3f", twinScore, distantScore)
	}
	if twinScore < 0 || twinScore > 1 {
		t.Errorf("score %.3f out of [0,1]", twinScore)
	}
	// Identical twin should approach the ceiling.
	if twinScore < 0.95 {
		t.Errorf("identical twin score %.3f, want near 1.0", twinScore)
	}
}

func TestSubstitutionReason(t *testing.T) {
	original := bench()
	twin := domain.SubstitutionCandidate{Exercise: bench(), SamePattern: true, SameEquipment: true}

	_, details := scoreCandidate(original, twin)
	reason := substitutionReason(details)

	for _, want := range []string{"same muscles", "same movement pattern", "same equipment", "same exercise type"} {
		if !strings.Contains(reason, want) {
			t.Errorf("reason %q missing %q", reason, want)
		}
	}

	// Empty details -> graceful fallback.
	if got := substitutionReason(matchDetails{}); got != "suitable alternative" {
		t.Errorf("empty reason = %q, want fallback", got)
	}
}
