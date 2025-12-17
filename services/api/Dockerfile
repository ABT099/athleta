# Build stage
FROM node:24-alpine AS builder

# Install build dependencies for bcrypt
RUN apk add --no-cache python3 make g++

WORKDIR /app

# Install dependencies first (cached layer)
COPY package.json package-lock.json ./
RUN npm ci

# Copy source and build
COPY . .
RUN npm run build

# Prune dev dependencies
RUN npm prune --production

# Runtime stage
FROM node:22-alpine

RUN addgroup -g 1001 -S app && \
    adduser -S app -u 1001 -G app

WORKDIR /app

# Copy built app and production deps
COPY --from=builder --chown=app:app /app/dist ./dist
COPY --from=builder --chown=app:app /app/node_modules ./node_modules
COPY --from=builder --chown=app:app /app/package.json ./

# Copy proto files for gRPC
COPY --from=builder --chown=app:app /app/proto ./proto

USER app

EXPOSE 8000

CMD ["node", "dist/main"]

