"""Schema separation - move AI Engine tables to ai_analysis schema

Revision ID: 008
Revises: 007
Create Date: 2025-01-22 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '008'
down_revision = '007'
branch_labels = None
depends_on = None

# List of AI Engine tables to move to ai_analysis schema
AI_ENGINE_TABLES = [
    'plan_entries',
    'workout_sessions',
    'exercise_sets',
    'recovery_metrics',
    'athlete_rpe_calibration',
    'performance_trends',
    'exercise_progression_tracking',
    'ml_model_metadata',
    'exercise_personal_records',
    'form_quality_trends',
]

# Foreign key constraints that reference public schema tables
# Format: (table_name, constraint_name, referenced_table, columns, referenced_columns)
CROSS_SCHEMA_FOREIGN_KEYS = [
    # plan_entries references public.workout_plans
    ('plan_entries', 'plan_entries_workout_plan_id_fkey', 'workout_plans', ['workout_plan_id'], ['id']),
    
    # workout_sessions references public.athletes and public.workout_days
    ('workout_sessions', 'workout_sessions_athlete_id_fkey', 'athletes', ['athlete_id'], ['id']),
    ('workout_sessions', 'workout_sessions_workout_day_id_fkey', 'workout_days', ['workout_day_id'], ['id']),
    
    # exercise_sets references public.exercises and ai_analysis.workout_sessions
    ('exercise_sets', 'exercise_sets_exercise_id_fkey', 'exercises', ['exercise_id'], ['id']),
    ('exercise_sets', 'exercise_sets_workout_session_id_fkey', 'ai_analysis.workout_sessions', ['workout_session_id'], ['id']),
    
    # recovery_metrics references public.athletes
    ('recovery_metrics', 'recovery_metrics_athlete_id_fkey', 'athletes', ['athlete_id'], ['id']),
    
    # athlete_rpe_calibration references public.athletes and public.exercises
    ('athlete_rpe_calibration', 'athlete_rpe_calibration_athlete_id_fkey', 'athletes', ['athlete_id'], ['id']),
    ('athlete_rpe_calibration', 'athlete_rpe_calibration_exercise_id_fkey', 'exercises', ['exercise_id'], ['id']),
    
    # performance_trends references public.athletes and ai_analysis.workout_sessions
    ('performance_trends', 'performance_trends_athlete_id_fkey', 'athletes', ['athlete_id'], ['id']),
    ('performance_trends', 'performance_trends_workout_session_id_fkey', 'ai_analysis.workout_sessions', ['workout_session_id'], ['id']),
    
    # exercise_progression_tracking references public.athletes, public.exercises, and ai_analysis.workout_sessions
    ('exercise_progression_tracking', 'exercise_progression_tracking_athlete_id_fkey', 'athletes', ['athlete_id'], ['id']),
    ('exercise_progression_tracking', 'exercise_progression_tracking_exercise_id_fkey', 'exercises', ['exercise_id'], ['id']),
    ('exercise_progression_tracking', 'exercise_progression_tracking_workout_session_id_fkey', 'ai_analysis.workout_sessions', ['workout_session_id'], ['id']),
    
    # ml_model_metadata references public.athletes
    ('ml_model_metadata', 'ml_model_metadata_athlete_id_fkey', 'athletes', ['athlete_id'], ['id']),
    
    # exercise_personal_records references public.athletes and public.exercises
    ('exercise_personal_records', 'exercise_personal_records_athlete_id_fk', 'athletes', ['athlete_id'], ['id']),
    ('exercise_personal_records', 'exercise_personal_records_exercise_id_fk', 'exercises', ['exercise_id'], ['id']),
    
    # form_quality_trends references public.athletes and public.exercises
    ('form_quality_trends', 'form_quality_trends_athlete_id_athletes_id_fk', 'athletes', ['athlete_id'], ['id']),
    ('form_quality_trends', 'form_quality_trends_exercise_id_exercises_id_fk', 'exercises', ['exercise_id'], ['id']),
]


def upgrade() -> None:
    # Create ai_analysis schema if it doesn't exist
    op.execute("CREATE SCHEMA IF NOT EXISTS ai_analysis")
    
    # Move all AI Engine tables to ai_analysis schema
    for table_name in AI_ENGINE_TABLES:
        op.execute(f'ALTER TABLE IF EXISTS "{table_name}" SET SCHEMA ai_analysis')
    
    # Drop existing foreign key constraints that need to be recreated with schema references
    for table_name, constraint_name, referenced_table, columns, referenced_columns in CROSS_SCHEMA_FOREIGN_KEYS:
        # Try to drop the constraint if it exists
        # Note: We need to handle different constraint name formats
        try:
            op.execute(f'ALTER TABLE ai_analysis."{table_name}" DROP CONSTRAINT IF EXISTS "{constraint_name}"')
        except:
            # Try alternative constraint names (PostgreSQL may auto-generate different names)
            pass
    
    # Recreate foreign key constraints with explicit schema references using raw SQL
    # Alembic's op.create_foreign_key doesn't support schema-qualified table names
    
    # plan_entries -> public.workout_plans
    op.execute("""
        ALTER TABLE ai_analysis.plan_entries
        ADD CONSTRAINT plan_entries_workout_plan_id_fkey
        FOREIGN KEY (workout_plan_id) REFERENCES public.workout_plans(id)
    """)
    
    # workout_sessions -> public.athletes and public.workout_days
    op.execute("""
        ALTER TABLE ai_analysis.workout_sessions
        ADD CONSTRAINT workout_sessions_athlete_id_fkey
        FOREIGN KEY (athlete_id) REFERENCES public.athletes(id)
    """)
    op.execute("""
        ALTER TABLE ai_analysis.workout_sessions
        ADD CONSTRAINT workout_sessions_workout_day_id_fkey
        FOREIGN KEY (workout_day_id) REFERENCES public.workout_days(id)
    """)
    
    # exercise_sets -> public.exercises and ai_analysis.workout_sessions
    op.execute("""
        ALTER TABLE ai_analysis.exercise_sets
        ADD CONSTRAINT exercise_sets_exercise_id_fkey
        FOREIGN KEY (exercise_id) REFERENCES public.exercises(id)
    """)
    op.execute("""
        ALTER TABLE ai_analysis.exercise_sets
        ADD CONSTRAINT exercise_sets_workout_session_id_fkey
        FOREIGN KEY (workout_session_id) REFERENCES ai_analysis.workout_sessions(id)
    """)
    
    # recovery_metrics -> public.athletes
    op.execute("""
        ALTER TABLE ai_analysis.recovery_metrics
        ADD CONSTRAINT recovery_metrics_athlete_id_fkey
        FOREIGN KEY (athlete_id) REFERENCES public.athletes(id)
    """)
    
    # athlete_rpe_calibration -> public.athletes and public.exercises
    op.execute("""
        ALTER TABLE ai_analysis.athlete_rpe_calibration
        ADD CONSTRAINT athlete_rpe_calibration_athlete_id_fkey
        FOREIGN KEY (athlete_id) REFERENCES public.athletes(id) ON DELETE CASCADE
    """)
    op.execute("""
        ALTER TABLE ai_analysis.athlete_rpe_calibration
        ADD CONSTRAINT athlete_rpe_calibration_exercise_id_fkey
        FOREIGN KEY (exercise_id) REFERENCES public.exercises(id) ON DELETE CASCADE
    """)
    
    # performance_trends -> public.athletes and ai_analysis.workout_sessions
    op.execute("""
        ALTER TABLE ai_analysis.performance_trends
        ADD CONSTRAINT performance_trends_athlete_id_fkey
        FOREIGN KEY (athlete_id) REFERENCES public.athletes(id) ON DELETE CASCADE
    """)
    op.execute("""
        ALTER TABLE ai_analysis.performance_trends
        ADD CONSTRAINT performance_trends_workout_session_id_fkey
        FOREIGN KEY (workout_session_id) REFERENCES ai_analysis.workout_sessions(id) ON DELETE CASCADE
    """)
    
    # exercise_progression_tracking -> public.athletes, public.exercises, and ai_analysis.workout_sessions
    op.execute("""
        ALTER TABLE ai_analysis.exercise_progression_tracking
        ADD CONSTRAINT exercise_progression_tracking_athlete_id_fkey
        FOREIGN KEY (athlete_id) REFERENCES public.athletes(id) ON DELETE CASCADE
    """)
    op.execute("""
        ALTER TABLE ai_analysis.exercise_progression_tracking
        ADD CONSTRAINT exercise_progression_tracking_exercise_id_fkey
        FOREIGN KEY (exercise_id) REFERENCES public.exercises(id) ON DELETE CASCADE
    """)
    op.execute("""
        ALTER TABLE ai_analysis.exercise_progression_tracking
        ADD CONSTRAINT exercise_progression_tracking_workout_session_id_fkey
        FOREIGN KEY (workout_session_id) REFERENCES ai_analysis.workout_sessions(id) ON DELETE CASCADE
    """)
    
    # ml_model_metadata -> public.athletes
    op.execute("""
        ALTER TABLE ai_analysis.ml_model_metadata
        ADD CONSTRAINT ml_model_metadata_athlete_id_fkey
        FOREIGN KEY (athlete_id) REFERENCES public.athletes(id) ON DELETE CASCADE
    """)
    
    # exercise_personal_records -> public.athletes and public.exercises
    op.execute("""
        ALTER TABLE ai_analysis.exercise_personal_records
        ADD CONSTRAINT exercise_personal_records_athlete_id_fk
        FOREIGN KEY (athlete_id) REFERENCES public.athletes(id) ON DELETE CASCADE
    """)
    op.execute("""
        ALTER TABLE ai_analysis.exercise_personal_records
        ADD CONSTRAINT exercise_personal_records_exercise_id_fk
        FOREIGN KEY (exercise_id) REFERENCES public.exercises(id) ON DELETE CASCADE
    """)
    
    # form_quality_trends -> public.athletes and public.exercises
    op.execute("""
        ALTER TABLE ai_analysis.form_quality_trends
        ADD CONSTRAINT form_quality_trends_athlete_id_athletes_id_fk
        FOREIGN KEY (athlete_id) REFERENCES public.athletes(id)
    """)
    op.execute("""
        ALTER TABLE ai_analysis.form_quality_trends
        ADD CONSTRAINT form_quality_trends_exercise_id_exercises_id_fk
        FOREIGN KEY (exercise_id) REFERENCES public.exercises(id)
    """)


def downgrade() -> None:
    # Drop foreign key constraints
    for table_name, constraint_name, _, _, _ in CROSS_SCHEMA_FOREIGN_KEYS:
        try:
            op.execute(f'ALTER TABLE ai_analysis."{table_name}" DROP CONSTRAINT IF EXISTS "{constraint_name}"')
        except:
            pass
    
    # Move all tables back to public schema
    for table_name in AI_ENGINE_TABLES:
        op.execute(f'ALTER TABLE IF EXISTS ai_analysis."{table_name}" SET SCHEMA public')
    
    # Recreate foreign key constraints without schema references (back to original)
    # Note: This is a simplified version - in practice, you'd need to restore the exact original constraints
    op.create_foreign_key(
        'plan_entries_workout_plan_id_fkey',
        'plan_entries', 'workout_plans',
        ['workout_plan_id'], ['id']
    )
    
    op.create_foreign_key(
        'workout_sessions_athlete_id_fkey',
        'workout_sessions', 'athletes',
        ['athlete_id'], ['id']
    )
    op.create_foreign_key(
        'workout_sessions_workout_day_id_fkey',
        'workout_sessions', 'workout_days',
        ['workout_day_id'], ['id']
    )
    
    op.create_foreign_key(
        'exercise_sets_exercise_id_fkey',
        'exercise_sets', 'exercises',
        ['exercise_id'], ['id']
    )
    op.create_foreign_key(
        'exercise_sets_workout_session_id_fkey',
        'exercise_sets', 'workout_sessions',
        ['workout_session_id'], ['id']
    )
    
    op.create_foreign_key(
        'recovery_metrics_athlete_id_fkey',
        'recovery_metrics', 'athletes',
        ['athlete_id'], ['id']
    )
    
    op.create_foreign_key(
        'athlete_rpe_calibration_athlete_id_fkey',
        'athlete_rpe_calibration', 'athletes',
        ['athlete_id'], ['id'],
        ondelete='CASCADE'
    )
    op.create_foreign_key(
        'athlete_rpe_calibration_exercise_id_fkey',
        'athlete_rpe_calibration', 'exercises',
        ['exercise_id'], ['id'],
        ondelete='CASCADE'
    )
    
    op.create_foreign_key(
        'performance_trends_athlete_id_fkey',
        'performance_trends', 'athletes',
        ['athlete_id'], ['id'],
        ondelete='CASCADE'
    )
    op.create_foreign_key(
        'performance_trends_workout_session_id_fkey',
        'performance_trends', 'workout_sessions',
        ['workout_session_id'], ['id'],
        ondelete='CASCADE'
    )
    
    op.create_foreign_key(
        'exercise_progression_tracking_athlete_id_fkey',
        'exercise_progression_tracking', 'athletes',
        ['athlete_id'], ['id'],
        ondelete='CASCADE'
    )
    op.create_foreign_key(
        'exercise_progression_tracking_exercise_id_fkey',
        'exercise_progression_tracking', 'exercises',
        ['exercise_id'], ['id'],
        ondelete='CASCADE'
    )
    op.create_foreign_key(
        'exercise_progression_tracking_workout_session_id_fkey',
        'exercise_progression_tracking', 'workout_sessions',
        ['workout_session_id'], ['id'],
        ondelete='CASCADE'
    )
    
    op.create_foreign_key(
        'ml_model_metadata_athlete_id_fkey',
        'ml_model_metadata', 'athletes',
        ['athlete_id'], ['id'],
        ondelete='CASCADE'
    )
    
    op.create_foreign_key(
        'exercise_personal_records_athlete_id_fk',
        'exercise_personal_records', 'athletes',
        ['athlete_id'], ['id'],
        ondelete='CASCADE'
    )
    op.create_foreign_key(
        'exercise_personal_records_exercise_id_fk',
        'exercise_personal_records', 'exercises',
        ['exercise_id'], ['id'],
        ondelete='CASCADE'
    )
    
    op.create_foreign_key(
        'form_quality_trends_athlete_id_athletes_id_fk',
        'form_quality_trends', 'athletes',
        ['athlete_id'], ['id']
    )
    op.create_foreign_key(
        'form_quality_trends_exercise_id_exercises_id_fk',
        'form_quality_trends', 'exercises',
        ['exercise_id'], ['id']
    )
    
    # Drop ai_analysis schema (only if empty)
    op.execute("DROP SCHEMA IF EXISTS ai_analysis")

