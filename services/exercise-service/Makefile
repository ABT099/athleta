.PHONY: proto build build-seed build-migrate run test test-integration clean docker-build fmt lint check

PROTO_DIR := ../../proto

# Generate protobuf code from the shared proto
proto:
	protoc --go_out=gen --go_opt=paths=source_relative \
		--go-grpc_out=gen --go-grpc_opt=paths=source_relative \
		--proto_path=$(PROTO_DIR) \
		exercise/v1/exercise.proto

# Build the server
build:
	go build -o bin/server ./cmd/server

# Build the graph seed tool (taxonomy + vocabulary archetypes)
build-seed:
	go build -o bin/seed ./cmd/seed
	
# Run the server locally
run:
	go run ./cmd/server

# Run fast unit tests (no Neo4j)
test:
	go test ./...

# Run integration tests against a real Neo4j via testcontainers (needs Docker)
test-integration:
	go test -tags integration -count=1 ./internal/integration/...

# Clean build artifacts
clean:
	rm -rf bin/

# Build Docker image
docker-build:
	docker build -t athleta/exercise-service:latest .

# Generate protobuf and build everything
all: proto build build-seed build-migrate

fmt:
	go fmt ./...

lint:
	@which golangci-lint > /dev/null || (echo "Install golangci-lint: https://golangci-lint.run/usage/install/" && exit 1)
	golangci-lint run

check: fmt lint test
