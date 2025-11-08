"""ML infrastructure

Revision ID: 004
Revises: 003
Create Date: 2025-11-08 01:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create ml_model_metadata table
    op.create_table('ml_model_metadata',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('model_name', sa.String(255), nullable=False),
        sa.Column('model_type', sa.String(100), nullable=False),
        sa.Column('athlete_id', sa.Integer(), nullable=True),
        sa.Column('version', sa.String(50), nullable=False),
        sa.Column('training_date', sa.DateTime(), nullable=False),
        sa.Column('training_samples', sa.Integer(), nullable=False),
        sa.Column('feature_count', sa.Integer(), nullable=False),
        sa.Column('target_count', sa.Integer(), nullable=False),
        sa.Column('model_path', sa.Text(), nullable=False),
        sa.Column('performance_metrics', sa.Text(), nullable=True),
        sa.Column('feature_importance', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['athlete_id'], ['athletes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ml_model_metadata_athlete_id'), 'ml_model_metadata', ['athlete_id'], unique=False)
    op.create_index(op.f('ix_ml_model_metadata_id'), 'ml_model_metadata', ['id'], unique=False)
    op.create_index(op.f('ix_ml_model_metadata_model_name'), 'ml_model_metadata', ['model_name'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_ml_model_metadata_model_name'), table_name='ml_model_metadata')
    op.drop_index(op.f('ix_ml_model_metadata_id'), table_name='ml_model_metadata')
    op.drop_index(op.f('ix_ml_model_metadata_athlete_id'), table_name='ml_model_metadata')
    op.drop_table('ml_model_metadata')

