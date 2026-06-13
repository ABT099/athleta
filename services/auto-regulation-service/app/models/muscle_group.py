"""
Muscle group models for granular muscle targeting.
"""
from sqlalchemy import Column, Integer, String, Enum, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from autoregulation.database import Base, get_schema_table_args, get_fk_reference


class MuscleGroupModel(Base):
    """
    Muscle group with metadata for recovery and targeting.
    
    20 granular muscles (vs old 12):
    - Chest: upper_chest, mid_chest, lower_chest
    - Back: lats, upper_traps, mid_back, lower_traps
    - Shoulders: anterior_delt, lateral_delt, posterior_delt
    - Arms: biceps, triceps, forearms
    - Legs: quadriceps, hamstrings, glutes, hip_flexors, calves
    - Core: abs, erector_spinae
    """
    __tablename__ = "muscle_groups"
    __table_args__ = get_schema_table_args("public")
    
    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False, index=True)
    display_name = Column(String(100), nullable=False)
    size = Column(Enum("small", "medium", "large", name="muscle_size_enum"), nullable=False)
    base_recovery_hours = Column(Integer, nullable=False)
    is_compound_target = Column(Boolean, nullable=False, default=False)
    antagonist_id = Column(Integer, ForeignKey(get_fk_reference("muscle_groups.id")), nullable=True)
    
    # Relationships
    antagonist = relationship("MuscleGroupModel", remote_side=[id], foreign_keys=[antagonist_id])
    exercise_links = relationship("ExerciseMuscle", back_populates="muscle_group", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<MuscleGroupModel(id={self.id}, name={self.name})>"


class ExerciseMuscle(Base):
    """
    Junction table linking exercises to muscles with functional roles.
    
    Role-based muscle targeting:
    - prime_mover: The muscle doing the majority of the work
    - synergist: Assists the prime mover significantly
    - stabilizer: Holds position, prevents unwanted movement
    """
    __tablename__ = "exercise_muscles"
    __table_args__ = get_schema_table_args("public")
    
    id = Column(Integer, primary_key=True)
    exercise_id = Column(Integer, ForeignKey(get_fk_reference("exercises.id"), ondelete="CASCADE"), nullable=False, index=True)
    muscle_group_id = Column(Integer, ForeignKey(get_fk_reference("muscle_groups.id"), ondelete="CASCADE"), nullable=False, index=True)
    role = Column(Enum("prime_mover", "synergist", "stabilizer", name="muscle_role_enum"), nullable=False)
    
    # Relationships
    exercise = relationship("Exercise", back_populates="muscle_links")
    muscle_group = relationship("MuscleGroupModel", back_populates="exercise_links")
    
    def __repr__(self):
        return f"<ExerciseMuscle(exercise_id={self.exercise_id}, muscle_id={self.muscle_group_id}, role={self.role})>"
