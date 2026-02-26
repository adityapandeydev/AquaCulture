"""add is_processed column to sensor_data_raw table

Revision ID: 827b962f98f2
Revises: 9bba9e60ff1c
Create Date: 2026-02-26 09:29:11.580974

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '827b962f98f2'
down_revision: Union[str, Sequence[str], None] = '9bba9e60ff1c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sensor_data_raw",
        sa.Column(
            "is_processed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false")
        )
    )

    # Optional: remove server default after backfilling
    op.alter_column(
        "sensor_data_raw",
        "is_processed",
        server_default=None
    )


def downgrade() -> None:
    op.drop_column("sensor_data_raw", "is_processed")
