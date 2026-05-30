"""Add optional display_name column — user-editable label, filename unchanged on disk."""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_add_document_display_name"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add nullable display_name column to documents."""
    op.add_column(
        "documents",
        sa.Column("display_name", sa.String(length=120), nullable=True),
    )


def downgrade() -> None:
    """Remove display_name column."""
    op.drop_column("documents", "display_name")
