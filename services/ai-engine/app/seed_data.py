"""
Seed data for exercises library.

Contains common exercises with muscle groups and injury risk levels.
"""
from sqlalchemy.orm import Session
from app.models import Exercise
from app.database import SessionLocal


EXERCISE_SEED_DATA = [
    # === CHEST EXERCISES ===
    {
        "name": "Barbell Bench Press",
        "description": "Compound chest exercise",
        "equipment": "Barbell",
        "difficulty": "intermediate",
        "primary_muscles": ["chest"],
        "secondary_muscles": ["triceps", "shoulders"],
        "injury_risk_level": 2.0,
        "joint_stress_areas": ["shoulder", "elbow"],
        "movement_pattern": "push",
        "is_compound": 1
    },
    {
        "name": "Incline Dumbbell Press",
        "description": "Upper chest focused press",
        "equipment": "Dumbbells",
        "difficulty": "intermediate",
        "primary_muscles": ["chest"],
        "secondary_muscles": ["shoulders", "triceps"],
        "injury_risk_level": 1.5,
        "joint_stress_areas": ["shoulder"],
        "movement_pattern": "push",
        "is_compound": 1
    },
    {
        "name": "Cable Fly",
        "description": "Isolation chest exercise",
        "equipment": "Cable Machine",
        "difficulty": "beginner",
        "primary_muscles": ["chest"],
        "secondary_muscles": [],
        "injury_risk_level": 1.0,
        "joint_stress_areas": ["shoulder"],
        "movement_pattern": "fly",
        "is_compound": 0
    },
    {
        "name": "Push-Ups",
        "description": "Bodyweight chest exercise",
        "equipment": "None",
        "difficulty": "beginner",
        "primary_muscles": ["chest"],
        "secondary_muscles": ["triceps", "shoulders", "abs"],
        "injury_risk_level": 1.0,
        "joint_stress_areas": [],
        "movement_pattern": "push",
        "is_compound": 1
    },
    
    # === BACK EXERCISES ===
    {
        "name": "Barbell Deadlift",
        "description": "Full body posterior chain exercise",
        "equipment": "Barbell",
        "difficulty": "advanced",
        "primary_muscles": ["back", "glutes", "hamstrings"],
        "secondary_muscles": ["lower_back", "forearms"],
        "injury_risk_level": 2.5,
        "joint_stress_areas": ["lower_back", "hip"],
        "movement_pattern": "hinge",
        "is_compound": 1
    },
    {
        "name": "Pull-Ups",
        "description": "Bodyweight back exercise",
        "equipment": "Pull-up Bar",
        "difficulty": "intermediate",
        "primary_muscles": ["back"],
        "secondary_muscles": ["biceps", "forearms"],
        "injury_risk_level": 1.5,
        "joint_stress_areas": ["shoulder", "elbow"],
        "movement_pattern": "pull",
        "is_compound": 1
    },
    {
        "name": "Bent-Over Barbell Row",
        "description": "Compound back exercise",
        "equipment": "Barbell",
        "difficulty": "intermediate",
        "primary_muscles": ["back"],
        "secondary_muscles": ["biceps", "lower_back"],
        "injury_risk_level": 2.0,
        "joint_stress_areas": ["lower_back"],
        "movement_pattern": "pull",
        "is_compound": 1
    },
    {
        "name": "Lat Pulldown",
        "description": "Machine back exercise",
        "equipment": "Cable Machine",
        "difficulty": "beginner",
        "primary_muscles": ["back"],
        "secondary_muscles": ["biceps"],
        "injury_risk_level": 1.0,
        "joint_stress_areas": [],
        "movement_pattern": "pull",
        "is_compound": 1
    },
    {
        "name": "Cable Row",
        "description": "Cable machine rowing",
        "equipment": "Cable Machine",
        "difficulty": "beginner",
        "primary_muscles": ["back"],
        "secondary_muscles": ["biceps"],
        "injury_risk_level": 1.0,
        "joint_stress_areas": [],
        "movement_pattern": "pull",
        "is_compound": 1
    },
    
    # === SHOULDER EXERCISES ===
    {
        "name": "Overhead Press",
        "description": "Compound shoulder exercise",
        "equipment": "Barbell",
        "difficulty": "intermediate",
        "primary_muscles": ["shoulders"],
        "secondary_muscles": ["triceps", "abs"],
        "injury_risk_level": 2.5,
        "joint_stress_areas": ["shoulder", "lower_back"],
        "movement_pattern": "push",
        "is_compound": 1
    },
    {
        "name": "Dumbbell Lateral Raise",
        "description": "Shoulder isolation",
        "equipment": "Dumbbells",
        "difficulty": "beginner",
        "primary_muscles": ["shoulders"],
        "secondary_muscles": [],
        "injury_risk_level": 1.5,
        "joint_stress_areas": ["shoulder"],
        "movement_pattern": "raise",
        "is_compound": 0
    },
    {
        "name": "Face Pulls",
        "description": "Rear delt and upper back",
        "equipment": "Cable Machine",
        "difficulty": "beginner",
        "primary_muscles": ["shoulders", "back"],
        "secondary_muscles": [],
        "injury_risk_level": 1.0,
        "joint_stress_areas": [],
        "movement_pattern": "pull",
        "is_compound": 0
    },
    
    # === LEG EXERCISES ===
    {
        "name": "Barbell Back Squat",
        "description": "Compound leg exercise",
        "equipment": "Barbell",
        "difficulty": "intermediate",
        "primary_muscles": ["quadriceps", "glutes"],
        "secondary_muscles": ["hamstrings", "abs"],
        "injury_risk_level": 2.5,
        "joint_stress_areas": ["knee", "hip", "lower_back"],
        "movement_pattern": "squat",
        "is_compound": 1
    },
    {
        "name": "Romanian Deadlift",
        "description": "Hamstring focused hinge",
        "equipment": "Barbell",
        "difficulty": "intermediate",
        "primary_muscles": ["hamstrings", "glutes"],
        "secondary_muscles": ["lower_back"],
        "injury_risk_level": 2.0,
        "joint_stress_areas": ["lower_back", "hip"],
        "movement_pattern": "hinge",
        "is_compound": 1
    },
    {
        "name": "Leg Press",
        "description": "Machine leg exercise",
        "equipment": "Leg Press Machine",
        "difficulty": "beginner",
        "primary_muscles": ["quadriceps", "glutes"],
        "secondary_muscles": ["hamstrings"],
        "injury_risk_level": 1.5,
        "joint_stress_areas": ["knee"],
        "movement_pattern": "squat",
        "is_compound": 1
    },
    {
        "name": "Leg Extension",
        "description": "Quad isolation",
        "equipment": "Machine",
        "difficulty": "beginner",
        "primary_muscles": ["quadriceps"],
        "secondary_muscles": [],
        "injury_risk_level": 1.5,
        "joint_stress_areas": ["knee"],
        "movement_pattern": "extension",
        "is_compound": 0
    },
    {
        "name": "Leg Curl",
        "description": "Hamstring isolation",
        "equipment": "Machine",
        "difficulty": "beginner",
        "primary_muscles": ["hamstrings"],
        "secondary_muscles": [],
        "injury_risk_level": 1.0,
        "joint_stress_areas": [],
        "movement_pattern": "curl",
        "is_compound": 0
    },
    {
        "name": "Bulgarian Split Squat",
        "description": "Single leg squat variation",
        "equipment": "Dumbbells",
        "difficulty": "intermediate",
        "primary_muscles": ["quadriceps", "glutes"],
        "secondary_muscles": ["hamstrings"],
        "injury_risk_level": 1.5,
        "joint_stress_areas": ["knee"],
        "movement_pattern": "squat",
        "is_compound": 1
    },
    {
        "name": "Walking Lunges",
        "description": "Dynamic leg exercise",
        "equipment": "Dumbbells",
        "difficulty": "beginner",
        "primary_muscles": ["quadriceps", "glutes"],
        "secondary_muscles": ["hamstrings"],
        "injury_risk_level": 1.5,
        "joint_stress_areas": ["knee"],
        "movement_pattern": "lunge",
        "is_compound": 1
    },
    
    # === ARM EXERCISES ===
    {
        "name": "Barbell Curl",
        "description": "Bicep exercise",
        "equipment": "Barbell",
        "difficulty": "beginner",
        "primary_muscles": ["biceps"],
        "secondary_muscles": ["forearms"],
        "injury_risk_level": 1.0,
        "joint_stress_areas": [],
        "movement_pattern": "curl",
        "is_compound": 0
    },
    {
        "name": "Hammer Curl",
        "description": "Bicep and forearm exercise",
        "equipment": "Dumbbells",
        "difficulty": "beginner",
        "primary_muscles": ["biceps"],
        "secondary_muscles": ["forearms"],
        "injury_risk_level": 1.0,
        "joint_stress_areas": [],
        "movement_pattern": "curl",
        "is_compound": 0
    },
    {
        "name": "Tricep Dips",
        "description": "Bodyweight tricep exercise",
        "equipment": "Dip Station",
        "difficulty": "intermediate",
        "primary_muscles": ["triceps"],
        "secondary_muscles": ["chest", "shoulders"],
        "injury_risk_level": 2.0,
        "joint_stress_areas": ["shoulder", "elbow"],
        "movement_pattern": "push",
        "is_compound": 1
    },
    {
        "name": "Tricep Pushdown",
        "description": "Cable tricep isolation",
        "equipment": "Cable Machine",
        "difficulty": "beginner",
        "primary_muscles": ["triceps"],
        "secondary_muscles": [],
        "injury_risk_level": 1.0,
        "joint_stress_areas": [],
        "movement_pattern": "extension",
        "is_compound": 0
    },
    {
        "name": "Skull Crushers",
        "description": "Tricep isolation exercise",
        "equipment": "Barbell/EZ Bar",
        "difficulty": "intermediate",
        "primary_muscles": ["triceps"],
        "secondary_muscles": [],
        "injury_risk_level": 1.5,
        "joint_stress_areas": ["elbow"],
        "movement_pattern": "extension",
        "is_compound": 0
    },
    
    # === CORE EXERCISES ===
    {
        "name": "Plank",
        "description": "Core stabilization",
        "equipment": "None",
        "difficulty": "beginner",
        "primary_muscles": ["abs"],
        "secondary_muscles": ["shoulders"],
        "injury_risk_level": 1.0,
        "joint_stress_areas": [],
        "movement_pattern": "hold",
        "is_compound": 0
    },
    {
        "name": "Hanging Leg Raise",
        "description": "Advanced ab exercise",
        "equipment": "Pull-up Bar",
        "difficulty": "advanced",
        "primary_muscles": ["abs"],
        "secondary_muscles": ["forearms"],
        "injury_risk_level": 1.5,
        "joint_stress_areas": ["shoulder"],
        "movement_pattern": "raise",
        "is_compound": 0
    },
    {
        "name": "Cable Crunch",
        "description": "Weighted ab exercise",
        "equipment": "Cable Machine",
        "difficulty": "beginner",
        "primary_muscles": ["abs"],
        "secondary_muscles": [],
        "injury_risk_level": 1.0,
        "joint_stress_areas": [],
        "movement_pattern": "crunch",
        "is_compound": 0
    },
    
    # === CALF EXERCISES ===
    {
        "name": "Standing Calf Raise",
        "description": "Calf isolation",
        "equipment": "Machine",
        "difficulty": "beginner",
        "primary_muscles": ["calves"],
        "secondary_muscles": [],
        "injury_risk_level": 1.0,
        "joint_stress_areas": [],
        "movement_pattern": "raise",
        "is_compound": 0
    },
    {
        "name": "Seated Calf Raise",
        "description": "Soleus focused",
        "equipment": "Machine",
        "difficulty": "beginner",
        "primary_muscles": ["calves"],
        "secondary_muscles": [],
        "injury_risk_level": 1.0,
        "joint_stress_areas": [],
        "movement_pattern": "raise",
        "is_compound": 0
    }
]


def seed_exercises(db: Session):
    """
    Seed the database with common exercises.
    
    Args:
        db: Database session
    """
    # Check if exercises already exist
    existing_count = db.query(Exercise).count()
    if existing_count > 0:
        print(f"Database already has {existing_count} exercises. Skipping seed.")
        return
    
    print("Seeding exercises...")
    
    for exercise_data in EXERCISE_SEED_DATA:
        exercise = Exercise(**exercise_data)
        db.add(exercise)
    
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


