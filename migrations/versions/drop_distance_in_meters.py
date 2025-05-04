"""drop_distance_in_meters

Revision ID: drop_distance_in_meters
Revises: add_distance_in_miles
Create Date: 2025-05-04 20:57:45.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'drop_distance_in_meters'
down_revision = 'add_distance_in_miles'
branch_labels = None
depends_on = None


def upgrade():
    # Drop old columns for distances in meters
    op.drop_column('clock_session', 'clock_in_distance_m')
    op.drop_column('clock_session', 'clock_out_distance_m')


def downgrade():
    # Add back the columns if needed
    op.add_column('clock_session', sa.Column('clock_in_distance_m', sa.Float(), nullable=True))
    op.add_column('clock_session', sa.Column('clock_out_distance_m', sa.Float(), nullable=True))
    
    # Note: data would be lost in a downgrade since we don't convert back from miles to meters