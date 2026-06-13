// Package resolver owns name resolution policy: turning a raw exercise name
// into a decision about identity — "this is vocabulary exercise X" versus
// "infer it from its attributes". The matcher produces scored, four-valued
// match results; the resolver interprets them. Keeping the policy here lets
// the matcher stay pure scoring and makes the matched-vs-inferred decision
// unit-testable on its own.
package resolver

import "github.com/athleta/exercise-service/internal/matcher"

// Outcome is the resolved identity decision for a raw name.
type Outcome struct {
	// Matched reports whether the name resolved to a vocabulary exercise.
	Matched bool
	// VocabularyID / CanonicalName identify the matched exercise (set only
	// when Matched).
	VocabularyID  string
	CanonicalName string
	// Confidence is the matcher score for the resolution, in [0,1].
	Confidence float32
}

// Resolver applies resolution policy over the matcher's scored results.
type Resolver struct {
	matcher *matcher.Matcher
}

// New builds a resolver over a matcher.
func New(m *matcher.Matcher) *Resolver {
	return &Resolver{matcher: m}
}

// Resolve interprets a name. A clear MATCH resolves to its top candidate; an
// AMBIGUOUS result resolves to the highest-popularity candidate the ranker
// placed first (a wrong-but-common guess beats forcing the caller to choose).
// LOW_CONFIDENCE and NO_MATCH do not resolve — forcing a shaky canonical
// mapping is worse than inferring from attributes.
func (r *Resolver) Resolve(name string) Outcome {
	res := r.matcher.Match(name)

	switch res.ResultType {
	case matcher.ResultTypeMatch:
		if res.TopCandidate != nil {
			return matched(res.TopCandidate, res.Confidence)
		}
	case matcher.ResultTypeAmbiguous:
		if len(res.Candidates) > 0 {
			return matched(&res.Candidates[0], res.Confidence)
		}
	}

	return Outcome{Matched: false, Confidence: res.Confidence}
}

func matched(c *matcher.Candidate, confidence float32) Outcome {
	return Outcome{
		Matched:       true,
		VocabularyID:  c.ExerciseID,
		CanonicalName: c.CanonicalName,
		Confidence:    confidence,
	}
}
