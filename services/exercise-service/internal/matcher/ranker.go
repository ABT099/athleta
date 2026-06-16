package matcher

import (
	"sort"

	"github.com/athleta/exercise-service/internal/config"
)

// ResultType represents the type of match result.
type ResultType int

const (
	ResultTypeMatch ResultType = iota
	ResultTypeAmbiguous
	ResultTypeLowConfidence
	ResultTypeNoMatch
)

// Candidate represents a ranked exercise candidate.
type Candidate struct {
	ExerciseID    string
	CanonicalName string
	Score         float32
	MatchMethod   string
	Popularity    float64
}

// MatchResult represents the final match result.
type MatchResult struct {
	ResultType   ResultType
	TopCandidate *Candidate
	Candidates   []Candidate
	Confidence   float32
}

// Ranker handles candidate scoring and ranking.
type Ranker struct {
	weights   *config.ScoringWeightsConfig
	exercises *config.ExercisesConfig
}

// NewRanker creates a new ranker.
func NewRanker(weights *config.ScoringWeightsConfig, exercises *config.ExercisesConfig) *Ranker {
	return &Ranker{weights: weights, exercises: exercises}
}

// RankCandidates ranks candidates using max-signal scoring: each exercise
// takes its single best weighted strategy score, preventing inflation from
// summing correlated signals. Ties break on popularity so that when the
// caller has to pick from an ambiguous result, the common interpretation
// comes first.
func (r *Ranker) RankCandidates(signals []CandidateSignal) *MatchResult {
	if len(signals) == 0 {
		return &MatchResult{ResultType: ResultTypeNoMatch, Candidates: []Candidate{}}
	}

	type candidateScore struct {
		Score       float32
		MatchMethod string
	}

	exerciseScores := make(map[string]*candidateScore)

	for _, signal := range signals {
		weightedScore := signal.Score * float32(r.getWeight(signal.Strategy))

		if existing, exists := exerciseScores[signal.ExerciseID]; exists {
			if weightedScore > existing.Score {
				existing.Score = weightedScore
				existing.MatchMethod = signal.Strategy
			}
		} else {
			exerciseScores[signal.ExerciseID] = &candidateScore{Score: weightedScore, MatchMethod: signal.Strategy}
		}
	}

	candidates := make([]Candidate, 0, len(exerciseScores))
	for id, score := range exerciseScores {
		ex := r.findExercise(id)
		if ex == nil {
			continue
		}
		candidates = append(candidates, Candidate{
			ExerciseID:    id,
			CanonicalName: ex.CanonicalName,
			Score:         score.Score,
			MatchMethod:   score.MatchMethod,
			Popularity:    ex.PopularityScore,
		})
	}

	sort.Slice(candidates, func(i, j int) bool {
		if candidates[i].Score != candidates[j].Score {
			return candidates[i].Score > candidates[j].Score
		}
		return candidates[i].Popularity > candidates[j].Popularity
	})

	return r.applyThresholds(candidates)
}

func (r *Ranker) applyThresholds(candidates []Candidate) *MatchResult {
	if len(candidates) == 0 {
		return &MatchResult{ResultType: ResultTypeNoMatch, Candidates: []Candidate{}}
	}

	topScore := candidates[0].Score
	matchMin := float32(r.weights.Thresholds.MatchMin)
	lowConfMin := float32(r.weights.Thresholds.LowConfidenceMin)
	ambiguousGap := float32(r.weights.Thresholds.AmbiguousGap)

	if topScore < lowConfMin {
		return &MatchResult{ResultType: ResultTypeNoMatch, Candidates: []Candidate{}, Confidence: topScore}
	}

	if topScore < matchMin {
		return &MatchResult{
			ResultType: ResultTypeLowConfidence,
			Candidates: topN(candidates, 3),
			Confidence: topScore,
		}
	}

	if len(candidates) > 1 && topScore-candidates[1].Score <= ambiguousGap {
		return &MatchResult{
			ResultType: ResultTypeAmbiguous,
			Candidates: topN(candidates, 3),
			Confidence: topScore,
		}
	}

	return &MatchResult{
		ResultType:   ResultTypeMatch,
		TopCandidate: &candidates[0],
		Candidates:   []Candidate{},
		Confidence:   topScore,
	}
}

func topN(candidates []Candidate, n int) []Candidate {
	if len(candidates) < n {
		n = len(candidates)
	}
	return candidates[:n]
}

func (r *Ranker) getWeight(strategy string) float64 {
	switch strategy {
	case "exact":
		return r.weights.MatchWeights.Exact
	case "alias":
		return r.weights.MatchWeights.Alias
	case "token_set":
		return r.weights.MatchWeights.TokenSet
	case "jaccard":
		return r.weights.MatchWeights.Jaccard
	case "phonetic":
		return r.weights.MatchWeights.Phonetic
	default:
		return 0.5
	}
}

func (r *Ranker) findExercise(id string) *config.ExerciseConfig {
	for i := range r.exercises.Exercises {
		if r.exercises.Exercises[i].ID == id {
			return &r.exercises.Exercises[i]
		}
	}
	return nil
}
