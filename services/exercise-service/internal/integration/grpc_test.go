//go:build integration

package integration

import (
	"context"
	"net"
	"testing"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/test/bufconn"

	exercisev1 "github.com/athleta/exercise-service/gen/exercise/v1"
	grpcserver "github.com/athleta/exercise-service/internal/grpc"
	"github.com/athleta/exercise-service/internal/service"
)

// startServer wires the full domain service behind an in-process gRPC server
// over bufconn (no network) and returns a connected client plus the service
// (for direct seeding).
func startServer(t *testing.T) (exercisev1.ExerciseServiceClient, *service.Service) {
	t.Helper()
	svc, _ := newService(t)

	lis := bufconn.Listen(1024 * 1024)
	srv := grpc.NewServer()
	exercisev1.RegisterExerciseServiceServer(srv, grpcserver.NewServer(svc))
	go func() { _ = srv.Serve(lis) }()
	t.Cleanup(srv.Stop)

	conn, err := grpc.NewClient(
		"passthrough://bufnet",
		grpc.WithContextDialer(func(ctx context.Context, _ string) (net.Conn, error) {
			return lis.DialContext(ctx)
		}),
		grpc.WithTransportCredentials(insecure.NewCredentials()),
	)
	if err != nil {
		t.Fatalf("dial bufconn: %v", err)
	}
	t.Cleanup(func() { _ = conn.Close() })

	return exercisev1.NewExerciseServiceClient(conn), svc
}

func TestInferExercisesGRPC(t *testing.T) {
	client, _ := startServer(t)
	ctx := ctxT(t)

	resp, err := client.InferExercises(ctx, &exercisev1.InferExercisesRequest{
		Names: []string{"bench press", "zorblax flux capacitor"},
	})
	if err != nil {
		t.Fatalf("InferExercises: %v", err)
	}
	if len(resp.Exercises) != 2 {
		t.Fatalf("got %d results, want 2 (one per name, in order)", len(resp.Exercises))
	}

	// Known vocabulary name -> matched, high confidence, real exercise.
	known := resp.Exercises[0]
	if known.RequestedName != "bench press" {
		t.Errorf("result[0] requested name = %q", known.RequestedName)
	}
	if known.Resolution != exercisev1.InferredExercise_RESOLUTION_MATCHED {
		t.Errorf("known resolution = %v, want MATCHED", known.Resolution)
	}
	if known.Exercise.Id <= 0 {
		t.Errorf("known exercise id = %d, want positive", known.Exercise.Id)
	}

	// Unknown name -> inferred, sub-1.0 confidence, never a gRPC error.
	unknown := resp.Exercises[1]
	if unknown.Resolution != exercisev1.InferredExercise_RESOLUTION_INFERRED {
		t.Errorf("unknown resolution = %v, want INFERRED", unknown.Resolution)
	}
	if unknown.Confidence >= 1.0 {
		t.Errorf("unknown confidence = %v, want < 1.0", unknown.Confidence)
	}
	if unknown.Exercise == nil || unknown.Exercise.Id <= 0 {
		t.Error("unknown name must still yield a persisted exercise")
	}
}

func TestGetExercisesGRPC(t *testing.T) {
	client, _ := startServer(t)
	ctx := ctxT(t)

	inferred, err := client.InferExercises(ctx, &exercisev1.InferExercisesRequest{Names: []string{"squat"}})
	if err != nil {
		t.Fatalf("infer: %v", err)
	}
	id := inferred.Exercises[0].Exercise.Id

	got, err := client.GetExercises(ctx, &exercisev1.GetExercisesRequest{Ids: []int32{id}})
	if err != nil {
		t.Fatalf("GetExercises: %v", err)
	}
	if len(got.Exercises) != 1 || got.Exercises[0].Id != id {
		t.Fatalf("round trip failed: %+v", got.Exercises)
	}

	// Unknown ID is omitted, not an error.
	empty, err := client.GetExercises(ctx, &exercisev1.GetExercisesRequest{Ids: []int32{999999}})
	if err != nil {
		t.Fatalf("GetExercises unknown: %v", err)
	}
	if len(empty.Exercises) != 0 {
		t.Errorf("unknown id returned %d exercises, want 0", len(empty.Exercises))
	}
}

