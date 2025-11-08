"""Advanced training features

Revision ID: 003
Revises: 001
Create Date: 2025-11-08 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '003'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new fields to athletes table
    op.add_column('athletes', sa.Column('rpe_calibration_factor', sa.Float(), nullable=False, server_default='1.0'))
    
    # Add new fields to exercises table
    op.add_column('exercises', sa.Column('exercise_type', sa.String(50), nullable=False, server_default='compound'))
    op.add_column('exercises', sa.Column('complexity_score', sa.Float(), nullable=False, server_default='1.0'))
    
    # Create athlete_rpe_calibration table
    op.create_table('athlete_rpe_calibration',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('athlete_id', sa.Integer(), nullable=False),
        sa.Column('exercise_id', sa.Integer(), nullable=False),
        sa.Column('reported_rpe', sa.Float(), nullable=False),
        sa.Column('predicted_rir', sa.Float(), nullable=False),
        sa.Column('actual_rir', sa.Float(), nullable=True),
        sa.Column('weight_used', sa.Float(), nullable=False),
        sa.Column('reps_completed', sa.Integer(), nullable=False),
        sa.Column('session_date', sa.DateTime(), nullable=False),
        sa.Column('calibration_accuracy', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['athlete_id'], ['athletes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['exercise_id'], ['exercises.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_athlete_rpe_calibration_athlete_id'), 'athlete_rpe_calibration', ['athlete_id'], unique=False)
    op.create_index(op.f('ix_athlete_rpe_calibration_id'), 'athlete_rpe_calibration', ['id'], unique=False)
    
    # Create performance_trends table
    op.create_table('performance_trends',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('athlete_id', sa.Integer(), nullable=False),
        sa.Column('workout_session_id', sa.Integer(), nullable=False),
        sa.Column('session_date', sa.DateTime(), nullable=False),
        sa.Column('total_volume', sa.Float(), nullable=False),
        sa.Column('average_intensity', sa.Float(), nullable=False),
        sa.Column('average_rpe', sa.Float(), nullable=False),
        sa.Column('readiness_score', sa.Float(), nullable=False),
        sa.Column('performance_score', sa.Float(), nullable=False),
        sa.Column('fatigue_index', sa.Float(), nullable=False),
        sa.Column('volume_load', sa.Float(), nullable=False),
        sa.Column('training_monotony', sa.Float(), nullable=True),
        sa.Column('training_strain', sa.Float(), nullable=True),
        sa.Column('acute_load', sa.Float(), nullable=True),
        sa.Column('chronic_load', sa.Float(), nullable=True),
        sa.Column('acwr', sa.Float(), nullable=True),
        sa.Column('deload_triggered', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('deload_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['athlete_id'], ['athletes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['workout_session_id'], ['workout_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_performance_trends_athlete_id'), 'performance_trends', ['athlete_id'], unique=False)
    op.create_index(op.f('ix_performance_trends_id'), 'performance_trends', ['id'], unique=False)
    op.create_index(op.f('ix_performance_trends_session_date'), 'performance_trends', ['session_date'], unique=False)
    
    # Create exercise_progression_tracking table
    op.create_table('exercise_progression_tracking',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('athlete_id', sa.Integer(), nullable=False),
        sa.Column('exercise_id', sa.Integer(), nullable=False),
        sa.Column('workout_session_id', sa.Integer(), nullable=False),
        sa.Column('session_date', sa.DateTime(), nullable=False),
        sa.Column('weight_used', sa.Float(), nullable=False),
        sa.Column('total_reps', sa.Integer(), nullable=False),
        sa.Column('total_sets', sa.Integer(), nullable=False),
        sa.Column('average_rpe', sa.Float(), nullable=False),
        sa.Column('estimated_1rm', sa.Float(), nullable=False),
        sa.Column('volume_load', sa.Float(), nullable=False),
        sa.Column('progression_state', sa.String(50), nullable=False),
        sa.Column('weeks_at_weight', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('sessions_at_weight', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('rep_progression_target', sa.Integer(), nullable=True),
        sa.Column('weight_progression_ready', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('familiarity_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['athlete_id'], ['athletes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['exercise_id'], ['exercises.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['workout_session_id'], ['workout_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_exercise_progression_tracking_athlete_id'), 'exercise_progression_tracking', ['athlete_id'], unique=False)
    op.create_index(op.f('ix_exercise_progression_tracking_exercise_id'), 'exercise_progression_tracking', ['exercise_id'], unique=False)
    op.create_index(op.f('ix_exercise_progression_tracking_id'), 'exercise_progression_tracking', ['id'], unique=False)


def downgrade() -> None:
    # Drop new tables
    op.drop_index(op.f('ix_exercise_progression_tracking_id'), table_name='exercise_progression_tracking')
    op.drop_index(op.f('ix_exercise_progression_tracking_exercise_id'), table_name='exercise_progression_tracking')
    op.drop_index(op.f('ix_exercise_progression_tracking_athlete_id'), table_name='exercise_progression_tracking')
    op.drop_table('exercise_progression_tracking')
    
    op.drop_index(op.f('ix_performance_trends_session_date'), table_name='performance_trends')
    op.drop_index(op.f('ix_performance_trends_id'), table_name='performance_trends')
    op.drop_index(op.f('ix_performance_trends_athlete_id'), table_name='performance_trends')
    op.drop_table('performance_trends')
    
    op.drop_index(op.f('ix_athlete_rpe_calibration_id'), table_name='athlete_rpe_calibration')
    op.drop_index(op.f('ix_athlete_rpe_calibration_athlete_id'), table_name='athlete_rpe_calibration')
    op.drop_table('athlete_rpe_calibration')
    
    # Remove columns from exercises table
    op.drop_column('exercises', 'complexity_score')
    op.drop_column('exercises', 'exercise_type')
    
    # Remove column from athletes table
    op.drop_column('athletes', 'rpe_calibration_factor')

