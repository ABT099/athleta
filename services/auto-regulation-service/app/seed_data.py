"""
Seed data for exercises library with role-based muscle targeting.

Contains common exercises with muscle roles (prime_mover, synergist, stabilizer).
"""
from sqlalchemy.orm import Session
from autoregulation.models import Exercise, MuscleGroupModel, ExerciseMuscle
from autoregulation.database import SessionLocal


def activation_to_role(activation_percent: int) -> str:
    """
    Convert activation percentage to muscle role.
    
    Args:
        activation_percent: Activation percentage (0-100)
    
    Returns:
        Role string: 'prime_mover', 'synergist', or 'stabilizer'
    """
    if activation_percent >= 70:
        return "prime_mover"
    elif activation_percent >= 40:
        return "synergist"
    else:
        return "stabilizer"


EXERCISE_SEED_DATA = [
    # === CHEST EXERCISES ===
    {
        "name": "Barbell Bench Press",
        "equipment": "Barbell",
        "injury_risk_level": 2.0,
        "joint_stress_areas": ["shoulder", "elbow"],
        "movement_pattern": "push",
        "exercise_type": "compound",
        "complexity_score": 0.7,
        "intensity_category": "compound_heavy",
        "muscles": [
            ("mid_chest", 90),
            ("anterior_delt", 60),
            ("triceps", 50),
            ("upper_chest", 30),
            ("lower_chest", 25),
        ]
    },
    {
        "name": "Incline Dumbbell Press",
        "equipment": "Dumbbells",
        "injury_risk_level": 1.5,
        "joint_stress_areas": ["shoulder"],
        "movement_pattern": "push",
        "exercise_type": "compound",
        "complexity_score": 0.6,
        "intensity_category": "compound_moderate",
        "muscles": [
            ("upper_chest", 85),
            ("anterior_delt", 65),
            ("triceps", 45),
            ("mid_chest", 40),
        ]
    },
    {
        "name": "Cable Fly",
        "equipment": "Cable Machine",
        "injury_risk_level": 1.0,
        "joint_stress_areas": ["shoulder"],
        "movement_pattern": "fly",
        "exercise_type": "isolation",
        "complexity_score": 0.3,
        "intensity_category": "isolation",
        "muscles": [
            ("mid_chest", 80),
            ("upper_chest", 30),
            ("lower_chest", 30),
        ]
    },
    {
        "name": "Push-Ups",
        "equipment": "None",
        "injury_risk_level": 1.0,
        "joint_stress_areas": [],
        "movement_pattern": "push",
        "exercise_type": "compound",
        "complexity_score": 0.2,
        "intensity_category": "compound_moderate",
        "muscles": [
            ("mid_chest", 75),
            ("triceps", 50),
            ("anterior_delt", 45),
            ("abs", 20),
        ]
    },
    
    # === BACK EXERCISES ===
    {
        "name": "Barbell Deadlift",
        "equipment": "Barbell",
        "injury_risk_level": 2.5,
        "joint_stress_areas": ["lower_back", "hip"],
        "movement_pattern": "hinge",
        "exercise_type": "compound",
        "complexity_score": 0.9,
        "intensity_category": "compound_heavy",
        "muscles": [
            ("erector_spinae", 85),
            ("glutes", 80),
            ("hamstrings", 75),
            ("upper_traps", 60),
            ("lats", 40),
            ("forearms", 35),
        ]
    },
    {
        "name": "Pull-Ups",
        "equipment": "Pull-up Bar",
        "injury_risk_level": 1.5,
        "joint_stress_areas": ["shoulder", "elbow"],
        "movement_pattern": "pull",
        "exercise_type": "compound",
        "complexity_score": 0.6,
        "intensity_category": "compound_moderate",
        "muscles": [
            ("lats", 85),
            ("biceps", 60),
            ("mid_back", 50),
            ("posterior_delt", 30),
            ("forearms", 25),
        ]
    },
    {
        "name": "Bent-Over Barbell Row",
        "equipment": "Barbell",
        "injury_risk_level": 2.0,
        "joint_stress_areas": ["lower_back"],
        "movement_pattern": "pull",
        "exercise_type": "compound",
        "complexity_score": 0.7,
        "intensity_category": "compound_heavy",
        "muscles": [
            ("mid_back", 80),
            ("lats", 70),
            ("biceps", 50),
            ("erector_spinae", 45),
            ("posterior_delt", 40),
        ]
    },
    {
        "name": "Lat Pulldown",
        "equipment": "Cable Machine",
        "injury_risk_level": 1.0,
        "joint_stress_areas": [],
        "movement_pattern": "pull",
        "exercise_type": "compound",
        "complexity_score": 0.3,
        "intensity_category": "compound_moderate",
        "muscles": [
            ("lats", 85),
            ("biceps", 55),
            ("mid_back", 45),
        ]
    },
    {
        "name": "Cable Row",
        "equipment": "Cable Machine",
        "injury_risk_level": 1.0,
        "joint_stress_areas": [],
        "movement_pattern": "pull",
        "exercise_type": "compound",
        "complexity_score": 0.3,
        "intensity_category": "compound_moderate",
        "muscles": [
            ("mid_back", 80),
            ("lats", 65),
            ("biceps", 50),
            ("posterior_delt", 35),
        ]
    },
    
    # === SHOULDER EXERCISES ===
    {
        "name": "Overhead Press",
        "equipment": "Barbell",
        "injury_risk_level": 2.5,
        "joint_stress_areas": ["shoulder", "lower_back"],
        "movement_pattern": "push",
        "exercise_type": "compound",
        "complexity_score": 0.7,
        "intensity_category": "compound_heavy",
        "muscles": [
            ("anterior_delt", 85),
            ("lateral_delt", 60),
            ("triceps", 55),
            ("upper_traps", 40),
            ("abs", 25),
        ]
    },
    {
        "name": "Dumbbell Lateral Raise",
        "equipment": "Dumbbells",
        "injury_risk_level": 1.5,
        "joint_stress_areas": ["shoulder"],
        "movement_pattern": "raise",
        "exercise_type": "isolation",
        "complexity_score": 0.2,
        "intensity_category": "isolation",
        "muscles": [
            ("lateral_delt", 90),
            ("anterior_delt", 20),
        ]
    },
    {
        "name": "Face Pulls",
        "equipment": "Cable Machine",
        "injury_risk_level": 1.0,
        "joint_stress_areas": [],
        "movement_pattern": "pull",
        "exercise_type": "isolation",
        "complexity_score": 0.3,
        "intensity_category": "isolation",
        "muscles": [
            ("posterior_delt", 85),
            ("mid_back", 50),
            ("upper_traps", 30),
        ]
    },
    
    # === LEG EXERCISES ===
    {
        "name": "Barbell Back Squat",
        "equipment": "Barbell",
        "injury_risk_level": 2.5,
        "joint_stress_areas": ["knee", "hip", "lower_back"],
        "movement_pattern": "squat",
        "exercise_type": "compound",
        "complexity_score": 0.8,
        "intensity_category": "compound_heavy",
        "muscles": [
            ("quadriceps", 90),
            ("glutes", 75),
            ("hamstrings", 40),
            ("erector_spinae", 35),
            ("abs", 25),
        ]
    },
    {
        "name": "Romanian Deadlift",
        "equipment": "Barbell",
        "injury_risk_level": 2.0,
        "joint_stress_areas": ["lower_back", "hip"],
        "movement_pattern": "hinge",
        "exercise_type": "compound",
        "complexity_score": 0.7,
        "intensity_category": "compound_heavy",
        "muscles": [
            ("hamstrings", 85),
            ("glutes", 75),
            ("erector_spinae", 60),
            ("forearms", 30),
        ]
    },
    {
        "name": "Leg Press",
        "equipment": "Leg Press Machine",
        "injury_risk_level": 1.5,
        "joint_stress_areas": ["knee"],
        "movement_pattern": "squat",
        "exercise_type": "compound",
        "complexity_score": 0.3,
        "intensity_category": "compound_moderate",
        "muscles": [
            ("quadriceps", 85),
            ("glutes", 70),
            ("hamstrings", 35),
        ]
    },
    {
        "name": "Leg Extension",
        "equipment": "Machine",
        "injury_risk_level": 1.5,
        "joint_stress_areas": ["knee"],
        "movement_pattern": "extension",
        "exercise_type": "isolation",
        "complexity_score": 0.1,
        "intensity_category": "isolation",
        "muscles": [
            ("quadriceps", 95),
        ]
    },
    {
        "name": "Leg Curl",
        "equipment": "Machine",
        "injury_risk_level": 1.0,
        "joint_stress_areas": [],
        "movement_pattern": "curl",
        "exercise_type": "isolation",
        "complexity_score": 0.1,
        "intensity_category": "isolation",
        "muscles": [
            ("hamstrings", 95),
        ]
    },
    {
        "name": "Bulgarian Split Squat",
        "equipment": "Dumbbells",
        "injury_risk_level": 1.5,
        "joint_stress_areas": ["knee"],
        "movement_pattern": "squat",
        "exercise_type": "compound",
        "complexity_score": 0.6,
        "intensity_category": "compound_moderate",
        "muscles": [
            ("quadriceps", 85),
            ("glutes", 75),
            ("hamstrings", 40),
        ]
    },
    {
        "name": "Walking Lunges",
        "equipment": "Dumbbells",
        "injury_risk_level": 1.5,
        "joint_stress_areas": ["knee"],
        "movement_pattern": "lunge",
        "exercise_type": "compound",
        "complexity_score": 0.5,
        "intensity_category": "compound_moderate",
        "muscles": [
            ("quadriceps", 80),
            ("glutes", 70),
            ("hamstrings", 35),
        ]
    },
    
    # === ARM EXERCISES ===
    {
        "name": "Barbell Curl",
        "equipment": "Barbell",
        "injury_risk_level": 1.0,
        "joint_stress_areas": [],
        "movement_pattern": "curl",
        "exercise_type": "isolation",
        "complexity_score": 0.2,
        "intensity_category": "isolation",
        "muscles": [
            ("biceps", 95),
            ("forearms", 25),
        ]
    },
    {
        "name": "Hammer Curl",
        "equipment": "Dumbbells",
        "injury_risk_level": 1.0,
        "joint_stress_areas": [],
        "movement_pattern": "curl",
        "exercise_type": "isolation",
        "complexity_score": 0.2,
        "intensity_category": "isolation",
        "muscles": [
            ("biceps", 85),
            ("forearms", 60),
        ]
    },
    {
        "name": "Tricep Dips",
        "equipment": "Dip Station",
        "injury_risk_level": 2.0,
        "joint_stress_areas": ["shoulder", "elbow"],
        "movement_pattern": "push",
        "exercise_type": "compound",
        "complexity_score": 0.5,
        "intensity_category": "compound_moderate",
        "muscles": [
            ("triceps", 85),
            ("lower_chest", 50),
            ("anterior_delt", 40),
        ]
    },
    {
        "name": "Tricep Pushdown",
        "equipment": "Cable Machine",
        "injury_risk_level": 1.0,
        "joint_stress_areas": [],
        "movement_pattern": "extension",
        "exercise_type": "isolation",
        "complexity_score": 0.2,
        "intensity_category": "isolation",
        "muscles": [
            ("triceps", 95),
        ]
    },
    {
        "name": "Skull Crushers",
        "equipment": "Barbell/EZ Bar",
        "injury_risk_level": 1.5,
        "joint_stress_areas": ["elbow"],
        "movement_pattern": "extension",
        "exercise_type": "isolation",
        "complexity_score": 0.4,
        "intensity_category": "isolation",
        "muscles": [
            ("triceps", 90),
        ]
    },
    
    # === CORE EXERCISES ===
    {
        "name": "Plank",
        "equipment": "None",
        "injury_risk_level": 1.0,
        "joint_stress_areas": [],
        "movement_pattern": "hold",
        "exercise_type": "isolation",
        "complexity_score": 0.2,
        "intensity_category": "isolation",
        "muscles": [
            ("abs", 85),
            ("erector_spinae", 30),
            ("anterior_delt", 15),
        ]
    },
    {
        "name": "Hanging Leg Raise",
        "equipment": "Pull-up Bar",
        "injury_risk_level": 1.5,
        "joint_stress_areas": ["shoulder"],
        "movement_pattern": "raise",
        "exercise_type": "isolation",
        "complexity_score": 0.6,
        "intensity_category": "isolation",
        "muscles": [
            ("abs", 90),
            ("hip_flexors", 60),
            ("forearms", 25),
        ]
    },
    {
        "name": "Cable Crunch",
        "equipment": "Cable Machine",
        "injury_risk_level": 1.0,
        "joint_stress_areas": [],
        "movement_pattern": "crunch",
        "exercise_type": "isolation",
        "complexity_score": 0.2,
        "intensity_category": "isolation",
        "muscles": [
            ("abs", 95),
        ]
    },
    
    # === CALF EXERCISES ===
    {
        "name": "Standing Calf Raise",
        "equipment": "Machine",
        "injury_risk_level": 1.0,
        "joint_stress_areas": [],
        "movement_pattern": "raise",
        "exercise_type": "isolation",
        "complexity_score": 0.1,
        "intensity_category": "isolation",
        "muscles": [
            ("calves", 95),
        ]
    },
    {
        "name": "Seated Calf Raise",
        "equipment": "Machine",
        "injury_risk_level": 1.0,
        "joint_stress_areas": [],
        "movement_pattern": "raise",
        "exercise_type": "isolation",
        "complexity_score": 0.1,
        "intensity_category": "isolation",
        "muscles": [
            ("calves", 95),
        ]
    }
]


