"""Add feeding, diaper, sleep, and mood entry tables.

Revision ID: 002_add_tracking_entries
Revises: 001_initial
Create Date: 2026-03-13 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '002_add_tracking_entries'
down_revision = '001_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create feeding_entries, diaper_entries, sleep_entries, mood_entries tables."""
    
    # Create feeding_entries table
    op.create_table(
        'feeding_entries',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('baby_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('feeding_type', sa.String(50), nullable=False),
        sa.Column('amount_ml', sa.Integer(), nullable=True),
        sa.Column('duration_min', sa.Integer(), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['baby_id'], ['babies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_feeding_entries_baby_id', 'feeding_entries', ['baby_id'])
    op.create_index('ix_feeding_entries_baby_id_timestamp', 'feeding_entries', ['baby_id', 'timestamp'])
    op.create_index('ix_feeding_entries_timestamp', 'feeding_entries', ['timestamp'])
    
    # Create diaper_entries table
    op.create_table(
        'diaper_entries',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('baby_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('diaper_type', sa.String(50), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['baby_id'], ['babies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_diaper_entries_baby_id', 'diaper_entries', ['baby_id'])
    op.create_index('ix_diaper_entries_baby_id_timestamp', 'diaper_entries', ['baby_id', 'timestamp'])
    op.create_index('ix_diaper_entries_timestamp', 'diaper_entries', ['timestamp'])
    
    # Create sleep_entries table
    op.create_table(
        'sleep_entries',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('baby_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('start_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_min', sa.Integer(), nullable=True),
        sa.Column('quality', sa.String(50), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['baby_id'], ['babies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_sleep_entries_baby_id', 'sleep_entries', ['baby_id'])
    op.create_index('ix_sleep_entries_baby_id_start_time', 'sleep_entries', ['baby_id', 'start_time'])
    op.create_index('ix_sleep_entries_start_time', 'sleep_entries', ['start_time'])
    
    # Create mood_entries table
    op.create_table(
        'mood_entries',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('baby_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('mood', sa.String(50), nullable=False),
        sa.Column('energy', sa.String(50), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['baby_id'], ['babies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_mood_entries_baby_id', 'mood_entries', ['baby_id'])
    op.create_index('ix_mood_entries_baby_id_timestamp', 'mood_entries', ['baby_id', 'timestamp'])
    op.create_index('ix_mood_entries_timestamp', 'mood_entries', ['timestamp'])


def downgrade() -> None:
    """Drop all tracking entry tables."""
    op.drop_index('ix_mood_entries_timestamp', table_name='mood_entries')
    op.drop_index('ix_mood_entries_baby_id_timestamp', table_name='mood_entries')
    op.drop_index('ix_mood_entries_baby_id', table_name='mood_entries')
    op.drop_table('mood_entries')
    
    op.drop_index('ix_sleep_entries_start_time', table_name='sleep_entries')
    op.drop_index('ix_sleep_entries_baby_id_start_time', table_name='sleep_entries')
    op.drop_index('ix_sleep_entries_baby_id', table_name='sleep_entries')
    op.drop_table('sleep_entries')
    
    op.drop_index('ix_diaper_entries_timestamp', table_name='diaper_entries')
    op.drop_index('ix_diaper_entries_baby_id_timestamp', table_name='diaper_entries')
    op.drop_index('ix_diaper_entries_baby_id', table_name='diaper_entries')
    op.drop_table('diaper_entries')
    
    op.drop_index('ix_feeding_entries_timestamp', table_name='feeding_entries')
    op.drop_index('ix_feeding_entries_baby_id_timestamp', table_name='feeding_entries')
    op.drop_index('ix_feeding_entries_baby_id', table_name='feeding_entries')
    op.drop_table('feeding_entries')
