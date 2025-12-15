.PHONY: proto build run test clean docker-build docker-run

# Generate protobuf code
proto:
	protoc --go_out=. --go_opt=paths=source_relative \
		--go-grpc_out=. --go-grpc_opt=paths=source_relative \
		proto/inference.proto

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

# Clean build artifacts
clean:
	rm -rf bin/
	rm -f proto/*.pb.go

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

