#!/usr/bin/env bash
# Regenerate the Python gRPC stubs for exercise-service from the shared proto.
#
# The generated stubs under app/grpc_gen/ are committed to the repo, so the
# Docker build does not need protoc. Run this script whenever
# proto/exercise/v1/exercise.proto changes.
#
# protobuf is pinned to the version in uv.lock so the runtime-version check
# baked into the generated *_pb2.py matches the installed protobuf (whose
# upper bound is constrained by tensorflow-cpu).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
OUT_DIR="$REPO_ROOT/services/auto-regulation-service/app/grpc_gen"
PROTO="proto/exercise/v1/exercise.proto"

GRPCIO_TOOLS_VERSION="1.76.0"
PROTOBUF_VERSION="6.33.2"

rm -rf "$OUT_DIR/exercise"
mkdir -p "$OUT_DIR"

cd "$REPO_ROOT"
uv run --no-project \
  --with "grpcio-tools==${GRPCIO_TOOLS_VERSION}" \
  --with "protobuf==${PROTOBUF_VERSION}" \
  python -m grpc_tools.protoc \
    -I proto \
    --python_out="$OUT_DIR" \
    --grpc_python_out="$OUT_DIR" \
    --pyi_out="$OUT_DIR" \
    "$PROTO"

# Make the generated tree importable as app.grpc_gen.*
touch "$OUT_DIR/__init__.py" \
      "$OUT_DIR/exercise/__init__.py" \
      "$OUT_DIR/exercise/v1/__init__.py"

# protoc emits an absolute import keyed off the proto package; rewrite it to a
# project-absolute import so it resolves as a normal package member.
GRPC_FILE="$OUT_DIR/exercise/v1/exercise_pb2_grpc.py"
python3 - "$GRPC_FILE" <<'PY'
import sys
path = sys.argv[1]
text = open(path).read()
text = text.replace(
    "from exercise.v1 import exercise_pb2",
    "from app.grpc_gen.exercise.v1 import exercise_pb2",
)
open(path, "w").write(text)
PY

echo "Generated stubs in $OUT_DIR"
