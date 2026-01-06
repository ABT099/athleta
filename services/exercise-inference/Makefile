.PHONY: proto build run test clean docker-build docker-run

# Shared proto location (migrated from local proto/)
PROTO_DIR := ../../proto
PROTO_FILE := $(PROTO_DIR)/inference/v1/inference.proto
PROTO_OUT_DIR := ./internal/generated

# Generate protobuf code from shared proto
proto:
	protoc --go_out=. --go_opt=paths=source_relative \
		--go-grpc_out=. --go-grpc_opt=paths=source_relative \
		--proto_path=$(PROTO_DIR) \
		inference/v1/inference.proto

# Build the server
build:
	go build -o bin/server ./cmd/server

# Build the migration tool
build-migrate:
	go build -o bin/migrate ./cmd/migrate

# Run the server locally
run:
	go run ./cmd/server

# Run tests
test:
	go test -v ./...

# Run tests with coverage
test-coverage:
	go test -v -coverprofile=coverage.out ./...
	go tool cover -html=coverage.out -o coverage.html

# Clean build artifacts
clean:
	rm -rf bin/
	rm -f coverage.out coverage.html

# Build Docker image
docker-build:
	docker build -t athleta/exercise-inference:latest .

# Run with Docker Compose
docker-run:
	docker-compose up exercise-inference

# Generate protobuf and build
all: proto build

# Development setup
dev-setup:
	go mod download
	go install google.golang.org/protobuf/cmd/protoc-gen-go@latest
	go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest

# Validate proto files
validate-proto:
	protoc --descriptor_set_out=NUL \
		--proto_path=$(PROTO_DIR) \
		inference/v1/inference.proto

# Hot reload for development
dev:
	@which air > /dev/null || go install github.com/air-verse/air@latest
	air

# Format code
fmt:
	go fmt ./...
	gofumpt -l -w .

# Lint code
lint:
	@which golangci-lint > /dev/null || (echo "Install golangci-lint: https://golangci-lint.run/usage/install/" && exit 1)
	golangci-lint run

# Run all checks (format, lint, test)
check: fmt lint test

# Show help
help:
	@echo proto - Generate protobuf code
	@echo build - Build the server
	@echo run - Run the server
	@echo test - Run tests
	@echo clean - Clean artifacts
	@echo all - Generate proto and build
