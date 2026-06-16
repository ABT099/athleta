package service

import (
	"context"
	"fmt"
	"sort"
	"strings"

	"github.com/athleta/exercise-service/internal/config"
	"github.com/athleta/exercise-service/internal/domain"
	"github.com/athleta/exercise-service/internal/inference"
	"github.com/athleta/exercise-service/internal/resolver"
)

const defaultSubstitutionLimit = 5

// Graph is everything the service needs from the exercise graph. It is the
// seam between orchestration and persistence: the Neo4j repository is one
// adapter, the in-memory MemGraph (used by unit tests) is another, so the
// service's resolution, seeding, and substitution logic can be exercised
// without a database.
type Graph interface {
	UpsertExercise(ctx context.Context, ex *domain.Exercise) (int32, error)
	GetExercisesByIDs(ctx context.Context, ids []int32) ([]*domain.Exercise, error)
	GetExerciseByName(ctx context.Context, name string) (*domain.Exercise, error)
	GetMuscles(ctx context.Context, names []string) ([]domain.Muscle, error)
	FindSubstitutionCandidates(ctx context.Context, exerciseID int32, excludeIDs []int32, excludeJoints []string) ([]domain.SubstitutionCandidate, error)
}

// Service orchestrates the exercise domain: name resolution, inference,
// persistence, and substitution.
type Service struct {
	repo     Graph
	resolver *resolver.Resolver
	loader   *config.Loader
	parser   *inference.Parser
	rules    *inference.RulesEngine
	safety   *inference.SafetyAnalyzer
}

// New creates a new exercise domain service over any Graph adapter.
func New(repo Graph, r *resolver.Resolver, loader *config.Loader) *Service {
	return &Service{
		repo:     repo,
		resolver: r,
		loader:   loader,
		parser:   inference.NewParser(),
		rules:    inference.NewRulesEngine(),
		safety:   inference.NewSafetyAnalyzer(),
	}
}

// InferExercises resolves each input name to a persisted, structured
// exercise. Every name produces exactly one result; unrecognizable names
// fall back to attribute inference instead of failing.
func (s *Service) InferExercises(ctx context.Context, names []string) ([]domain.InferredExercise, error) {
	results := make([]domain.InferredExercise, 0, len(names))

	for _, name := range names {
		inferred, err := s.inferOne(ctx, name)
		if err != nil {
			return nil, fmt.Errorf("failed to infer exercise %q: %w", name, err)
		}
		results = append(results, *inferred)
	}

	return results, nil
}

func (s *Service) inferOne(ctx context.Context, requestedName string) (*domain.InferredExercise, error) {
	outcome := s.resolver.Resolve(requestedName)

	if outcome.Matched {
		exercise, err := s.resolveCanonical(ctx, outcome.VocabularyID, outcome.CanonicalName)
		if err != nil {
			return nil, err
		}
		return &domain.InferredExercise{
			Exercise:      exercise,
			RequestedName: requestedName,
			Resolution:    domain.ResolutionMatched,
			Confidence:    outcome.Confidence,
		}, nil
	}

	// Unresolved name: compose the exercise from its parsed attributes.
	exercise, err := s.inferFromAttributes(ctx, requestedName)
	if err != nil {
		return nil, err
	}
	return &domain.InferredExercise{
		Exercise:      exercise,
		RequestedName: requestedName,
		Resolution:    domain.ResolutionInferred,
		Confidence:    outcome.Confidence,
	}, nil
}

// resolveCanonical returns the graph exercise for a vocabulary entry,
// creating it from the curated definition on first use.
func (s *Service) resolveCanonical(ctx context.Context, vocabularyID, canonicalName string) (*domain.Exercise, error) {
	existing, err := s.repo.GetExerciseByName(ctx, canonicalName)
	if err != nil {
		return nil, err
	}
	if existing != nil {
		return existing, nil
	}

	cfg := s.findVocabularyEntry(vocabularyID)
	if cfg == nil {
		return nil, fmt.Errorf("vocabulary entry %q not found", vocabularyID)
	}

	exercise := s.BuildFromVocabulary(cfg)
	return s.persistAndReload(ctx, exercise)
}

// inferFromAttributes builds an exercise purely from parsed attributes and
// persists it.
func (s *Service) inferFromAttributes(ctx context.Context, requestedName string) (*domain.Exercise, error) {
	name := canonicalizeInferredName(requestedName)

	existing, err := s.repo.GetExerciseByName(ctx, name)
	if err != nil {
		return nil, err
	}
	if existing != nil {
		return existing, nil
	}

	parsed := s.parser.Parse(name)
	exercise := s.composeFromParsed(name, parsed)
	return s.persistAndReload(ctx, exercise)
}

