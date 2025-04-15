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
    # Skip creating the trade table as it already exists
    
    # Add trade_id column to labor_activity table if it doesn't exist
    try:
        op.add_column('labor_activity', 
            sa.Column('trade_id', sa.Integer(), nullable=True)
        )
    except Exception as e:
        print(f"Column may already exist: {e}")
    
    # Add is_active column to labor_activity table if it doesn't exist
    try:
        op.add_column('labor_activity',
            sa.Column('is_active', sa.Boolean(), nullable=True, server_default=sa.text('true'))
        )
    except Exception as e:
        print(f"Column may already exist: {e}")
    
    # Create a foreign key from labor_activity.trade_id to trade.id if it doesn't exist
    try:
        op.create_foreign_key(
            'fk_labor_activity_trade',
            'labor_activity', 'trade',
            ['trade_id'], ['id']
        )
    except Exception as e:
        print(f"Foreign key may already exist: {e}")


def downgrade():
    # Remove the foreign key if it exists
    try:
        op.drop_constraint('fk_labor_activity_trade', 'labor_activity', type_='foreignkey')
    except Exception as e:
        print(f"Foreign key may not exist: {e}")
    
    # Remove the columns from labor_activity if they exist
    try:
        op.drop_column('labor_activity', 'trade_id')
    except Exception as e:
        print(f"Column may not exist: {e}")
        
    try:
        op.drop_column('labor_activity', 'is_active')
    except Exception as e:
        print(f"Column may not exist: {e}")
        
    # Don't drop the trade table as it was not created by this migration