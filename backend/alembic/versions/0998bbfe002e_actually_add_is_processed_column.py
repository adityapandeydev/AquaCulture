"""actually add is_processed column

Revision ID: 0998bbfe002e
Revises: 827b962f98f2
Create Date: 2026-02-26 09:40:29.523746

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0998bbfe002e'
down_revision: Union[str, Sequence[str], None] = '827b962f98f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column(
        "sensor_data_raw",
        sa.Column(
            "is_processed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false")
        )
    )

def downgrade():
    op.drop_column("sensor_data_raw", "is_processed")