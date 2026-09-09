"""add citation_faithfulness to tender_analyses

Revision ID: 151edd6902db
Revises: 1545737ea415
Create Date: 2026-09-09 18:11:29.752710

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "151edd6902db"
down_revision: str | Sequence[str] | None = "1545737ea415"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Adds `citation_faithfulness` -- 3.5's citation-verification score, computed by
    the graph's `verify` node (3.6) but never persisted until now.
    """
    op.add_column("tender_analyses", sa.Column("citation_faithfulness", sa.Float(), nullable=True))


def downgrade() -> None:
    """Drops `citation_faithfulness`, losing every score recorded so far."""
    op.drop_column("tender_analyses", "citation_faithfulness")
