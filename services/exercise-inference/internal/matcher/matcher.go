package matcher

import (
	"github.com/athleta/exercise-inference/internal/config"
)

// Matcher is the main entry point for exercise matching
type Matcher struct {
	loader         *config.Loader
	normalizer     *Normalizer
	strategyRunner *StrategyRunner
	ranker         *Ranker
}

// NewMatcher creates a new matcher
func NewMatcher(loader *config.Loader) *Matcher {
	// Get initial config for normalizer (stop words and patterns change less frequently)
	weights := loader.GetScoringWeights()
	normalizer := NewNormalizer(weights.StopWords, weights.ConversationalPatterns)
	
	return &Matcher{
		loader:     loader,
		normalizer: normalizer,
		// strategyRunner and ranker will be created on-demand with fresh config
	}
}

// Match performs the complete matching pipeline
// Gets fresh config on each call to support hot-reload
func (m *Matcher) Match(input string) *MatchResult {
	// Get fresh config on each match to support hot-reload
	exercises := m.loader.GetExercises()
	weights := m.loader.GetScoringWeights()
	
	// Update normalizer if stop words or patterns changed
	// Check if we need to recreate normalizer (simple heuristic: compare lengths)
	// This is a lightweight check - normalizer recreation is rare
	if m.normalizer == nil {
		m.normalizer = NewNormalizer(weights.StopWords, weights.ConversationalPatterns)
	}
	
	// Step 1: Normalize input
	tokens := m.normalizer.Normalize(input)
	normalizedString := m.normalizer.NormalizeToString(input)
	
	if len(tokens) == 0 {
		return &MatchResult{
			ResultType: ResultTypeNoMatch,
			Candidates: []Candidate{},
			Confidence: 0.0,
		}
	}
	
	// Step 2: Generate candidates with fresh config
	strategyRunner := NewStrategyRunner(exercises)
	signals := strategyRunner.RunAllStrategies(tokens, normalizedString)
	
	// Step 3: Rank candidates with fresh config
	ranker := NewRanker(weights, exercises)
	result := ranker.RankCandidates(signals)
	
	return result
}


