package matcher

import (
	"regexp"
	"strings"
)

// Normalizer handles text normalization and stop word removal
type Normalizer struct {
	stopWords            map[string]bool
	conversationalPatterns []string
}

// NewNormalizer creates a new normalizer with stop words and patterns
func NewNormalizer(stopWords []string, conversationalPatterns []string) *Normalizer {
	stopWordMap := make(map[string]bool)
	for _, word := range stopWords {
		stopWordMap[strings.ToLower(word)] = true
	}
	
	return &Normalizer{
		stopWords:            stopWordMap,
		conversationalPatterns: conversationalPatterns,
	}
}

// Normalize normalizes input text and returns tokens
func (n *Normalizer) Normalize(input string) []string {
	// Step 1: Lowercase
	text := strings.ToLower(input)
	
	// Step 2: Remove conversational patterns first (before tokenization)
	for _, pattern := range n.conversationalPatterns {
		patternLower := strings.ToLower(pattern)
		text = strings.ReplaceAll(text, patternLower, " ")
	}
	// Handle contractions separately
	text = strings.ReplaceAll(text, "i'm", " ")
	text = strings.ReplaceAll(text, "im", " ")
	text = strings.ReplaceAll(text, "i've", " ")
	text = strings.ReplaceAll(text, "ive", " ")
	text = strings.ReplaceAll(text, "'", " ") // Remove apostrophes
	
	// Step 3: Normalize hyphens and underscores to spaces
	text = strings.ReplaceAll(text, "-", " ")
	text = strings.ReplaceAll(text, "_", " ")
	
	// Step 4: Remove duplicate spaces
	spaceRegex := regexp.MustCompile(`\s+`)
	text = spaceRegex.ReplaceAllString(text, " ")
	
	// Step 5: Trim
	text = strings.TrimSpace(text)
	
	// Step 6: Tokenize
	tokens := strings.Fields(text)
	
	// Step 7: Remove stop words and handle plurals
	filtered := make([]string, 0, len(tokens))
	for _, token := range tokens {
		if !n.stopWords[token] {
			// Handle plurals: remove trailing 's' only for common plural patterns
			// Don't remove 's' from words that naturally end in 's' (like "press", "crushers")
			// Only remove for words that are clearly plurals (length > 4 helps avoid "press" -> "pres")
			if len(token) > 4 && strings.HasSuffix(token, "s") {
				// Check if it's a common plural ending (not words ending in 'ss', 'us', etc.)
				secondLast := token[len(token)-2]
				if secondLast != 's' && secondLast != 'u' {
					token = token[:len(token)-1]
				}
			}
			filtered = append(filtered, token)
		}
	}
	
	return filtered
}

// NormalizeToString normalizes and returns as a single string
func (n *Normalizer) NormalizeToString(input string) string {
	tokens := n.Normalize(input)
	return strings.Join(tokens, " ")
}

