"""Initial migration

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create plan_entries table
    op.create_table('plan_entries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('workout_plan_id', sa.Integer(), nullable=False),
        sa.Column('week_number', sa.Integer(), nullable=False),
        sa.Column('start_date', sa.DateTime(), nullable=False),
        sa.Column('end_date', sa.DateTime(), nullable=False),
        sa.Column('training_phase', sa.Enum('accumulation', 'intensification', 'realization', name='trainingphase'), nullable=False),
        sa.Column('target_volume_multiplier', sa.Float(), nullable=False),
        sa.Column('target_intensity_multiplier', sa.Float(), nullable=False),
        sa.Column('is_deload_week', sa.Integer(), nullable=False),
        sa.Column('ai_adjustments', sa.JSON(), nullable=True),
        sa.Column('completed_workouts', sa.Integer(), nullable=False),
        sa.Column('average_rpe', sa.Float(), nullable=True),
        sa.Column('average_recovery_score', sa.Float(), nullable=True),
        sa.Column('total_volume', sa.Float(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['workout_plan_id'], ['workout_plans.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_plan_entries_id'), 'plan_entries', ['id'], unique=False)
    
    # Create workout_sessions table
    op.create_table('workout_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('athlete_id', sa.Integer(), nullable=False),
        sa.Column('workout_day_id', sa.Integer(), nullable=False),
        sa.Column('session_date', sa.DateTime(), nullable=False),
        sa.Column('duration_minutes', sa.Integer(), nullable=True),
        sa.Column('overall_rpe', sa.Float(), nullable=True),
        sa.Column('overall_feeling', sa.String(length=50), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('total_volume', sa.Float(), nullable=True),
        sa.Column('estimated_fatigue', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['athlete_id'], ['athletes.id'], ),
        sa.ForeignKeyConstraint(['workout_day_id'], ['workout_days.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_workout_sessions_id'), 'workout_sessions', ['id'], unique=False)
    
    # Create exercise_sets table
    op.create_table('exercise_sets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('workout_session_id', sa.Integer(), nullable=False),
        sa.Column('exercise_id', sa.Integer(), nullable=False),
        sa.Column('set_number', sa.Integer(), nullable=False),
        sa.Column('weight', sa.Float(), nullable=False),
        sa.Column('reps', sa.Integer(), nullable=False),
        sa.Column('rpe', sa.Float(), nullable=True),
        sa.Column('rir', sa.Integer(), nullable=True),
        sa.Column('form_quality', sa.String(length=50), nullable=True),
        sa.Column('tempo_adherence', sa.String(length=50), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['exercise_id'], ['exercises.id'], ),
        sa.ForeignKeyConstraint(['workout_session_id'], ['workout_sessions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_exercise_sets_id'), 'exercise_sets', ['id'], unique=False)
    
    # Create recovery_metrics table
    op.create_table('recovery_metrics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('athlete_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.DateTime(), nullable=False),
        sa.Column('sleep_quality', sa.Enum('poor', 'not_bad', 'good', 'excellent', name='sleepquality'), nullable=False),
        sa.Column('sleep_hours', sa.Float(), nullable=True),
        sa.Column('overall_soreness', sa.Integer(), nullable=True),
        sa.Column('muscle_soreness', sa.Text(), nullable=True),
        sa.Column('stress_level', sa.Integer(), nullable=True),
        sa.Column('energy_level', sa.Integer(), nullable=True),
        sa.Column('readiness_score', sa.Float(), nullable=True),
        sa.Column('hrv', sa.Float(), nullable=True),
        sa.Column('resting_heart_rate', sa.Integer(), nullable=True),
        sa.Column('nutrition_adherence', sa.String(length=50), nullable=True),
        sa.Column('hydration_level', sa.String(length=50), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['athlete_id'], ['athletes.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_recovery_metrics_date'), 'recovery_metrics', ['date'], unique=False)
    op.create_index(op.f('ix_recovery_metrics_id'), 'recovery_metrics', ['id'], unique=False)


def downgrade() -> None:
    # Drop AI engine tables only (NestJS tables are managed by NestJS migrations)
    op.drop_index(op.f('ix_recovery_metrics_id'), table_name='recovery_metrics')
    op.drop_index(op.f('ix_recovery_metrics_date'), table_name='recovery_metrics')
    op.drop_table('recovery_metrics')
    op.drop_index(op.f('ix_exercise_sets_id'), table_name='exercise_sets')
    op.drop_table('exercise_sets')
    op.drop_index(op.f('ix_workout_sessions_id'), table_name='workout_sessions')
    op.drop_table('workout_sessions')
    op.drop_index(op.f('ix_plan_entries_id'), table_name='plan_entries')
    op.drop_table('plan_entries')

