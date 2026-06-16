package service

import (
	"math"
	"strings"

	"github.com/athleta/exercise-service/internal/domain"
)

// Substitution scoring. The hybrid score blends what the exercise does to
// muscles (activation-weighted Jaccard) with how it is performed (pattern/
// equipment affinity, exercise type, complexity). Every weight — including
// how the graph's structural facts become pattern/equipment scores — lives
// here, so the entire scoring policy reads top to bottom in one module.
const (
	muscleWeight     = 0.6
	structuralWeight = 0.4

	// Structural sub-weights (sum to 1).
	patternWeight    = 0.5
	equipmentWeight  = 0.2
	typeWeight       = 0.15
	complexityWeight = 0.15

	// How structural facts score: an exact match is full credit, a
	// SIMILAR_TO equipment edge is half.
	sameScore            = 1.0
	similarEquipmentScore = 0.5
)

type matchDetails struct {
	muscleSimilarity     float64
	patternScore         float64
	equipmentScore       float64
	typeScore            float64
	complexitySimilarity float64
}

func scoreCandidate(original *domain.Exercise, candidate domain.SubstitutionCandidate) (float64, matchDetails) {
	details := matchDetails{
		muscleSimilarity: weightedMuscleSimilarity(original.Muscles, candidate.Exercise.Muscles),
		patternScore:     patternScore(candidate),
		equipmentScore:   equipmentScore(candidate),
	}

	if original.ExerciseType != "" && original.ExerciseType == candidate.Exercise.ExerciseType {
		details.typeScore = 1.0
	}

	complexityDiff := math.Abs(float64(original.Safety.ComplexityScore - candidate.Exercise.Safety.ComplexityScore))
	details.complexitySimilarity = math.Max(0, 1.0-complexityDiff)

	structural := patternWeight*details.patternScore +
		equipmentWeight*details.equipmentScore +
		typeWeight*details.typeScore +
		complexityWeight*details.complexitySimilarity

	score := muscleWeight*details.muscleSimilarity + structuralWeight*structural
	return score, details
}

// patternScore turns the graph's pattern facts into a [0,1] affinity: full
// credit for the same pattern, the RELATED_TO edge weight otherwise.
func patternScore(c domain.SubstitutionCandidate) float64 {
	if c.SamePattern {
		return sameScore
	}
	return c.RelatedPatternWeight
}

// equipmentScore turns the graph's equipment facts into a [0,1] affinity.
func equipmentScore(c domain.SubstitutionCandidate) float64 {
	switch {
	case c.SameEquipment:
		return sameScore
	case c.SimilarEquipment:
		return similarEquipmentScore
	default:
		return 0
	}
}

// weightedMuscleSimilarity is the activation-weighted Jaccard similarity of
// two muscle target sets, in [0,1].
func weightedMuscleSimilarity(a, b []domain.MuscleTarget) float64 {
	if len(a) == 0 && len(b) == 0 {
		return 1.0
	}
	if len(a) == 0 || len(b) == 0 {
		return 0.0
	}

	activations := func(targets []domain.MuscleTarget) map[string]float64 {
		m := make(map[string]float64, len(targets))
		for _, t := range targets {
			m[t.Name] = float64(t.ActivationPercent) / 100.0
		}
		return m
	}

	mapA := activations(a)
	mapB := activations(b)

	var intersection, union float64
	seen := make(map[string]bool)
	for name, actA := range mapA {
		actB := mapB[name]
		intersection += math.Min(actA, actB)
		union += math.Max(actA, actB)
		seen[name] = true
	}
	for name, actB := range mapB {
		if !seen[name] {
			union += actB
		}
	}

	if union == 0 {
		return 0
	}
	return intersection / union
}

// substitutionReason builds the human-readable explanation for a candidate.
func substitutionReason(details matchDetails) string {
	reasons := []string{}

	if details.muscleSimilarity >= 0.8 {
		reasons = append(reasons, "targets same muscles")
	} else if details.muscleSimilarity >= 0.5 {
		reasons = append(reasons, "targets similar muscles")
	}

	if details.patternScore >= 0.9 {
		reasons = append(reasons, "same movement pattern")
	} else if details.patternScore >= 0.3 {
		reasons = append(reasons, "related movement pattern")
	}

	if details.equipmentScore >= 0.9 {
		reasons = append(reasons, "same equipment")
	} else if details.equipmentScore >= 0.5 {
		reasons = append(reasons, "interchangeable equipment")
	}

	if details.typeScore == 1.0 {
		reasons = append(reasons, "same exercise type")
	}

	if details.complexitySimilarity >= 0.9 {
		reasons = append(reasons, "similar complexity level")
	}

	if len(reasons) == 0 {
		return "suitable alternative"
	}
	return strings.Join(reasons, ", ")
}
