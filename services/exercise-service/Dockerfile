# Build stage
FROM golang:1.25-alpine AS builder

WORKDIR /app

RUN apk add --no-cache git protobuf

# Copy go mod files from service directory
COPY services/exercise-service/go.mod services/exercise-service/go.sum* ./
RUN go mod download

# Install protobuf plugins
RUN go install google.golang.org/protobuf/cmd/protoc-gen-go@latest
RUN go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest

# Copy centralized proto files
COPY proto/ ./proto/

# Copy source code
COPY services/exercise-service/ ./

# Generate Go code from proto
RUN protoc --go_out=gen --go_opt=paths=source_relative \
    --go-grpc_out=gen --go-grpc_opt=paths=source_relative \
    --proto_path=proto \
    exercise/v1/exercise.proto

# Build the server and seed binaries
RUN CGO_ENABLED=0 GOOS=linux go build -o main ./cmd/server && \
    CGO_ENABLED=0 GOOS=linux go build -o seed ./cmd/seed

# Runtime stage
FROM alpine:latest

RUN apk --no-cache add ca-certificates wget

WORKDIR /root/

COPY --from=builder /app/main .
COPY --from=builder /app/seed .
COPY --from=builder /app/config ./config

# Download and install grpc_health_probe
RUN wget -qO/bin/grpc_health_probe https://github.com/grpc-ecosystem/grpc-health-probe/releases/download/v0.4.19/grpc_health_probe-linux-amd64 && \
    chmod +x /bin/grpc_health_probe

EXPOSE 50051

CMD ["./main"]
