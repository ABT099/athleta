package inference

import (
	"testing"

	"github.com/athleta/exercise-service/internal/domain"
)

// These cases pin down bugs from the old exercise-inference service:
//   - "curl"/"raise"/"extension" verbs were mapped to compound push/pull
//   - vertical pulls were detected via an impossible implement value
//   - substring keyword matching corrupted words ("landmine" contains "im")
func TestParse(t *testing.T) {
	parser := NewParser()

	tests := []struct {
		name        string
		input       string
		pattern     string
		exType      string
		forceVector string
		isolation   string
		equipment   string
		angle       string
	}{
		{
			name:    "bicep curl is isolation, not a compound pull",
			input:   "Barbell Bicep Curl",
			pattern: domain.PatternPull, exType: domain.TypeIsolation,
			isolation: "biceps", equipment: "barbell",
		},
		{
			name:    "lateral raise is isolation targeting side delts",
			input:   "Dumbbell Lateral Raise",
			pattern: domain.PatternPush, exType: domain.TypeIsolation,
			isolation: "lateral_delt", equipment: "dumbbell",
		},
		{
			name:    "leg extension is a quad isolation, not a press",
			input:   "Leg Extension",
			pattern: domain.PatternSquat, exType: domain.TypeIsolation,
			isolation: "quadriceps", equipment: "bodyweight",
		},
		{
			name:    "lat pulldown is a vertical pull",
			input:   "Lat Pulldown",
			pattern: domain.PatternPull, exType: domain.TypeCompound,
			forceVector: domain.VectorVertical,
		},
		{
			name:    "pull up is a vertical pull",
			input:   "Pull Up",
			pattern: domain.PatternPull, exType: domain.TypeCompound,
			forceVector: domain.VectorVertical, equipment: "bodyweight",
		},
		{
			name:    "row is a horizontal pull",
			input:   "Barbell Row",
			pattern: domain.PatternPull, exType: domain.TypeCompound,
			forceVector: domain.VectorHorizontal, equipment: "barbell",
		},
		{
			name:    "landmine survives keyword extraction intact",
			input:   "Landmine Press",
			pattern: domain.PatternPush, exType: domain.TypeCompound,
			equipment: "landmine",
		},
		{
			name:    "overhead press is vertical with overhead angle",
			input:   "Overhead Press",
			pattern: domain.PatternPush, exType: domain.TypeCompound,
			forceVector: domain.VectorVertical, equipment: "bodyweight", angle: "overhead",
		},
		{
			name:    "split squat classifies as lunge, not squat",
			input:   "Bulgarian Split Squat",
			pattern: domain.PatternLunge, exType: domain.TypeCompound,
		},
		{
			name:    "incline dumbbell press keeps angle and equipment",
			input:   "Incline Dumbbell Press",
			pattern: domain.PatternPush, exType: domain.TypeCompound,
			equipment: "dumbbell", angle: "incline",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := parser.Parse(tt.input)

			if got.MovementPattern != tt.pattern {
				t.Errorf("pattern = %q, want %q", got.MovementPattern, tt.pattern)
			}
			if got.ExerciseType != tt.exType {
				t.Errorf("exercise type = %q, want %q", got.ExerciseType, tt.exType)
			}
			if tt.forceVector != "" && got.Modifiers.ForceVector != tt.forceVector {
				t.Errorf("force vector = %q, want %q", got.Modifiers.ForceVector, tt.forceVector)
			}
			if tt.isolation != "" && got.IsolationTarget != tt.isolation {
				t.Errorf("isolation target = %q, want %q", got.IsolationTarget, tt.isolation)
			}
			if tt.equipment != "" && got.Modifiers.Equipment != tt.equipment {
				t.Errorf("equipment = %q, want %q", got.Modifiers.Equipment, tt.equipment)
			}
			if tt.angle != "" && got.Modifiers.Angle != tt.angle {
				t.Errorf("angle = %q, want %q", got.Modifiers.Angle, tt.angle)
			}
		})
	}
}

func TestIntensityCategory(t *testing.T) {
	parser := NewParser()
	safety := NewSafetyAnalyzer()

	tests := []struct {
		input string
		want  string
	}{
		// Barbell rows were misclassified compound_moderate in the old service.
		{"Barbell Row", domain.IntensityCompoundHeavy},
		{"Barbell Back Squat", domain.IntensityCompoundHeavy},
		{"Conventional Deadlift", domain.IntensityCompoundHeavy},
		{"Dumbbell Bench Press", domain.IntensityCompoundModerate},
		{"Leg Press machine", domain.IntensityCompoundModerate},
		{"Barbell Bicep Curl", domain.IntensityIsolation},
		{"Dumbbell Lateral Raise", domain.IntensityIsolation},
	}

	for _, tt := range tests {
		parsed := parser.Parse(tt.input)
		if got := safety.IntensityCategory(parsed); got != tt.want {
			t.Errorf("IntensityCategory(%q) = %q, want %q", tt.input, got, tt.want)
		}
	}
}
