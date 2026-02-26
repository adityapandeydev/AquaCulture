"""drop manganese column from raw and clean tables

Revision ID: 9bba9e60ff1c
Revises: d3439c9f497c
Create Date: 2026-02-26 08:13:00.563520

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9bba9e60ff1c'
down_revision: Union[str, Sequence[str], None] = 'd3439c9f497c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop manganese column from raw table
    op.drop_column("sensor_data_raw", "manganese")

    # Drop manganese column from clean table
    op.drop_column("sensor_data_clean", "manganese")


def downgrade() -> None:
    # Re-add manganese column to raw table
    op.add_column(
        "sensor_data_raw",
        sa.Column("manganese", sa.Float(), nullable=True)
    )

    # Re-add manganese column to clean table
    op.add_column(
        "sensor_data_clean",
        sa.Column("manganese", sa.Float(), nullable=True)
    )
