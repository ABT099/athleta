"""add workout prescription history

Revision ID: 009_prescription_history
Revises: 008_schema_separation
Create Date: 2025-12-14

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '009'
down_revision = '008'
branch_labels = None
depends_on = None


def upgrade():
    """Add workout_prescription_history table."""
    op.create_table(
        'workout_prescription_history',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('athlete_id', sa.Integer(), sa.ForeignKey('public.athletes.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('workout_day_id', sa.Integer(), sa.ForeignKey('public.workout_days.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('exercise_id', sa.Integer(), sa.ForeignKey('public.exercises.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('prescribed_date', sa.DateTime(), nullable=False, index=True),
        
        # What AI prescribed
        sa.Column('prescribed_weight', sa.Float(), nullable=True),
        sa.Column('prescribed_sets', sa.Integer(), nullable=True),
        sa.Column('prescribed_reps_min', sa.Integer(), nullable=True),
        sa.Column('prescribed_reps_max', sa.Integer(), nullable=True),
        sa.Column('prescribed_rpe', sa.Float(), nullable=True),
        sa.Column('prescribed_rir', sa.Integer(), nullable=True),
        sa.Column('rest_period_seconds', sa.Integer(), nullable=True),
        
        # Intensity techniques
        sa.Column('set_type', sa.String(50), nullable=True),
        sa.Column('rep_style', sa.String(50), nullable=True),
        sa.Column('set_type_params', postgresql.JSONB(), nullable=True),
        sa.Column('rep_style_params', postgresql.JSONB(), nullable=True),
        
        # Why it was prescribed (AI context)
        sa.Column('volume_multiplier', sa.Float(), nullable=False),
        sa.Column('intensity_multiplier', sa.Float(), nullable=False),
        sa.Column('adjustment_reason', sa.Text(), nullable=True),
        
        # Context when prescribed
        sa.Column('week_number', sa.Integer(), nullable=True),
        sa.Column('readiness_score', sa.Float(), nullable=True),
        sa.Column('training_phase', sa.String(50), nullable=True),
        
        # Metadata
        sa.Column('created_at', sa.DateTime(), nullable=False),
        
        schema='ai_analysis'
    )
    
    # Create composite index for fast lookups
    op.create_index(
        'idx_athlete_workout_exercise_date',
        'workout_prescription_history',
        ['athlete_id', 'workout_day_id', 'exercise_id', 'prescribed_date'],
        schema='ai_analysis'
    )
    
    # Create index for per-exercise history
    op.create_index(
        'idx_athlete_exercise',
        'workout_prescription_history',
        ['athlete_id', 'exercise_id'],
        schema='ai_analysis'
    )


def downgrade():
    """Drop workout_prescription_history table."""
    op.drop_index('idx_athlete_exercise', table_name='workout_prescription_history', schema='ai_analysis')
    op.drop_index('idx_athlete_workout_exercise_date', table_name='workout_prescription_history', schema='ai_analysis')
    op.drop_table('workout_prescription_history', schema='ai_analysis')