def seed_exercises(db: Session):
    """
    Seed the database with common exercises and their muscle activations.
    
    Args:
        db: Database session
    """
    # Check if exercises already exist
    existing_count = db.query(Exercise).count()
    if existing_count > 0:
        print(f"Database already has {existing_count} exercises. Skipping seed.")
        return
    
    # Check if muscle groups exist
    muscle_count = db.query(MuscleGroupModel).count()
    if muscle_count == 0:
        print("ERROR: No muscle groups found. Run Drizzle migration 0007_seed_muscle_groups first to seed muscle groups.")
        return
    
    # Get all muscle groups for lookup
    muscles = {m.name: m for m in db.query(MuscleGroupModel).all()}
    
    print("Seeding exercises...")
    
    for exercise_data in EXERCISE_SEED_DATA:
        # Extract muscle data (use .get() to avoid mutating the original data)
        muscle_activations = exercise_data.get("muscles", [])
        
        # Create exercise (exclude "muscles" key as it's not an Exercise model field)
        exercise_data_copy = {k: v for k, v in exercise_data.items() if k != "muscles"}
        exercise = Exercise(**exercise_data_copy)
        db.add(exercise)
        db.flush()  # Get the exercise ID
        
        # Create muscle links with roles
        for muscle_name, activation_percent in muscle_activations:
            if muscle_name not in muscles:
                print(f"WARNING: Muscle '{muscle_name}' not found for exercise '{exercise.name}'")
                continue
            
            # Convert activation percentage to role
            role = activation_to_role(activation_percent)
            
            link = ExerciseMuscle(
                exercise_id=exercise.id,
                muscle_group_id=muscles[muscle_name].id,
                role=role
            )
            db.add(link)
    
    db.commit()
    print(f"✓ Seeded {len(EXERCISE_SEED_DATA)} exercises successfully!")


def main():
    """Main function to run seeding."""
    db = SessionLocal()
    try:
        seed_exercises(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
