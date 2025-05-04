"""Add unique constraint for one active clock session per user

Revision ID: add_unique_active_clock_session
Revises: add_location_tracking_fields
Create Date: 2025-05-04 20:35:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_unique_active_clock_session'
down_revision = 'add_location_tracking_fields'
branch_labels = None
depends_on = None


def upgrade():
    # Create a partial unique index on user_id for active clock sessions
    # This enforces the constraint that a user can have only one active clock session at a time
    op.execute(
        """
        CREATE UNIQUE INDEX ux_clock_session_one_active_per_user 
        ON clock_session (user_id) 
        WHERE clock_out IS NULL AND is_active = TRUE
        """
    )


def downgrade():
    # Drop the partial unique index
    op.execute("DROP INDEX IF EXISTS ux_clock_session_one_active_per_user")