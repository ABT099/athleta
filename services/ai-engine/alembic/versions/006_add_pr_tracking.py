"""Add PR tracking

Revision ID: 006
Revises: 005
Create Date: 2025-01-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create exercise_personal_records table
    op.create_table(
        'exercise_personal_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('athlete_id', sa.Integer(), nullable=False),
        sa.Column('exercise_id', sa.Integer(), nullable=False),
        
        # Rep-max PRs
        sa.Column('one_rep_max', sa.Float(), nullable=True),
        sa.Column('one_rm_date', sa.DateTime(), nullable=True),
        sa.Column('three_rep_max', sa.Float(), nullable=True),
        sa.Column('three_rm_date', sa.DateTime(), nullable=True),
        sa.Column('five_rep_max', sa.Float(), nullable=True),
        sa.Column('five_rm_date', sa.DateTime(), nullable=True),
        sa.Column('eight_rep_max', sa.Float(), nullable=True),
        sa.Column('eight_rm_date', sa.DateTime(), nullable=True),
        sa.Column('ten_rep_max', sa.Float(), nullable=True),
        sa.Column('ten_rm_date', sa.DateTime(), nullable=True),
        sa.Column('twelve_rep_max', sa.Float(), nullable=True),
        sa.Column('twelve_rm_date', sa.DateTime(), nullable=True),
        
        # Volume PRs
        sa.Column('max_volume_session', sa.Float(), nullable=True),
        sa.Column('max_volume_date', sa.DateTime(), nullable=True),
        sa.Column('max_total_reps', sa.Integer(), nullable=True),
        sa.Column('max_reps_date', sa.DateTime(), nullable=True),
        
        # Metadata
        sa.Column('total_pr_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_pr_date', sa.DateTime(), nullable=True),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('athlete_id', 'exercise_id', name='uq_athlete_exercise_pr')
    )
    
    # Add foreign keys
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
    
    # Add indexes
    op.create_index('idx_exercise_personal_records_athlete_id', 'exercise_personal_records', ['athlete_id'])
    op.create_index('idx_exercise_personal_records_exercise_id', 'exercise_personal_records', ['exercise_id'])


def downgrade() -> None:
    op.drop_index('idx_exercise_personal_records_exercise_id', table_name='exercise_personal_records')
    op.drop_index('idx_exercise_personal_records_athlete_id', table_name='exercise_personal_records')
    op.drop_table('exercise_personal_records')

