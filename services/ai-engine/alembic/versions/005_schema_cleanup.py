"""Schema cleanup and form quality tracking

Revision ID: 005
Revises: 004
Create Date: 2025-01-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop unused columns from recovery_metrics
    op.drop_column('recovery_metrics', 'hrv')
    op.drop_column('recovery_metrics', 'resting_heart_rate')
    
    # Drop unused column from exercise_sets
    op.drop_column('exercise_sets', 'tempo_adherence')
    
    # Drop redundant column from exercises
    op.drop_column('exercises', 'is_compound')
    
    # Create form_quality_trends table
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
    op.create_index(op.f('ix_form_quality_trends_id'), 'form_quality_trends', ['id'], unique=False)
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



