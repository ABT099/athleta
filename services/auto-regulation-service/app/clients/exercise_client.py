"""
gRPC client for exercise-service.

A thin wrapper around the generated ExerciseService stub. The exercise domain
(exercises, muscles, substitutions) lives in exercise-service; this service
reads it over gRPC instead of SQLAlchemy.

Usage:
    with ExerciseClient() as client:
        exercises = client.get_exercises([1, 2, 3])
        muscles = client.get_muscles(["lats", "biceps"])
        subs = client.find_substitutions(exercise_id=5, limit=3)
"""
from __future__ import annotations

import json
import os
from typing import Iterable, List, Optional

import grpc

from app.grpc_gen.exercise.v1 import exercise_pb2 as pb
from app.grpc_gen.exercise.v1 import exercise_pb2_grpc as pb_grpc

DEFAULT_ADDR = "localhost:50051"
DEFAULT_TIMEOUT_SECONDS = 5.0

# Built-in gRPC retry policy applied to every method on the service. Only
# transient failures are retried; application errors (e.g. NOT_FOUND) are not.
_RETRY_SERVICE_CONFIG = json.dumps(
    {
        "methodConfig": [
            {
                "name": [{"service": "exercise.v1.ExerciseService"}],
                "retryPolicy": {
                    "maxAttempts": 4,
                    "initialBackoff": "0.1s",
                    "maxBackoff": "2s",
                    "backoffMultiplier": 2.0,
                    "retryableStatusCodes": [
                        "UNAVAILABLE",
                        "DEADLINE_EXCEEDED",
                        "RESOURCE_EXHAUSTED",
                    ],
                },
            }
        ]
    }
)

_CHANNEL_OPTIONS = [
    ("grpc.enable_retries", 1),
    ("grpc.service_config", _RETRY_SERVICE_CONFIG),
]


class ExerciseClient:
    """
    Context-managed gRPC client for exercise-service.

    The channel is opened on ``__enter__`` and closed on ``__exit__``; the
    client must be used inside a ``with`` block. The connection address comes
    from the ``EXERCISE_SERVICE_ADDR`` environment variable.
    """

    def __init__(
        self,
        addr: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._addr = addr or os.getenv("EXERCISE_SERVICE_ADDR", DEFAULT_ADDR)
        self._timeout = timeout
        self._channel: Optional[grpc.Channel] = None
        self._stub: Optional[pb_grpc.ExerciseServiceStub] = None

    def __enter__(self) -> "ExerciseClient":
        self._channel = grpc.insecure_channel(self._addr, options=_CHANNEL_OPTIONS)
        self._stub = pb_grpc.ExerciseServiceStub(self._channel)
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.close()
        return False

    def close(self) -> None:
        if self._channel is not None:
            self._channel.close()
            self._channel = None
            self._stub = None

    def _stub_or_raise(self) -> pb_grpc.ExerciseServiceStub:
        if self._stub is None:
            raise RuntimeError(
                "ExerciseClient must be used as a context manager "
                "(`with ExerciseClient() as client: ...`)"
            )
        return self._stub

    def get_exercises(self, ids: Iterable[int]) -> List[pb.Exercise]:
        """Fetch exercises by ID. Unknown IDs are omitted from the response."""
        ids = list(ids)
        if not ids:
            return []
        resp = self._stub_or_raise().GetExercises(
            pb.GetExercisesRequest(ids=ids), timeout=self._timeout
        )
        return list(resp.exercises)

    def get_muscles(self, names: Optional[Iterable[str]] = None) -> List[pb.Muscle]:
        """Fetch muscle metadata by name. Empty/None returns all muscles."""
        resp = self._stub_or_raise().GetMuscles(
            pb.GetMusclesRequest(names=list(names or [])), timeout=self._timeout
        )
        return list(resp.muscles)

    def find_substitutions(
        self,
        exercise_id: int,
        exclude_joints: Optional[Iterable[str]] = None,
        exclude_ids: Optional[Iterable[int]] = None,
        limit: int = 5,
    ) -> List[pb.Substitution]:
        """Find substitute exercises, scored by muscle/structural similarity."""
        req = pb.FindSubstitutionsRequest(
            exercise_id=exercise_id,
            exclude_joint_stress=list(exclude_joints or []),
            exclude_exercise_ids=list(exclude_ids or []),
            limit=limit,
        )
        resp = self._stub_or_raise().FindSubstitutions(req, timeout=self._timeout)
        return list(resp.substitutions)
