from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class InferExercisesRequest(_message.Message):
    __slots__ = ("names",)
    NAMES_FIELD_NUMBER: _ClassVar[int]
    names: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, names: _Optional[_Iterable[str]] = ...) -> None: ...

class InferExercisesResponse(_message.Message):
    __slots__ = ("exercises",)
    EXERCISES_FIELD_NUMBER: _ClassVar[int]
    exercises: _containers.RepeatedCompositeFieldContainer[InferredExercise]
    def __init__(self, exercises: _Optional[_Iterable[_Union[InferredExercise, _Mapping]]] = ...) -> None: ...

class InferredExercise(_message.Message):
    __slots__ = ("exercise", "requested_name", "resolution", "confidence")
    class Resolution(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        RESOLUTION_UNSPECIFIED: _ClassVar[InferredExercise.Resolution]
        RESOLUTION_MATCHED: _ClassVar[InferredExercise.Resolution]
        RESOLUTION_INFERRED: _ClassVar[InferredExercise.Resolution]
    RESOLUTION_UNSPECIFIED: InferredExercise.Resolution
    RESOLUTION_MATCHED: InferredExercise.Resolution
    RESOLUTION_INFERRED: InferredExercise.Resolution
    EXERCISE_FIELD_NUMBER: _ClassVar[int]
    REQUESTED_NAME_FIELD_NUMBER: _ClassVar[int]
    RESOLUTION_FIELD_NUMBER: _ClassVar[int]
    CONFIDENCE_FIELD_NUMBER: _ClassVar[int]
    exercise: Exercise
    requested_name: str
    resolution: InferredExercise.Resolution
    confidence: float
    def __init__(self, exercise: _Optional[_Union[Exercise, _Mapping]] = ..., requested_name: _Optional[str] = ..., resolution: _Optional[_Union[InferredExercise.Resolution, str]] = ..., confidence: _Optional[float] = ...) -> None: ...

class Exercise(_message.Message):
    __slots__ = ("id", "name", "movement_pattern", "exercise_type", "intensity_category", "attributes", "muscles", "safety")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    MOVEMENT_PATTERN_FIELD_NUMBER: _ClassVar[int]
    EXERCISE_TYPE_FIELD_NUMBER: _ClassVar[int]
    INTENSITY_CATEGORY_FIELD_NUMBER: _ClassVar[int]
    ATTRIBUTES_FIELD_NUMBER: _ClassVar[int]
    MUSCLES_FIELD_NUMBER: _ClassVar[int]
    SAFETY_FIELD_NUMBER: _ClassVar[int]
    id: int
    name: str
    movement_pattern: str
    exercise_type: str
    intensity_category: str
    attributes: ExerciseAttributes
    muscles: _containers.RepeatedCompositeFieldContainer[MuscleTarget]
    safety: SafetyProfile
    def __init__(self, id: _Optional[int] = ..., name: _Optional[str] = ..., movement_pattern: _Optional[str] = ..., exercise_type: _Optional[str] = ..., intensity_category: _Optional[str] = ..., attributes: _Optional[_Union[ExerciseAttributes, _Mapping]] = ..., muscles: _Optional[_Iterable[_Union[MuscleTarget, _Mapping]]] = ..., safety: _Optional[_Union[SafetyProfile, _Mapping]] = ...) -> None: ...

class ExerciseAttributes(_message.Message):
    __slots__ = ("equipment", "laterality", "angle", "grip", "tempo", "force_vector")
    EQUIPMENT_FIELD_NUMBER: _ClassVar[int]
    LATERALITY_FIELD_NUMBER: _ClassVar[int]
    ANGLE_FIELD_NUMBER: _ClassVar[int]
    GRIP_FIELD_NUMBER: _ClassVar[int]
    TEMPO_FIELD_NUMBER: _ClassVar[int]
    FORCE_VECTOR_FIELD_NUMBER: _ClassVar[int]
    equipment: str
    laterality: str
    angle: str
    grip: str
    tempo: str
    force_vector: str
    def __init__(self, equipment: _Optional[str] = ..., laterality: _Optional[str] = ..., angle: _Optional[str] = ..., grip: _Optional[str] = ..., tempo: _Optional[str] = ..., force_vector: _Optional[str] = ...) -> None: ...

class MuscleTarget(_message.Message):
    __slots__ = ("name", "display_name", "role", "activation_percent")
    NAME_FIELD_NUMBER: _ClassVar[int]
    DISPLAY_NAME_FIELD_NUMBER: _ClassVar[int]
    ROLE_FIELD_NUMBER: _ClassVar[int]
    ACTIVATION_PERCENT_FIELD_NUMBER: _ClassVar[int]
    name: str
    display_name: str
    role: str
    activation_percent: int
    def __init__(self, name: _Optional[str] = ..., display_name: _Optional[str] = ..., role: _Optional[str] = ..., activation_percent: _Optional[int] = ...) -> None: ...

class SafetyProfile(_message.Message):
    __slots__ = ("injury_risk_level", "complexity_score", "joint_stress_areas")
    INJURY_RISK_LEVEL_FIELD_NUMBER: _ClassVar[int]
    COMPLEXITY_SCORE_FIELD_NUMBER: _ClassVar[int]
    JOINT_STRESS_AREAS_FIELD_NUMBER: _ClassVar[int]
    injury_risk_level: float
    complexity_score: float
    joint_stress_areas: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, injury_risk_level: _Optional[float] = ..., complexity_score: _Optional[float] = ..., joint_stress_areas: _Optional[_Iterable[str]] = ...) -> None: ...

