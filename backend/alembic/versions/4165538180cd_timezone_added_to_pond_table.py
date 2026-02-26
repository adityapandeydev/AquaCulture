"""timezone added to pond table

Revision ID: 4165538180cd
Revises: 0998bbfe002e
Create Date: 2026-02-26 11:43:08.964869

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4165538180cd'
down_revision: Union[str, Sequence[str], None] = '0998bbfe002e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ponds",
        sa.Column("timezone", sa.String(), nullable=False, server_default="UTC")
    )


def downgrade() -> None:
    op.drop_column("ponds", "timezone")