// BuildFromVocabulary composes a full exercise from a curated vocabulary
// entry. Safety metrics are derived from the entry's attributes; curated
// fields always win over anything parsed from the name.
func (s *Service) BuildFromVocabulary(cfg *config.ExerciseConfig) *domain.Exercise {
	parsed := s.parser.Parse(cfg.CanonicalName)

	parsed.MovementPattern = cfg.MovementPattern
	if cfg.ExerciseType != "" {
		parsed.ExerciseType = cfg.ExerciseType
	}
	if cfg.Equipment != "" {
		parsed.Modifiers.Equipment = cfg.Equipment
	}
	if cfg.Laterality != "" {
		parsed.Modifiers.Laterality = cfg.Laterality
	}
	if cfg.Angle != "" {
		parsed.Modifiers.Angle = cfg.Angle
	}
	if cfg.Grip != "" {
		parsed.Modifiers.Grip = cfg.Grip
	}
	if cfg.ForceVector != "" {
		parsed.Modifiers.ForceVector = cfg.ForceVector
	}

	exercise := s.composeFromParsed(cfg.CanonicalName, parsed)

	// Curated muscle targets replace rule-derived ones.
	muscles := make([]domain.MuscleTarget, 0, len(cfg.MuscleTargets))
	for _, mt := range cfg.MuscleTargets {
		muscles = append(muscles, domain.MuscleTarget{
			Name:              mt.Name,
			Role:              mt.Role,
			ActivationPercent: domain.ActivationForRole(mt.Role),
		})
	}
	exercise.Muscles = muscles

	return exercise
}

func (s *Service) composeFromParsed(name string, parsed *inference.ParsedExercise) *domain.Exercise {
	return &domain.Exercise{
		Name:              name,
		MovementPattern:   parsed.MovementPattern,
		ExerciseType:      parsed.ExerciseType,
		IntensityCategory: s.safety.IntensityCategory(parsed),
		Attributes:        parsed.Modifiers, // already the full domain attribute shape
		Muscles:           s.rules.InferMuscleTargets(parsed),
		Safety:            s.safety.Analyze(parsed),
	}
}

// persistAndReload upserts the exercise and reads it back so muscle display
// names and any graph-side defaults are populated.
func (s *Service) persistAndReload(ctx context.Context, exercise *domain.Exercise) (*domain.Exercise, error) {
	id, err := s.repo.UpsertExercise(ctx, exercise)
	if err != nil {
		return nil, err
	}

	stored, err := s.repo.GetExercisesByIDs(ctx, []int32{id})
	if err != nil {
		return nil, err
	}
	if len(stored) == 0 {
		return nil, fmt.Errorf("exercise %d not found after upsert", id)
	}
	return stored[0], nil
}

func (s *Service) findVocabularyEntry(id string) *config.ExerciseConfig {
	exercises := s.loader.GetExercises()
	for i := range exercises.Exercises {
		if exercises.Exercises[i].ID == id {
			return &exercises.Exercises[i]
		}
	}
	return nil
}

// GetExercises fetches exercises by ID; unknown IDs are omitted.
func (s *Service) GetExercises(ctx context.Context, ids []int32) ([]*domain.Exercise, error) {
	if len(ids) == 0 {
		return nil, nil
	}
	return s.repo.GetExercisesByIDs(ctx, ids)
}

// GetMuscles returns muscle metadata; empty names returns all muscles.
func (s *Service) GetMuscles(ctx context.Context, names []string) ([]domain.Muscle, error) {
	return s.repo.GetMuscles(ctx, names)
}

// Seed upserts every curated vocabulary exercise as a graph archetype.
// Idempotent: exercises MERGE by name, so re-running leaves node and
// relationship counts unchanged. Returns the number of exercises seeded.
func (s *Service) Seed(ctx context.Context) (int, error) {
	exercises := s.loader.GetExercises().Exercises
	for i := range exercises {
		exercise := s.BuildFromVocabulary(&exercises[i])
		if _, err := s.repo.UpsertExercise(ctx, exercise); err != nil {
			return i, fmt.Errorf("seed %q: %w", exercises[i].CanonicalName, err)
		}
	}
	return len(exercises), nil
}

// FindSubstitutions returns scored substitution candidates for an exercise.
func (s *Service) FindSubstitutions(ctx context.Context, exerciseID int32, filters domain.SubstitutionFilters) ([]domain.Substitution, error) {
	originals, err := s.repo.GetExercisesByIDs(ctx, []int32{exerciseID})
	if err != nil {
		return nil, err
	}
	if len(originals) == 0 {
		return nil, ErrExerciseNotFound
	}
	original := originals[0]

	candidates, err := s.repo.FindSubstitutionCandidates(ctx, exerciseID, filters.ExcludeExerciseIDs, filters.ExcludeJointStress)
	if err != nil {
		return nil, err
	}

	substitutions := make([]domain.Substitution, 0, len(candidates))
	for _, candidate := range candidates {
		score, details := scoreCandidate(original, candidate)
		substitutions = append(substitutions, domain.Substitution{
			Exercise: candidate.Exercise,
			Score:    float32(score),
			Reason:   substitutionReason(details),
		})
	}

	sort.Slice(substitutions, func(i, j int) bool {
		return substitutions[i].Score > substitutions[j].Score
	})

	limit := filters.Limit
	if limit <= 0 {
		limit = defaultSubstitutionLimit
	}
	if len(substitutions) > limit {
		substitutions = substitutions[:limit]
	}

	return substitutions, nil
}

// ErrExerciseNotFound is returned when an exercise ID does not exist.
var ErrExerciseNotFound = fmt.Errorf("exercise not found")

// canonicalizeInferredName produces a stable, presentable name for an
// exercise we could not match to the vocabulary: trimmed and title-cased.
func canonicalizeInferredName(input string) string {
	fields := strings.Fields(strings.ToLower(strings.TrimSpace(input)))
	for i, f := range fields {
		fields[i] = strings.ToUpper(f[:1]) + f[1:]
	}
	return strings.Join(fields, " ")
}
