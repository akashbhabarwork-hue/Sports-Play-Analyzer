"""videos: sport, title, thumbnail_key (T-085)

Expand-only: three new columns with safe defaults/NULLs, so the previous app image keeps
working against the upgraded schema (rollback-by-image stays safe). Must stay identical to
app/adapters/db_tables.py (tests/integration/test_migrations.py compares them).

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-02 14:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "videos",
        sa.Column("sport", sa.Text(), server_default=sa.text("'football'"), nullable=False),
    )
    op.add_column("videos", sa.Column("title", sa.Text(), nullable=True))
    op.add_column("videos", sa.Column("thumbnail_key", sa.Text(), nullable=True))
    op.create_check_constraint(
        op.f("ck_videos_sport_valid"), "videos", "sport IN ('football', 'basketball')"
    )
    op.create_check_constraint(
        op.f("ck_videos_title_length"), "videos", "char_length(title) <= 120"
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_videos_title_length"), "videos", type_="check")
    op.drop_constraint(op.f("ck_videos_sport_valid"), "videos", type_="check")
    op.drop_column("videos", "thumbnail_key")
    op.drop_column("videos", "title")
    op.drop_column("videos", "sport")
