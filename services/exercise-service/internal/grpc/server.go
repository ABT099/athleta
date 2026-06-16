package grpc

import (
	"context"
	"errors"
	"strings"

	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	exercisev1 "github.com/athleta/exercise-service/gen/exercise/v1"
	"github.com/athleta/exercise-service/internal/domain"
	"github.com/athleta/exercise-service/internal/service"
)

// Server implements the ExerciseService gRPC contract.
type Server struct {
	exercisev1.UnimplementedExerciseServiceServer
	svc *service.Service
}

// NewServer creates a new gRPC server around the domain service.
func NewServer(svc *service.Service) *Server {
	return &Server{svc: svc}
}

// InferExercises resolves raw names into structured exercises.
func (s *Server) InferExercises(ctx context.Context, req *exercisev1.InferExercisesRequest) (*exercisev1.InferExercisesResponse, error) {
	if len(req.Names) == 0 {
		return &exercisev1.InferExercisesResponse{}, nil
	}

	// Blank names are malformed input, not unrecognizable exercises: reject
	// them so they can't collapse into a junk empty-named graph node.
	for i, name := range req.Names {
		if strings.TrimSpace(name) == "" {
			return nil, status.Errorf(codes.InvalidArgument, "names[%d] is blank", i)
		}
	}

	results, err := s.svc.InferExercises(ctx, req.Names)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "inference failed: %v", err)
	}

	out := make([]*exercisev1.InferredExercise, 0, len(results))
	for _, r := range results {
		out = append(out, &exercisev1.InferredExercise{
			Exercise:      toProtoExercise(r.Exercise),
			RequestedName: r.RequestedName,
			Resolution:    toProtoResolution(r.Resolution),
			Confidence:    r.Confidence,
		})
	}

	return &exercisev1.InferExercisesResponse{Exercises: out}, nil
}

// GetExercises fetches exercises by ID.
func (s *Server) GetExercises(ctx context.Context, req *exercisev1.GetExercisesRequest) (*exercisev1.GetExercisesResponse, error) {
	exercises, err := s.svc.GetExercises(ctx, req.Ids)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "lookup failed: %v", err)
	}

	out := make([]*exercisev1.Exercise, 0, len(exercises))
	for _, ex := range exercises {
		out = append(out, toProtoExercise(ex))
	}

	return &exercisev1.GetExercisesResponse{Exercises: out}, nil
}

// FindSubstitutions returns scored substitutes for an exercise.
func (s *Server) FindSubstitutions(ctx context.Context, req *exercisev1.FindSubstitutionsRequest) (*exercisev1.FindSubstitutionsResponse, error) {
	substitutions, err := s.svc.FindSubstitutions(ctx, req.ExerciseId, domain.SubstitutionFilters{
		ExcludeJointStress: req.ExcludeJointStress,
		ExcludeExerciseIDs: req.ExcludeExerciseIds,
		Limit:              int(req.Limit),
	})
	if err != nil {
		if errors.Is(err, service.ErrExerciseNotFound) {
			return nil, status.Errorf(codes.NotFound, "exercise %d not found", req.ExerciseId)
		}
		return nil, status.Errorf(codes.Internal, "substitution search failed: %v", err)
	}

	out := make([]*exercisev1.Substitution, 0, len(substitutions))
	for _, sub := range substitutions {
		out = append(out, &exercisev1.Substitution{
			Exercise: toProtoExercise(sub.Exercise),
			Score:    sub.Score,
			Reason:   sub.Reason,
		})
	}

	return &exercisev1.FindSubstitutionsResponse{Substitutions: out}, nil
}

// GetMuscles returns muscle taxonomy metadata.
func (s *Server) GetMuscles(ctx context.Context, req *exercisev1.GetMusclesRequest) (*exercisev1.GetMusclesResponse, error) {
	muscles, err := s.svc.GetMuscles(ctx, req.Names)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "muscle lookup failed: %v", err)
	}

	out := make([]*exercisev1.Muscle, 0, len(muscles))
	for _, m := range muscles {
		out = append(out, &exercisev1.Muscle{
			Name:             m.Name,
			DisplayName:      m.DisplayName,
			Size:             toProtoSize(m.Size),
			RecoveryHours:    int32(m.RecoveryHours),
			Antagonist:       m.Antagonist,
			IsCompoundTarget: m.IsCompoundTarget,
		})
	}

	return &exercisev1.GetMusclesResponse{Muscles: out}, nil
}

func toProtoSize(size string) exercisev1.Muscle_Size {
	switch size {
	case domain.SizeSmall:
		return exercisev1.Muscle_SIZE_SMALL
	case domain.SizeMedium:
		return exercisev1.Muscle_SIZE_MEDIUM
	case domain.SizeLarge:
		return exercisev1.Muscle_SIZE_LARGE
	default:
		return exercisev1.Muscle_SIZE_UNSPECIFIED
	}
}

func toProtoExercise(ex *domain.Exercise) *exercisev1.Exercise {
	if ex == nil {
		return nil
	}

	muscles := make([]*exercisev1.MuscleTarget, 0, len(ex.Muscles))
	for _, m := range ex.Muscles {
		muscles = append(muscles, &exercisev1.MuscleTarget{
			Name:              m.Name,
			DisplayName:       m.DisplayName,
			Role:              m.Role,
			ActivationPercent: m.ActivationPercent,
		})
	}

	return &exercisev1.Exercise{
		Id:                ex.ID,
		Name:              ex.Name,
		MovementPattern:   ex.MovementPattern,
		ExerciseType:      ex.ExerciseType,
		IntensityCategory: ex.IntensityCategory,
		Attributes: &exercisev1.ExerciseAttributes{
			Equipment:   ex.Attributes.Equipment,
			Laterality:  ex.Attributes.Laterality,
			Angle:       ex.Attributes.Angle,
			Grip:        ex.Attributes.Grip,
			Tempo:       ex.Attributes.Tempo,
			ForceVector: ex.Attributes.ForceVector,
		},
		Muscles: muscles,
		Safety: &exercisev1.SafetyProfile{
			InjuryRiskLevel:  ex.Safety.InjuryRiskLevel,
			ComplexityScore:  ex.Safety.ComplexityScore,
			JointStressAreas: ex.Safety.JointStressAreas,
		},
	}
}

func toProtoResolution(r domain.Resolution) exercisev1.InferredExercise_Resolution {
	switch r {
	case domain.ResolutionMatched:
		return exercisev1.InferredExercise_RESOLUTION_MATCHED
	case domain.ResolutionInferred:
		return exercisev1.InferredExercise_RESOLUTION_INFERRED
	default:
		return exercisev1.InferredExercise_RESOLUTION_UNSPECIFIED
	}
}