func TestFindSubstitutionsGRPC(t *testing.T) {
	client, svc := startServer(t)
	ctx := ctxT(t)

	if _, err := svc.Seed(ctx); err != nil {
		t.Fatalf("seed: %v", err)
	}

	infer, _ := client.InferExercises(ctx, &exercisev1.InferExercisesRequest{Names: []string{"barbell bench press"}})
	benchID := infer.Exercises[0].Exercise.Id

	resp, err := client.FindSubstitutions(ctx, &exercisev1.FindSubstitutionsRequest{ExerciseId: benchID, Limit: 5})
	if err != nil {
		t.Fatalf("FindSubstitutions: %v", err)
	}
	if len(resp.Substitutions) == 0 {
		t.Fatal("expected substitution candidates for bench press")
	}
	// Ordered by non-increasing score.
	for i := 1; i < len(resp.Substitutions); i++ {
		if resp.Substitutions[i-1].Score < resp.Substitutions[i].Score {
			t.Errorf("substitutions not score-ordered at %d", i)
		}
	}
	for _, s := range resp.Substitutions {
		if s.Exercise.Id == benchID {
			t.Error("substitutions must exclude the original exercise")
		}
	}

	// Exclude the top candidate -> it disappears from results.
	top := resp.Substitutions[0].Exercise.Id
	excluded, err := client.FindSubstitutions(ctx, &exercisev1.FindSubstitutionsRequest{
		ExerciseId:         benchID,
		ExcludeExerciseIds: []int32{top},
		Limit:              5,
	})
	if err != nil {
		t.Fatalf("FindSubstitutions excluded: %v", err)
	}
	for _, s := range excluded.Substitutions {
		if s.Exercise.Id == top {
			t.Error("excluded id still present")
		}
	}

	// Excluding shoulder stress must drop shoulder-stressing candidates.
	noShoulder, err := client.FindSubstitutions(ctx, &exercisev1.FindSubstitutionsRequest{
		ExerciseId:         benchID,
		ExcludeJointStress: []string{"shoulder"},
		Limit:              20,
	})
	if err != nil {
		t.Fatalf("FindSubstitutions joint exclude: %v", err)
	}
	for _, s := range noShoulder.Substitutions {
		for _, j := range s.Exercise.Safety.JointStressAreas {
			if j == "shoulder" {
				t.Errorf("candidate %q stresses excluded shoulder", s.Exercise.Name)
			}
		}
	}

	// Unknown exercise -> NotFound.
	if _, err := client.FindSubstitutions(ctx, &exercisev1.FindSubstitutionsRequest{ExerciseId: 999999}); err == nil {
		t.Error("expected error for unknown exercise id")
	}
}

func TestGetMusclesGRPC(t *testing.T) {
	client, _ := startServer(t)
	ctx := ctxT(t)

	all, err := client.GetMuscles(ctx, &exercisev1.GetMusclesRequest{})
	if err != nil {
		t.Fatalf("GetMuscles all: %v", err)
	}
	if len(all.Muscles) != 20 {
		t.Fatalf("muscle count = %d, want 20", len(all.Muscles))
	}

	one, err := client.GetMuscles(ctx, &exercisev1.GetMusclesRequest{Names: []string{"quadriceps"}})
	if err != nil {
		t.Fatalf("GetMuscles quad: %v", err)
	}
	if len(one.Muscles) != 1 {
		t.Fatalf("quad query returned %d", len(one.Muscles))
	}
	q := one.Muscles[0]
	if q.Size != exercisev1.Muscle_SIZE_LARGE || q.RecoveryHours != 72 || !q.IsCompoundTarget {
		t.Errorf("quadriceps metadata wrong: %+v", q)
	}
}
