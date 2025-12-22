package matcher

import (
	"sort"

	"github.com/athleta/exercise-inference/internal/config"
)

// ResultType represents the type of match result
type ResultType int

const (
	ResultTypeMatch ResultType = iota
	ResultTypeAmbiguous
	ResultTypeLowConfidence
	ResultTypeNoMatch
)

// Candidate represents a ranked exercise candidate
type Candidate struct {
	ExerciseID    string
	CanonicalName string
	Score         float32
	MatchMethod   string
	MuscleGroups  []string
}

// MatchResult represents the final match result
type MatchResult struct {
	ResultType   ResultType
	TopCandidate *Candidate
	Candidates   []Candidate
	Confidence   float32
}

// Ranker handles candidate scoring and ranking
type Ranker struct {
	weights   *config.ScoringWeightsConfig
	exercises *config.ExercisesConfig
}

// NewRanker creates a new ranker
func NewRanker(weights *config.ScoringWeightsConfig, exercises *config.ExercisesConfig) *Ranker {
	return &Ranker{
		weights:   weights,
		exercises: exercises,
	}
}

// RankCandidates ranks candidates using max signal scoring
func (r *Ranker) RankCandidates(signals []CandidateSignal) *MatchResult {
	if len(signals) == 0 {
		return &MatchResult{
			ResultType: ResultTypeNoMatch,
			Candidates: []Candidate{},
			Confidence: 0.0,
		}
	}
	
	// Group signals by exercise ID and compute max weighted score per exercise
	exerciseScores := make(map[string]*candidateScore)
	
	for _, signal := range signals {
		weight := r.getWeight(signal.Strategy)
		weightedScore := signal.Score * float32(weight)
		
		if existing, exists := exerciseScores[signal.ExerciseID]; exists {
			// Use MAX score (not sum) to prevent inflation
			if weightedScore > existing.Score {
				existing.Score = weightedScore
				existing.MatchMethod = signal.Strategy
			}
		} else {
			exerciseScores[signal.ExerciseID] = &candidateScore{
				ExerciseID:  signal.ExerciseID,
				Score:       weightedScore,
				MatchMethod: signal.Strategy,
			}
		}
	}
	
	// Convert to candidates and sort by score
	candidates := make([]Candidate, 0, len(exerciseScores))
	for _, score := range exerciseScores {
		ex := r.findExercise(score.ExerciseID)
		if ex == nil {
			continue
		}
		
		candidates = append(candidates, Candidate{
			ExerciseID:    score.ExerciseID,
			CanonicalName: ex.CanonicalName,
			Score:         score.Score,
			MatchMethod:   score.MatchMethod,
			MuscleGroups:  ex.MuscleGroups,
		})
	}
	
	// Sort by score descending
	sort.Slice(candidates, func(i, j int) bool {
		return candidates[i].Score > candidates[j].Score
	})
	
	// Apply thresholds to determine result type
	return r.applyThresholds(candidates)
}

// applyThresholds applies decision thresholds
func (r *Ranker) applyThresholds(candidates []Candidate) *MatchResult {
	if len(candidates) == 0 {
		return &MatchResult{
			ResultType: ResultTypeNoMatch,
			Candidates: []Candidate{},
			Confidence: 0.0,
		}
	}
	
	topScore := candidates[0].Score
	matchMin := float32(r.weights.Thresholds.MatchMin)
	lowConfMin := float32(r.weights.Thresholds.LowConfidenceMin)
	ambiguousGap := float32(r.weights.Thresholds.AmbiguousGap)
	
	// Check for NO_MATCH
	if topScore < lowConfMin {
		return &MatchResult{
			ResultType: ResultTypeNoMatch,
			Candidates: []Candidate{},
			Confidence: topScore,
		}
	}
	
	// Check for LOW_CONFIDENCE
	if topScore < matchMin {
		top3 := r.getTopN(candidates, 3)
		return &MatchResult{
			ResultType:   ResultTypeLowConfidence,
			TopCandidate: nil,
			Candidates:   top3,
			Confidence:   topScore,
		}
	}
	
	// Check for AMBIGUOUS (top score >= matchMin but gap to second is small)
	if len(candidates) > 1 {
		secondScore := candidates[1].Score
		gap := topScore - secondScore
		
		if gap <= ambiguousGap {
			top3 := r.getTopN(candidates, 3)
			return &MatchResult{
				ResultType:   ResultTypeAmbiguous,
				TopCandidate: nil,
				Candidates:   top3,
				Confidence:   topScore,
			}
		}
	}
	
	// MATCH - clear winner
	return &MatchResult{
		ResultType:   ResultTypeMatch,
		TopCandidate: &candidates[0],
		Candidates:   []Candidate{},
		Confidence:   topScore,
	}
}

// getTopN returns top N candidates
func (r *Ranker) getTopN(candidates []Candidate, n int) []Candidate {
	if len(candidates) < n {
		n = len(candidates)
	}
	return candidates[:n]
}

// getWeight gets the weight for a strategy
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
		return 0.5 // Default weight
	}
}

// findExercise finds an exercise by ID
func (r *Ranker) findExercise(id string) *config.ExerciseConfig {
	for _, ex := range r.exercises.Exercises {
		if ex.ID == id {
			return &ex
		}
	}
	return nil
}

// candidateScore is an internal structure for scoring
type candidateScore struct {
	ExerciseID  string
	Score       float32
	MatchMethod string
}


