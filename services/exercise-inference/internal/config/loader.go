package config

import (
	"encoding/json"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"sync"

	"github.com/fsnotify/fsnotify"
)

// Loader manages configuration loading and hot-reload
type Loader struct {
	exercisesPath      string
	scoringWeightsPath string
	
	mu                 sync.RWMutex
	exercises          *ExercisesConfig
	scoringWeights     *ScoringWeightsConfig
	
	watcher            *fsnotify.Watcher
	stopWatcher        chan struct{}
}

// NewLoader creates a new config loader
func NewLoader(exercisesPath, scoringWeightsPath string) (*Loader, error) {
	loader := &Loader{
		exercisesPath:      exercisesPath,
		scoringWeightsPath: scoringWeightsPath,
		stopWatcher:        make(chan struct{}),
	}
	
	// Load initial config
	if err := loader.loadAll(); err != nil {
		return nil, fmt.Errorf("failed to load initial config: %w", err)
	}
	
	// Setup file watcher
	if err := loader.setupWatcher(); err != nil {
		log.Printf("Warning: Failed to setup file watcher: %v", err)
		// Continue without hot-reload
	}
	
	return loader, nil
}

// loadAll loads both config files
func (l *Loader) loadAll() error {
	// Load exercises
	exercises, err := l.loadExercises()
	if err != nil {
		return fmt.Errorf("failed to load exercises: %w", err)
	}
	
	// Load scoring weights
	weights, err := l.loadScoringWeights()
	if err != nil {
		return fmt.Errorf("failed to load scoring weights: %w", err)
	}
	
	// Validate before swapping
	if err := validateExercises(exercises); err != nil {
		return fmt.Errorf("validation failed: %w", err)
	}
	
	// Atomic swap
	l.mu.Lock()
	l.exercises = exercises
	l.scoringWeights = weights
	l.mu.Unlock()
	
	log.Println("✓ Configuration loaded successfully")
	return nil
}

// loadExercises loads exercises.json
func (l *Loader) loadExercises() (*ExercisesConfig, error) {
	data, err := os.ReadFile(l.exercisesPath)
	if err != nil {
		return nil, err
	}
	
	var config ExercisesConfig
	if err := json.Unmarshal(data, &config); err != nil {
		return nil, fmt.Errorf("failed to parse exercises.json: %w", err)
	}
	
	return &config, nil
}

// loadScoringWeights loads scoring_weights.json
func (l *Loader) loadScoringWeights() (*ScoringWeightsConfig, error) {
	data, err := os.ReadFile(l.scoringWeightsPath)
	if err != nil {
		return nil, err
	}
	
	var config ScoringWeightsConfig
	if err := json.Unmarshal(data, &config); err != nil {
		return nil, fmt.Errorf("failed to parse scoring_weights.json: %w", err)
	}
	
	return &config, nil
}

// validateExercises validates the exercises config
func validateExercises(config *ExercisesConfig) error {
	if len(config.Exercises) == 0 {
		return fmt.Errorf("exercises array is empty")
	}
	
	// Track aliases to detect duplicates
	aliasMap := make(map[string]string)
	
	for _, ex := range config.Exercises {
		// Check required fields
		if ex.ID == "" {
			return fmt.Errorf("exercise missing required field: id")
		}
		if ex.CanonicalName == "" {
			return fmt.Errorf("exercise %s missing required field: canonical_name", ex.ID)
		}
		if len(ex.Aliases) == 0 {
			return fmt.Errorf("exercise %s missing required field: aliases", ex.ID)
		}
		
		// Check for duplicate aliases
		allNames := append([]string{ex.CanonicalName}, ex.Aliases...)
		allNames = append(allNames, ex.Slang...)
		allNames = append(allNames, ex.CommonTypos...)
		
		for _, name := range allNames {
			normalized := normalizeForComparison(name)
			if existingID, exists := aliasMap[normalized]; exists {
				log.Printf("Warning: Duplicate alias '%s' found in exercises %s and %s", name, existingID, ex.ID)
			} else {
				aliasMap[normalized] = ex.ID
			}
		}
	}
	
	return nil
}

// normalizeForComparison normalizes a string for duplicate detection
func normalizeForComparison(s string) string {
	// Simple normalization - lowercase and trim
	// More sophisticated normalization could be added
	return s
}

// setupWatcher sets up file watching for hot-reload
func (l *Loader) setupWatcher() error {
	watcher, err := fsnotify.NewWatcher()
	if err != nil {
		return err
	}
	
	l.watcher = watcher
	
	// Watch config directory
	configDir := filepath.Dir(l.exercisesPath)
	if err := watcher.Add(configDir); err != nil {
		return err
	}
	
	// Start watching goroutine
	go l.watchFiles()
	
	return nil
}

// watchFiles watches for file changes and reloads config
func (l *Loader) watchFiles() {
	for {
		select {
		case event, ok := <-l.watcher.Events:
			if !ok {
				return
			}
			
			// Only reload on write events
			if event.Op&fsnotify.Write == fsnotify.Write {
				filename := filepath.Base(event.Name)
				if filename == "exercises.json" || filename == "scoring_weights.json" {
					log.Printf("Config file changed: %s, reloading...", filename)
					
					// Try to reload
					if err := l.loadAll(); err != nil {
						log.Printf("Error reloading config: %v (keeping old config)", err)
					} else {
						log.Println("✓ Configuration reloaded successfully")
					}
				}
			}
			
		case err, ok := <-l.watcher.Errors:
			if !ok {
				return
			}
			log.Printf("File watcher error: %v", err)
			
		case <-l.stopWatcher:
			return
		}
	}
}

// GetExercises returns the current exercises config (thread-safe)
func (l *Loader) GetExercises() *ExercisesConfig {
	l.mu.RLock()
	defer l.mu.RUnlock()
	return l.exercises
}

// GetScoringWeights returns the current scoring weights config (thread-safe)
func (l *Loader) GetScoringWeights() *ScoringWeightsConfig {
	l.mu.RLock()
	defer l.mu.RUnlock()
	return l.scoringWeights
}

// Close stops the file watcher
func (l *Loader) Close() error {
	if l.watcher != nil {
		close(l.stopWatcher)
		return l.watcher.Close()
	}
	return nil
}

