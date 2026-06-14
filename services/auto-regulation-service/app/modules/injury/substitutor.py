"""
Exercise Substitution adapter.

Substitution scoring (muscle-activation overlap + structural similarity) now
lives in exercise-service. This is a thin adapter over the FindSubstitutions
RPC that maps the response to the shape plateau intervention expects.
"""
from typing import Dict, Iterable, Optional

from app.clients.exercise_client import ExerciseClient


class ExerciseSubstitutor:
    """Adapter over exercise-service's FindSubstitutions RPC."""

    def __init__(self, exercise_client: Optional[ExerciseClient] = None):
        # An open ExerciseClient may be injected to share a channel; otherwise a
        # short-lived one is opened per call.
        self._client = exercise_client

    def find_substitute(
        self,
        exercise_id: int,
        variation_type: str = "equipment_or_angle",
        exclude_joints: Optional[Iterable[str]] = None,
        exclude_ids: Optional[Iterable[int]] = None,
    ) -> Optional[Dict]:
        """
        Find a single substitute exercise.

        Returns a dict with the fields callers use (`exercise_id`, `name`,
        `substitution_type`), or None when no substitution is available.
        """
        substitutions = self._find_substitutions(
            exercise_id, exclude_joints, exclude_ids, limit=1
        )
        if not substitutions:
            return None

        top = substitutions[0]
        return {
            "exercise_id": top.exercise.id,
            "name": top.exercise.name,
            "substitution_type": variation_type,
        }

    def _find_substitutions(
        self,
        exercise_id: int,
        exclude_joints: Optional[Iterable[str]],
        exclude_ids: Optional[Iterable[int]],
        limit: int,
    ):
        if self._client is not None:
            return self._client.find_substitutions(
                exercise_id, exclude_joints, exclude_ids, limit
            )
        with ExerciseClient() as client:
            return client.find_substitutions(
                exercise_id, exclude_joints, exclude_ids, limit
            )
