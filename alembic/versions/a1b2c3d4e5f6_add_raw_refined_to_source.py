"""add raw and refined columns to source

Revision ID: a1b2c3d4e5f6
Revises: d6a2ae340f36
Create Date: 2026-03-10 13:40:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "d6a2ae340f36"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("source", sa.Column("raw", sa.Text(), nullable=True))
    op.add_column("source", sa.Column("refined", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("source", "refined")
    op.drop_column("source", "raw")
