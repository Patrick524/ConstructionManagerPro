"""add trade model and relationships

Revision ID: trade_model_migration
Revises: 
Create Date: 2025-04-15 19:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'trade_model_migration'
down_revision = '148b8b2ae5bb'  # Points to the add_location_field_to_jobs_table migration
branch_labels = None
depends_on = None


def upgrade():
    # Create the trade table
    op.create_table('trade',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    
    # Add trade_id column to labor_activity table
    op.add_column('labor_activity', 
        sa.Column('trade_id', sa.Integer(), nullable=True)
    )
    
    # Add is_active column to labor_activity table if it doesn't exist
    op.add_column('labor_activity',
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default=sa.text('true'))
    )
    
    # Create a foreign key from labor_activity.trade_id to trade.id
    op.create_foreign_key(
        'fk_labor_activity_trade',
        'labor_activity', 'trade',
        ['trade_id'], ['id']
    )


def downgrade():
    # Remove the foreign key
    op.drop_constraint('fk_labor_activity_trade', 'labor_activity', type_='foreignkey')
    
    # Remove the columns from labor_activity
    op.drop_column('labor_activity', 'trade_id')
    op.drop_column('labor_activity', 'is_active')
    
    # Drop the trade table
    op.drop_table('trade')