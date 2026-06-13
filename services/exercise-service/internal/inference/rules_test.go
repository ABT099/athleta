package inference

import (
	"testing"

	"github.com/athleta/exercise-service/internal/domain"
)

// roleOf returns the role assigned to a muscle, or "" if absent.
func roleOf(targets []domain.MuscleTarget, muscle string) string {
	for _, t := range targets {
		if t.Name == muscle {
			return t.Role
		}
	}
	return ""
}

func TestInferMuscleTargets(t *testing.T) {
	p := NewParser()
	rules := NewRulesEngine()

	cases := []struct {
		name        string
		input       string
		wantPrime   []string // every listed muscle must be a prime_mover
		wantRole    map[string]string
		wantAbsent  []string
	}{
		{
			name:      "flat bench -> mid chest prime",
			input:     "Barbell Bench Press",
			wantPrime: []string{"mid_chest"},
			wantRole:  map[string]string{"triceps": domain.RoleSynergist},
		},
		{
			name:      "incline -> upper chest prime",
			input:     "Incline Dumbbell Press",
			wantPrime: []string{"upper_chest"},
		},
		{
			name:      "decline -> lower chest prime",
			input:     "Decline Bench Press",
			wantPrime: []string{"lower_chest"},
		},
		{
			name:      "overhead press -> delts prime",
			input:     "Overhead Press",
			wantPrime: []string{"anterior_delt", "lateral_delt"},
		},
		{
			name:      "vertical pull -> lats prime",
			input:     "Lat Pulldown",
			wantPrime: []string{"lats"},
		},
		{
			name:      "horizontal pull -> mid back + lats prime",
			input:     "Barbell Row",
			wantPrime: []string{"mid_back", "lats"},
		},
		{
			name:      "squat -> quads + glutes prime",
			input:     "Barbell Back Squat",
			wantPrime: []string{"quadriceps", "glutes"},
		},
		{
			name:      "hinge -> posterior chain prime",
			input:     "Conventional Deadlift",
			wantPrime: []string{"glutes", "hamstrings", "erector_spinae"},
		},
		{
			name:      "carry -> grip + traps + core prime",
			input:     "Farmers Carry",
			wantPrime: []string{"forearms", "upper_traps", "abs"},
		},
		{
			name:      "rotation has real prime movers (audit fix)",
			input:     "Cable Woodchop",
			wantPrime: []string{"abs"},
		},
		{
			name:      "isolation curl -> biceps prime, forearms synergist",
			input:     "Barbell Bicep Curl",
			wantPrime: []string{"biceps"},
			wantRole:  map[string]string{"forearms": domain.RoleSynergist},
		},
		{
			name:      "isolation lateral raise -> side delt prime",
			input:     "Dumbbell Lateral Raise",
			wantPrime: []string{"lateral_delt"},
		},
	}

	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			targets := rules.InferMuscleTargets(p.Parse(c.input))
			if len(targets) == 0 {
				t.Fatal("no muscle targets produced")
			}
			for _, m := range c.wantPrime {
				if roleOf(targets, m) != domain.RolePrimeMover {
					t.Errorf("%s: %q role = %q, want prime_mover", c.input, m, roleOf(targets, m))
				}
			}
			for m, role := range c.wantRole {
				if roleOf(targets, m) != role {
					t.Errorf("%s: %q role = %q, want %q", c.input, m, roleOf(targets, m), role)
				}
			}
			for _, m := range c.wantAbsent {
				if roleOf(targets, m) != "" {
					t.Errorf("%s: %q present, want absent", c.input, m)
				}
			}
			// Activation must match the assigned role for every target.
			for _, tgt := range targets {
				if tgt.ActivationPercent != domain.ActivationForRole(tgt.Role) {
					t.Errorf("%s: %q activation %d != role default", c.input, tgt.Name, tgt.ActivationPercent)
				}
			}
		})
	}
}

func TestUnilateralAddsCoreStabilizer(t *testing.T) {
	p := NewParser()
	rules := NewRulesEngine()

	// Single-arm row demands anti-rotation core; abs must appear as stabilizer.
	targets := rules.InferMuscleTargets(p.Parse("Single Arm Dumbbell Row"))
	if roleOf(targets, "abs") != domain.RoleStabilizer {
		t.Fatalf("unilateral row abs role = %q, want stabilizer", roleOf(targets, "abs"))
	}
}
