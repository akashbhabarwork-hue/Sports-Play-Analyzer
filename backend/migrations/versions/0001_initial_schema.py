"""initial schema: users, sessions, videos, jobs, job_results, player_tracks

Hand-reviewed autogenerate output; must stay identical to app/adapters/db_tables.py
(tests/integration/test_migrations.py compares them).

Revision ID: 0001
Revises:
Create Date: 2026-10-01 13:04:02.227674
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("provider_sub", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint(
            "provider", "provider_sub", name=op.f("uq_users_provider_provider_sub")
        ),
    )
    op.create_table(
        "sessions",
        sa.Column("token_hash", postgresql.BYTEA(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_sessions_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("token_hash", name=op.f("pk_sessions")),
    )
    # logout-all / session cleanup per user (see D-011)
    op.create_index("ix_sessions_user", "sessions", ["user_id"], unique=False)
    op.create_table(
        "videos",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("original_filename", sa.Text(), nullable=True),
        sa.Column("storage_key", sa.Text(), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("duration_s", sa.REAL(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("fps", sa.REAL(), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(source_type = 'url') = (source_url IS NOT NULL)",
            name=op.f("ck_videos_url_matches_source"),
        ),
        sa.CheckConstraint(
            "source_type IN ('upload', 'url')", name=op.f("ck_videos_source_type_valid")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_videos_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_videos")),
    )
    op.create_table(
        "jobs",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("video_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'queued'"), nullable=False),
        sa.Column("progress", sa.SmallInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("stage", sa.Text(), nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("attempts", sa.SmallInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("max_attempts", sa.SmallInteger(), server_default=sa.text("3"), nullable=False),
        sa.Column("locked_by", sa.Text(), nullable=True),
        sa.Column("lease_expires_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("finished_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status <> 'failed' OR error_code IS NOT NULL", name=op.f("ck_jobs_failed_has_error")
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'processing', 'succeeded', 'failed')",
            name=op.f("ck_jobs_status_valid"),
        ),
        sa.CheckConstraint(
            "attempts >= 0 AND max_attempts >= 1", name=op.f("ck_jobs_attempts_valid")
        ),
        sa.CheckConstraint("progress BETWEEN 0 AND 100", name=op.f("ck_jobs_progress_range")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_jobs_user_id_users"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["video_id"], ["videos.id"], name=op.f("fk_jobs_video_id_videos"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jobs")),
    )
    # worker claim query; partial so finished jobs drop out (see D-011)
    op.create_index(
        "ix_jobs_claimable",
        "jobs",
        ["created_at"],
        unique=False,
        postgresql_where=sa.text("status IN ('queued', 'processing')"),
    )
    # "my jobs" list ordered newest first (see D-011)
    op.create_index(
        "ix_jobs_user_created",
        "jobs",
        ["user_id", sa.literal_column("created_at DESC")],
        unique=False,
    )
    op.create_table(
        "job_results",
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("stats", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("annotated_key", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name=op.f("fk_job_results_job_id_jobs"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("job_id", name=op.f("pk_job_results")),
    )
    op.create_table(
        "player_tracks",
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("track_id", sa.Integer(), nullable=False),
        sa.Column("team", sa.Text(), nullable=True),
        sa.Column("frames_visible", sa.Integer(), nullable=False),
        sa.Column("distance_px", sa.REAL(), nullable=False),
        sa.Column("distance_rel", sa.REAL(), nullable=False),
        sa.Column("possession_frames", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("heatmap", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("track", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.CheckConstraint(
            "team IS NULL OR team IN ('A', 'B', 'unknown')",
            name=op.f("ck_player_tracks_team_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name=op.f("fk_player_tracks_job_id_jobs"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("job_id", "track_id", name=op.f("pk_player_tracks")),
    )


def downgrade() -> None:
    op.drop_table("player_tracks")
    op.drop_table("job_results")
    op.drop_index("ix_jobs_user_created", table_name="jobs")
    op.drop_index(
        "ix_jobs_claimable",
        table_name="jobs",
        postgresql_where=sa.text("status IN ('queued', 'processing')"),
    )
    op.drop_table("jobs")
    op.drop_table("videos")
    op.drop_index("ix_sessions_user", table_name="sessions")
    op.drop_table("sessions")
    op.drop_table("users")
