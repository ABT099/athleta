"""Schema cleanup and form quality tracking

Revision ID: 005
Revises: 004
Create Date: 2025-01-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Helper function to check if column exists before dropping
    def column_exists(table_name, column_name):
        bind = op.get_bind()
        inspector = inspect(bind)
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    
    # Drop unused columns from recovery_metrics (only if they exist)
    if column_exists('recovery_metrics', 'hrv'):
        op.drop_column('recovery_metrics', 'hrv')
    if column_exists('recovery_metrics', 'resting_heart_rate'):
        op.drop_column('recovery_metrics', 'resting_heart_rate')
    
    # Drop unused column from exercise_sets (only if it exists)
    if column_exists('exercise_sets', 'tempo_adherence'):
        op.drop_column('exercise_sets', 'tempo_adherence')
    
    # Create form_quality_trends table (only if it doesn't exist)
    # Note: Drizzle may have already created this table, so check first
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = inspector.get_table_names()
    
    if 'form_quality_trends' not in tables:
        op.create_table('form_quality_trends',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('athlete_id', sa.Integer(), nullable=False),
            sa.Column('exercise_id', sa.Integer(), nullable=False),
            sa.Column('date', sa.DateTime(), nullable=False),
            sa.Column('average_form_score', sa.Float(), nullable=False),  # 1.0=excellent, 0.75=good, 0.5=fair, 0.25=poor
            sa.Column('sets_analyzed', sa.Integer(), nullable=False),
            sa.Column('degradation_rate', sa.Float(), nullable=True),  # Form drop across sets in session
            sa.Column('high_rpe_poor_form_count', sa.Integer(), nullable=False, server_default='0'),
            sa.ForeignKeyConstraint(['athlete_id'], ['athletes.id'], ),
            sa.ForeignKeyConstraint(['exercise_id'], ['exercises.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
    
    # Create indexes (check if they exist first to avoid errors)
    def index_exists(table_name, index_name):
        indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
        return index_name in indexes
    
    if not index_exists('form_quality_trends', 'ix_form_quality_trends_id'):
        op.create_index(op.f('ix_form_quality_trends_id'), 'form_quality_trends', ['id'], unique=False)
    if not index_exists('form_quality_trends', 'ix_form_quality_trends_athlete_exercise_date'):
        op.create_index('ix_form_quality_trends_athlete_exercise_date', 'form_quality_trends', ['athlete_id', 'exercise_id', 'date'], unique=False)


def downgrade() -> None:
    # Drop form_quality_trends table
    op.drop_index('ix_form_quality_trends_athlete_exercise_date', table_name='form_quality_trends')
    op.drop_index(op.f('ix_form_quality_trends_id'), table_name='form_quality_trends')
    op.drop_table('form_quality_trends')
    
    # Restore dropped columns
    op.add_column('exercises', sa.Column('is_compound', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('exercise_sets', sa.Column('tempo_adherence', sa.String(length=50), nullable=True))
    op.add_column('recovery_metrics', sa.Column('resting_heart_rate', sa.Integer(), nullable=True))
    op.add_column('recovery_metrics', sa.Column('hrv', sa.Float(), nullable=True))



