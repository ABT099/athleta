"""Add intensity techniques

Revision ID: 007
Revises: 006
Create Date: 2025-01-21 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum types for set_type and rep_style
    op.execute("""
        CREATE TYPE set_type_enum AS ENUM (
            'straight', 'drop_set', 'rest_pause', 'myo_reps', 
            'cluster_set', 'superset_antagonist', 'pre_exhaust'
        )
    """)
    
    op.execute("""
        CREATE TYPE rep_style_enum AS ENUM (
            'normal', 'lengthened_partials', 'tempo_eccentric', 
            'tempo_paused', 'eccentric_overload'
        )
    """)
    
    # Add intensity technique fields to workout_day_exercises
    op.add_column(
        'workout_day_exercises',
        sa.Column('set_type', sa.Enum('straight', 'drop_set', 'rest_pause', 'myo_reps', 'cluster_set', 'superset_antagonist', 'pre_exhaust', name='set_type_enum'), nullable=False, server_default='straight')
    )
    op.add_column(
        'workout_day_exercises',
        sa.Column('rep_style', sa.Enum('normal', 'lengthened_partials', 'tempo_eccentric', 'tempo_paused', 'eccentric_overload', name='rep_style_enum'), nullable=False, server_default='normal')
    )
    op.add_column(
        'workout_day_exercises',
        sa.Column('set_type_params', postgresql.JSON(astext_type=sa.Text()), nullable=True)
    )
    op.add_column(
        'workout_day_exercises',
        sa.Column('rep_style_params', postgresql.JSON(astext_type=sa.Text()), nullable=True)
    )
    
    # Add intensity technique tracking fields to exercise_sets
    op.add_column(
        'exercise_sets',
        sa.Column('set_type_used', sa.Enum('straight', 'drop_set', 'rest_pause', 'myo_reps', 'cluster_set', 'superset_antagonist', 'pre_exhaust', name='set_type_enum'), nullable=True)
    )
    op.add_column(
        'exercise_sets',
        sa.Column('rep_style_used', sa.Enum('normal', 'lengthened_partials', 'tempo_eccentric', 'tempo_paused', 'eccentric_overload', name='rep_style_enum'), nullable=True)
    )
    op.add_column(
        'exercise_sets',
        sa.Column('technique_details', postgresql.JSON(astext_type=sa.Text()), nullable=True)
    )


def downgrade() -> None:
    # Remove columns from exercise_sets
    op.drop_column('exercise_sets', 'technique_details')
    op.drop_column('exercise_sets', 'rep_style_used')
    op.drop_column('exercise_sets', 'set_type_used')
    
    # Remove columns from workout_day_exercises
    op.drop_column('workout_day_exercises', 'rep_style_params')
    op.drop_column('workout_day_exercises', 'set_type_params')
    op.drop_column('workout_day_exercises', 'rep_style')
    op.drop_column('workout_day_exercises', 'set_type')
    
    # Drop enum types
    op.execute('DROP TYPE IF EXISTS rep_style_enum')
    op.execute('DROP TYPE IF EXISTS set_type_enum')

