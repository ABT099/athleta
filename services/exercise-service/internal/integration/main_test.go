//go:build integration

// Package integration holds tests that run against a real Neo4j instance
// spun up via testcontainers-go. They are gated behind the `integration`
// build tag so `go test ./...` stays fast and Neo4j-free.
//
//	go test -tags integration ./internal/integration/...
package integration

import (
	"context"
	"log"
	"os"
	"testing"
	"time"

	"github.com/neo4j/neo4j-go-driver/v6/neo4j"
	tcneo4j "github.com/testcontainers/testcontainers-go/modules/neo4j"

	"github.com/athleta/exercise-service/internal/config"
	"github.com/athleta/exercise-service/internal/graph"
	"github.com/athleta/exercise-service/internal/matcher"
	"github.com/athleta/exercise-service/internal/resolver"
	"github.com/athleta/exercise-service/internal/service"
)

const (
	testUser = "neo4j"
	testPass = "testpassword"
)

// testURI is the bolt URI of the shared container, set by TestMain.
var testURI string

func TestMain(m *testing.M) {
	ctx := context.Background()

	container, err := tcneo4j.Run(ctx, "neo4j:5.26-community",
		tcneo4j.WithAdminPassword(testPass),
	)
	if err != nil {
		log.Fatalf("start neo4j container: %v", err)
	}

	uri, err := container.BoltUrl(ctx)
	if err != nil {
		log.Fatalf("bolt url: %v", err)
	}
	testURI = uri

	code := m.Run()

	if err := container.Terminate(ctx); err != nil {
		log.Printf("terminate container: %v", err)
	}
	os.Exit(code)
}

// rawDriver opens a direct driver for fixture setup, wiping, and assertions.
func rawDriver(t *testing.T) neo4j.DriverWithContext {
	t.Helper()
	driver, err := neo4j.NewDriverWithContext(testURI, neo4j.BasicAuth(testUser, testPass, ""))
	if err != nil {
		t.Fatalf("raw driver: %v", err)
	}
	t.Cleanup(func() { _ = driver.Close(context.Background()) })
	return driver
}

// wipe removes every node and relationship for test isolation.
func wipe(t *testing.T, driver neo4j.DriverWithContext) {
	t.Helper()
	ctx := context.Background()
	session := driver.NewSession(ctx, neo4j.SessionConfig{AccessMode: neo4j.AccessModeWrite})
	defer session.Close(ctx)
	if _, err := session.Run(ctx, "MATCH (n) DETACH DELETE n", nil); err != nil {
		t.Fatalf("wipe: %v", err)
	}
}

// counts returns (nodeCount, relCount) for idempotency assertions.
func counts(t *testing.T, driver neo4j.DriverWithContext) (int64, int64) {
	t.Helper()
	ctx := context.Background()
	session := driver.NewSession(ctx, neo4j.SessionConfig{AccessMode: neo4j.AccessModeRead})
	defer session.Close(ctx)

	scalar := func(query string) int64 {
		res, err := session.Run(ctx, query, nil)
		if err != nil {
			t.Fatalf("count query %q: %v", query, err)
		}
		if !res.Next(ctx) {
			t.Fatalf("count query %q returned nothing", query)
		}
		v, _ := res.Record().Get("c")
		n, _ := v.(int64)
		return n
	}
	return scalar("MATCH (n) RETURN count(n) AS c"), scalar("MATCH ()-[r]->() RETURN count(r) AS c")
}

// newRepo returns a fresh repository against a wiped, schema-initialized graph.
func newRepo(t *testing.T) *graph.Repository {
	t.Helper()
	wipe(t, rawDriver(t))

	repo, err := graph.NewRepository(testURI, testUser, testPass)
	if err != nil {
		t.Fatalf("new repo: %v", err)
	}
	t.Cleanup(func() { _ = repo.Close(context.Background()) })

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	if err := repo.InitSchema(ctx); err != nil {
		t.Fatalf("init schema: %v", err)
	}
	return repo
}

// newService builds the full domain service over a fresh repo.
func newService(t *testing.T) (*service.Service, *graph.Repository) {
	t.Helper()
	repo := newRepo(t)

	loader, err := config.NewLoader("../../config/exercises.json", "../../config/scoring_weights.json")
	if err != nil {
		t.Fatalf("config loader: %v", err)
	}
	t.Cleanup(func() { _ = loader.Close() })

	return service.New(repo, resolver.New(matcher.NewMatcher(loader)), loader), repo
}

func ctxT(t *testing.T) context.Context {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	t.Cleanup(cancel)
	return ctx
}
