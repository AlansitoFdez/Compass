"""add title embedding vector column

Revision ID: 57bad4ff539e
Revises: 198bdf87e9a5
Create Date: 2026-09-08 13:31:36.047118

"""

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "57bad4ff539e"
down_revision: str | Sequence[str] | None = "198bdf87e9a5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Enables pgvector and adds `title_embedding` (768-dim, per phase2.4) + its HNSW index.

    Nullable, unlike `title_tsv`: an embedding needs the model, not just SQL,
    so it can't be a generated column -- `matching.tasks.generate_embeddings_task`
    populates it after this migration runs, not this migration itself.
    """
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.add_column("tenders", sa.Column("title_embedding", Vector(768), nullable=True))
    op.create_index(
        "ix_tenders_title_embedding_hnsw",
        "tenders",
        ["title_embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"title_embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    """Drops `title_embedding` and its HNSW index -- the vector recovery stage loses its column."""
    op.drop_index(
        "ix_tenders_title_embedding_hnsw",
        table_name="tenders",
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"title_embedding": "vector_cosine_ops"},
    )
    op.drop_column("tenders", "title_embedding")
    op.execute("DROP EXTENSION IF EXISTS vector")
