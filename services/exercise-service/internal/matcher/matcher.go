package matcher

import (
	"github.com/athleta/exercise-service/internal/config"
)

// Matcher resolves free-form input against the curated exercise vocabulary.
type Matcher struct {
	loader *config.Loader
}

// NewMatcher creates a new matcher.
func NewMatcher(loader *config.Loader) *Matcher {
	return &Matcher{loader: loader}
}

// Match performs the complete matching pipeline. Config is read fresh on
// each call so hot-reloaded vocabulary takes effect immediately.
func (m *Matcher) Match(input string) *MatchResult {
	exercises := m.loader.GetExercises()
	weights := m.loader.GetScoringWeights()

	normalizer := NewNormalizer(weights.StopWords, weights.ConversationalPatterns)
	tokens := normalizer.Normalize(input)
	normalizedString := normalizer.NormalizeToString(input)

	if len(tokens) == 0 {
		return &MatchResult{ResultType: ResultTypeNoMatch, Candidates: []Candidate{}}
	}

	signals := NewStrategyRunner(exercises).RunAllStrategies(tokens, normalizedString)
	return NewRanker(weights, exercises).RankCandidates(signals)
}
