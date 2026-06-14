"""
In-memory fake of exercise-service for tests.

The auto-regulation-service reads the exercise domain over gRPC. Tests run the
real service logic (against a real Postgres via testcontainers) but resolve the
gRPC boundary through this fake, which returns real protobuf messages. The
``fake_exercise_service`` autouse fixture (conftest) resets this registry and
patches ``ExerciseClient`` to delegate here.
"""
from __future__ import annotations

import itertools
from typing import Iterable, List, Optional, Sequence, Tuple, Union

from app.grpc_gen.exercise.v1 import exercise_pb2 as pb

# Muscle taxonomy mirrors what production seeds in exercise-service.
# (name, display_name, size, recovery_hours)
_DEFAULT_MUSCLES: List[Tuple[str, str, str, int]] = [
    ("mid_chest", "Mid Chest", "large", 72),
    ("upper_chest", "Upper Chest", "large", 72),
    ("lower_chest", "Lower Chest", "large", 72),
    ("lats", "Lats", "large", 72),
    ("mid_back", "Mid Back", "medium", 60),
    ("upper_traps", "Upper Traps", "medium", 60),
    ("lower_traps", "Lower Traps", "medium", 60),
    ("anterior_delt", "Front Delts", "medium", 60),
    ("lateral_delt", "Side Delts", "small", 48),
    ("posterior_delt", "Rear Delts", "small", 48),
    ("biceps", "Biceps", "small", 48),
    ("triceps", "Triceps", "small", 48),
    ("forearms", "Forearms", "small", 48),
    ("quadriceps", "Quadriceps", "large", 72),
    ("hamstrings", "Hamstrings", "large", 72),
    ("glutes", "Glutes", "large", 72),
    ("hip_flexors", "Hip Flexors", "medium", 60),
    ("calves", "Calves", "small", 48),
    ("abs", "Abs", "medium", 60),
    ("erector_spinae", "Lower Back", "medium", 60),
]

_SIZE_ENUM = {
    "small": pb.Muscle.SIZE_SMALL,
    "medium": pb.Muscle.SIZE_MEDIUM,
    "large": pb.Muscle.SIZE_LARGE,
}

# proto activation_percent derived from role (matches the real service: 85/55/25)
_ROLE_ACTIVATION = {"prime_mover": 85, "synergist": 55, "stabilizer": 25}

# A muscle spec is either ("mid_chest", "prime_mover") or ("mid_chest", 90),
# where an int is an activation percentage converted to a role.
MuscleSpec = Tuple[str, Union[str, int]]


def _activation_to_role(activation_percent: int) -> str:
    if activation_percent >= 70:
        return "prime_mover"
    if activation_percent >= 40:
        return "synergist"
    return "stabilizer"


class FakeExerciseService:
    """In-memory registry returning real protobuf messages."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._muscles: dict[str, pb.Muscle] = {}
        self._exercises: dict[int, pb.Exercise] = {}
        self._ids = itertools.count(1)
        for name, display_name, size, recovery_hours in _DEFAULT_MUSCLES:
            self.add_muscle(name, display_name, size, recovery_hours)

    # ---- registration -----------------------------------------------------
    def add_muscle(
        self,
        name: str,
        display_name: str,
        size: str,
        recovery_hours: int,
        is_compound_target: bool = False,
        antagonist: str = "",
    ) -> pb.Muscle:
        muscle = pb.Muscle(
            name=name,
            display_name=display_name,
            size=_SIZE_ENUM[size],
            recovery_hours=recovery_hours,
            is_compound_target=is_compound_target,
            antagonist=antagonist,
        )
        self._muscles[name] = muscle
        return muscle

    def add_exercise(
        self,
        *,
        name: str,
        muscles: Sequence[MuscleSpec],
        exercise_id: Optional[int] = None,
        exercise_type: str = "compound",
        intensity_category: Optional[str] = None,
        movement_pattern: str = "",
        complexity_score: float = 1.0,
        injury_risk_level: float = 0.5,
        joint_stress_areas: Optional[Iterable[str]] = None,
    ) -> pb.Exercise:
        exercise_id = exercise_id if exercise_id is not None else next(self._ids)
        if intensity_category is None:
            intensity_category = (
                "compound_moderate" if exercise_type == "compound" else "isolation"
            )

        targets = []
        for muscle_name, role_or_activation in muscles:
            role = (
                role_or_activation
                if isinstance(role_or_activation, str)
                else _activation_to_role(role_or_activation)
            )
            targets.append(
                pb.MuscleTarget(
                    name=muscle_name,
                    display_name=self._muscles[muscle_name].display_name
                    if muscle_name in self._muscles
                    else muscle_name,
                    role=role,
                    activation_percent=_ROLE_ACTIVATION.get(role, 25),
                )
            )

        exercise = pb.Exercise(
            id=exercise_id,
            name=name,
            movement_pattern=movement_pattern,
            exercise_type=exercise_type,
            intensity_category=intensity_category,
            muscles=targets,
            safety=pb.SafetyProfile(
                injury_risk_level=injury_risk_level,
                complexity_score=complexity_score,
                joint_stress_areas=list(joint_stress_areas or []),
            ),
        )
        self._exercises[exercise_id] = exercise
        return exercise

    # ---- gRPC surface (mirrors ExerciseClient) ----------------------------
    def get_exercises(self, ids: Iterable[int]) -> List[pb.Exercise]:
        return [self._exercises[i] for i in ids if i in self._exercises]

    def get_muscles(self, names: Optional[Iterable[str]] = None) -> List[pb.Muscle]:
        names = list(names or [])
        if not names:
            return list(self._muscles.values())
        return [self._muscles[n] for n in names if n in self._muscles]

    def find_substitutions(
        self,
        exercise_id: int,
        exclude_joints: Optional[Iterable[str]] = None,
        exclude_ids: Optional[Iterable[int]] = None,
        limit: int = 5,
    ) -> List[pb.Substitution]:
        excluded = set(exclude_ids or [])
        excluded.add(exercise_id)
        excluded_joints = set(exclude_joints or [])

        substitutions: List[pb.Substitution] = []
        for eid, exercise in self._exercises.items():
            if eid in excluded:
                continue
            if excluded_joints & set(exercise.safety.joint_stress_areas):
                continue
            substitutions.append(
                pb.Substitution(
                    exercise=exercise,
                    score=0.8,
                    reason="targets same muscles, similar movement pattern",
                )
            )
            if len(substitutions) >= limit:
                break
        return substitutions


# Module-level singleton shared by the autouse fixture and ExerciseFactory.
FAKE = FakeExerciseService()
