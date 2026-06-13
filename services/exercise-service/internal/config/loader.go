package config

import (
	"encoding/json"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"strings"
	"sync"

	"github.com/fsnotify/fsnotify"
)

// Loader manages configuration loading and hot-reload.
type Loader struct {
	exercisesPath      string
	scoringWeightsPath string

	mu             sync.RWMutex
	exercises      *ExercisesConfig
	scoringWeights *ScoringWeightsConfig

	watcher     *fsnotify.Watcher
	stopWatcher chan struct{}
}

// NewLoader creates a new config loader.
func NewLoader(exercisesPath, scoringWeightsPath string) (*Loader, error) {
	loader := &Loader{
		exercisesPath:      exercisesPath,
		scoringWeightsPath: scoringWeightsPath,
		stopWatcher:        make(chan struct{}),
	}

	if err := loader.loadAll(); err != nil {
		return nil, fmt.Errorf("failed to load initial config: %w", err)
	}

	if err := loader.setupWatcher(); err != nil {
		log.Printf("Warning: failed to set up file watcher, hot-reload disabled: %v", err)
	}

	return loader, nil
}

func (l *Loader) loadAll() error {
	exercises, err := loadJSON[ExercisesConfig](l.exercisesPath)
	if err != nil {
		return fmt.Errorf("failed to load exercises: %w", err)
	}

	weights, err := loadJSON[ScoringWeightsConfig](l.scoringWeightsPath)
	if err != nil {
		return fmt.Errorf("failed to load scoring weights: %w", err)
	}

	if err := validateExercises(exercises); err != nil {
		return fmt.Errorf("exercises validation failed: %w", err)
	}

	l.mu.Lock()
	l.exercises = exercises
	l.scoringWeights = weights
	l.mu.Unlock()

	return nil
}

func loadJSON[T any](path string) (*T, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}

	var out T
	if err := json.Unmarshal(data, &out); err != nil {
		return nil, fmt.Errorf("failed to parse %s: %w", filepath.Base(path), err)
	}
	return &out, nil
}

func validateExercises(config *ExercisesConfig) error {
	if len(config.Exercises) == 0 {
		return fmt.Errorf("exercises array is empty")
	}

	aliasOwner := make(map[string]string)

	for _, ex := range config.Exercises {
		if ex.ID == "" {
			return fmt.Errorf("exercise missing required field: id")
		}
		if ex.CanonicalName == "" {
			return fmt.Errorf("exercise %s missing required field: canonical_name", ex.ID)
		}
		if ex.MovementPattern == "" {
			return fmt.Errorf("exercise %s missing required field: movement_pattern", ex.ID)
		}
		if len(ex.MuscleTargets) == 0 {
			return fmt.Errorf("exercise %s missing required field: muscle_targets", ex.ID)
		}

		allNames := append([]string{ex.CanonicalName}, ex.Aliases...)
		allNames = append(allNames, ex.Slang...)
		allNames = append(allNames, ex.CommonTypos...)

		for _, name := range allNames {
			normalized := strings.ToLower(strings.TrimSpace(name))
			if owner, exists := aliasOwner[normalized]; exists && owner != ex.ID {
				log.Printf("Warning: alias %q is shared by exercises %s and %s", name, owner, ex.ID)
			} else {
				aliasOwner[normalized] = ex.ID
			}
		}
	}

	return nil
}

func (l *Loader) setupWatcher() error {
	watcher, err := fsnotify.NewWatcher()
	if err != nil {
		return err
	}
	l.watcher = watcher

	if err := watcher.Add(filepath.Dir(l.exercisesPath)); err != nil {
		return err
	}

	go l.watchFiles()
	return nil
}

func (l *Loader) watchFiles() {
	for {
		select {
		case event, ok := <-l.watcher.Events:
			if !ok {
				return
			}
			if event.Op&fsnotify.Write == fsnotify.Write {
				filename := filepath.Base(event.Name)
				if filename == filepath.Base(l.exercisesPath) || filename == filepath.Base(l.scoringWeightsPath) {
					log.Printf("Config file changed: %s, reloading...", filename)
					if err := l.loadAll(); err != nil {
						log.Printf("Error reloading config (keeping old config): %v", err)
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

// GetExercises returns the current exercises config (thread-safe).
func (l *Loader) GetExercises() *ExercisesConfig {
	l.mu.RLock()
	defer l.mu.RUnlock()
	return l.exercises
}

// GetScoringWeights returns the current scoring weights config (thread-safe).
func (l *Loader) GetScoringWeights() *ScoringWeightsConfig {
	l.mu.RLock()
	defer l.mu.RUnlock()
	return l.scoringWeights
}

// Close stops the file watcher.
func (l *Loader) Close() error {
	if l.watcher != nil {
		close(l.stopWatcher)
		return l.watcher.Close()
	}
	return nil
}
