package matcher

import (
	"regexp"
	"strings"
)

// Normalizer handles text normalization and stop word removal.
type Normalizer struct {
	stopWords              map[string]bool
	conversationalPatterns []string
}

var spaceRegex = regexp.MustCompile(`\s+`)

// NewNormalizer creates a new normalizer with stop words and patterns.
func NewNormalizer(stopWords []string, conversationalPatterns []string) *Normalizer {
	stopWordMap := make(map[string]bool)
	for _, word := range stopWords {
		stopWordMap[strings.ToLower(word)] = true
	}
	// Contractions are dropped like stop words. Handled per-token so that
	// words containing these letter sequences (e.g. "landmine") are unharmed.
	for _, w := range []string{"i'm", "im", "i've", "ive"} {
		stopWordMap[w] = true
	}

	return &Normalizer{
		stopWords:              stopWordMap,
		conversationalPatterns: conversationalPatterns,
	}
}

// Normalize normalizes input text and returns tokens.
func (n *Normalizer) Normalize(input string) []string {
	text := strings.ToLower(input)

	// Remove conversational phrases before tokenization (they span words).
	for _, pattern := range n.conversationalPatterns {
		text = strings.ReplaceAll(text, strings.ToLower(pattern), " ")
	}

	text = strings.ReplaceAll(text, "'", " ")
	text = strings.ReplaceAll(text, "-", " ")
	text = strings.ReplaceAll(text, "_", " ")
	text = strings.TrimSpace(spaceRegex.ReplaceAllString(text, " "))

	tokens := strings.Fields(text)

	filtered := make([]string, 0, len(tokens))
	for _, token := range tokens {
		if n.stopWords[token] {
			continue
		}
		filtered = append(filtered, depluralize(token))
	}

	return filtered
}

// depluralize removes a trailing plural 's' from longer words, leaving words
// that naturally end in 's' ("press") or 'us'/'ss' endings alone.
func depluralize(token string) string {
	if len(token) > 4 && strings.HasSuffix(token, "s") {
		secondLast := token[len(token)-2]
		if secondLast != 's' && secondLast != 'u' {
			return token[:len(token)-1]
		}
	}
	return token
}

// NormalizeToString normalizes and returns as a single string.
func (n *Normalizer) NormalizeToString(input string) string {
	return strings.Join(n.Normalize(input), " ")
}
