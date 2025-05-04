"""add_distance_in_miles

Revision ID: add_distance_in_miles
Revises: add_unique_active_clock_session
Create Date: 2025-05-04 20:57:30.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text


# revision identifiers, used by Alembic.
revision = 'add_distance_in_miles'
down_revision = 'add_unique_active_clock_session'
branch_labels = None
depends_on = None


def upgrade():
    # Add new columns for distance in miles
    op.add_column('clock_session', sa.Column('clock_in_distance_mi', sa.Float(), nullable=True))
    op.add_column('clock_session', sa.Column('clock_out_distance_mi', sa.Float(), nullable=True))
    
    # Convert existing data from meters to miles (1 meter = 0.000621371 miles)
    # We're rounding to 2 decimal places as required
    conn = op.get_bind()
    
    # Update clock_in_distance_mi based on existing clock_in_distance_m values
    conn.execute(text("""
        UPDATE clock_session 
        SET clock_in_distance_mi = ROUND(clock_in_distance_m / 1609.34, 2) 
        WHERE clock_in_distance_m IS NOT NULL
    """))
    
    # Update clock_out_distance_mi based on existing clock_out_distance_m values
    conn.execute(text("""
        UPDATE clock_session 
        SET clock_out_distance_mi = ROUND(clock_out_distance_m / 1609.34, 2) 
        WHERE clock_out_distance_m IS NOT NULL
    """))


def downgrade():
    # Remove new columns
    op.drop_column('clock_session', 'clock_in_distance_mi')
    op.drop_column('clock_session', 'clock_out_distance_mi')