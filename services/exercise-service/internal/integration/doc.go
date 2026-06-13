// Package integration contains tests that run the service against a real
// Neo4j instance via testcontainers-go. All test files are gated behind the
// `integration` build tag; run them with:
//
//	go test -tags integration ./internal/integration/...
//
// Requires a working Docker daemon.
package integration