class GetExercisesRequest(_message.Message):
    __slots__ = ("ids",)
    IDS_FIELD_NUMBER: _ClassVar[int]
    ids: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, ids: _Optional[_Iterable[int]] = ...) -> None: ...

class GetExercisesResponse(_message.Message):
    __slots__ = ("exercises",)
    EXERCISES_FIELD_NUMBER: _ClassVar[int]
    exercises: _containers.RepeatedCompositeFieldContainer[Exercise]
    def __init__(self, exercises: _Optional[_Iterable[_Union[Exercise, _Mapping]]] = ...) -> None: ...

class FindSubstitutionsRequest(_message.Message):
    __slots__ = ("exercise_id", "exclude_joint_stress", "exclude_exercise_ids", "limit")
    EXERCISE_ID_FIELD_NUMBER: _ClassVar[int]
    EXCLUDE_JOINT_STRESS_FIELD_NUMBER: _ClassVar[int]
    EXCLUDE_EXERCISE_IDS_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    exercise_id: int
    exclude_joint_stress: _containers.RepeatedScalarFieldContainer[str]
    exclude_exercise_ids: _containers.RepeatedScalarFieldContainer[int]
    limit: int
    def __init__(self, exercise_id: _Optional[int] = ..., exclude_joint_stress: _Optional[_Iterable[str]] = ..., exclude_exercise_ids: _Optional[_Iterable[int]] = ..., limit: _Optional[int] = ...) -> None: ...

class FindSubstitutionsResponse(_message.Message):
    __slots__ = ("substitutions",)
    SUBSTITUTIONS_FIELD_NUMBER: _ClassVar[int]
    substitutions: _containers.RepeatedCompositeFieldContainer[Substitution]
    def __init__(self, substitutions: _Optional[_Iterable[_Union[Substitution, _Mapping]]] = ...) -> None: ...

class Substitution(_message.Message):
    __slots__ = ("exercise", "score", "reason")
    EXERCISE_FIELD_NUMBER: _ClassVar[int]
    SCORE_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    exercise: Exercise
    score: float
    reason: str
    def __init__(self, exercise: _Optional[_Union[Exercise, _Mapping]] = ..., score: _Optional[float] = ..., reason: _Optional[str] = ...) -> None: ...

class GetMusclesRequest(_message.Message):
    __slots__ = ("names",)
    NAMES_FIELD_NUMBER: _ClassVar[int]
    names: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, names: _Optional[_Iterable[str]] = ...) -> None: ...

class GetMusclesResponse(_message.Message):
    __slots__ = ("muscles",)
    MUSCLES_FIELD_NUMBER: _ClassVar[int]
    muscles: _containers.RepeatedCompositeFieldContainer[Muscle]
    def __init__(self, muscles: _Optional[_Iterable[_Union[Muscle, _Mapping]]] = ...) -> None: ...

class Muscle(_message.Message):
    __slots__ = ("name", "display_name", "size", "recovery_hours", "antagonist", "is_compound_target")
    class Size(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        SIZE_UNSPECIFIED: _ClassVar[Muscle.Size]
        SIZE_SMALL: _ClassVar[Muscle.Size]
        SIZE_MEDIUM: _ClassVar[Muscle.Size]
        SIZE_LARGE: _ClassVar[Muscle.Size]
    SIZE_UNSPECIFIED: Muscle.Size
    SIZE_SMALL: Muscle.Size
    SIZE_MEDIUM: Muscle.Size
    SIZE_LARGE: Muscle.Size
    NAME_FIELD_NUMBER: _ClassVar[int]
    DISPLAY_NAME_FIELD_NUMBER: _ClassVar[int]
    SIZE_FIELD_NUMBER: _ClassVar[int]
    RECOVERY_HOURS_FIELD_NUMBER: _ClassVar[int]
    ANTAGONIST_FIELD_NUMBER: _ClassVar[int]
    IS_COMPOUND_TARGET_FIELD_NUMBER: _ClassVar[int]
    name: str
    display_name: str
    size: Muscle.Size
    recovery_hours: int
    antagonist: str
    is_compound_target: bool
    def __init__(self, name: _Optional[str] = ..., display_name: _Optional[str] = ..., size: _Optional[_Union[Muscle.Size, str]] = ..., recovery_hours: _Optional[int] = ..., antagonist: _Optional[str] = ..., is_compound_target: bool = ...) -> None: ...
