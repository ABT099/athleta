# Build stage
FROM golang:1.25-alpine AS builder

WORKDIR /app

# Install build dependencies
RUN apk add --no-cache git protobuf

# Copy go mod files from service directory
COPY services/exercise-inference/go.mod services/exercise-inference/go.sum* ./
RUN go mod download

# Install protobuf plugins
RUN go install google.golang.org/protobuf/cmd/protoc-gen-go@latest
RUN go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest

# Copy centralized proto files
COPY proto/ ./proto/

# Generate Go code from proto
RUN protoc --go_out=. --go_opt=paths=source_relative \
    --go-grpc_out=. --go-grpc_opt=paths=source_relative \
    --proto_path=proto \
    inference/v1/inference.proto

# Copy source code
COPY services/exercise-inference/ ./

# Build the application
RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o main ./cmd/server

# Runtime stage
FROM alpine:latest

RUN apk --no-cache add ca-certificates wget

WORKDIR /root/

# Copy the binary from builder
COPY --from=builder /app/main .

# Copy config files
COPY --from=builder /app/config ./config

# Download and install grpc_health_probe
RUN wget -qO/bin/grpc_health_probe https://github.com/grpc-ecosystem/grpc-health-probe/releases/download/v0.4.19/grpc_health_probe-linux-amd64 && \
    chmod +x /bin/grpc_health_probe

# Expose gRPC port
EXPOSE 50051

CMD ["./main"]
