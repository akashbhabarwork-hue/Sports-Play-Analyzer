"""SQLAlchemy Core table definitions — the single source of truth for the schema.

Alembic revisions are written to match these; `tests/integration/test_migrations.py`
fails if the two drift. Never call `metadata.create_all()` in app code.
"""

from sqlalchemy import (
    REAL,
    BigInteger,
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    PrimaryKeyConstraint,
    SmallInteger,
    Table,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import BYTEA, JSONB, TIMESTAMP, UUID

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=NAMING_CONVENTION)

JOB_STATUSES = ("queued", "processing", "succeeded", "failed")
SPORTS = ("football", "basketball")  # same tuple as core/submit_rules.SPORTS (test_submit_rules)
TEAMS = ("A", "B", "unknown")


def _uuid_pk() -> Column:
    return Column(
        "id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )


def _created_at() -> Column:
    return Column(
        "created_at", TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )


def _in_list(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


users = Table(
    "users",
    metadata,
    _uuid_pk(),
    Column("provider", Text, nullable=False),
    Column("provider_sub", Text, nullable=False),
    Column("email", Text),
    Column("name", Text),
    Column("avatar_url", Text),
    _created_at(),
    UniqueConstraint("provider", "provider_sub"),
)

sessions = Table(
    "sessions",
    metadata,
    # sha256 of the opaque cookie token; the raw token is never stored
    Column("token_hash", BYTEA, primary_key=True),
    Column(
        "user_id",
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    ),
    _created_at(),
    Column("expires_at", TIMESTAMP(timezone=True), nullable=False),
)

videos = Table(
    "videos",
    metadata,
    _uuid_pk(),
    Column(
        "user_id",
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("source_type", Text, nullable=False),
    Column("source_url", Text),
    Column("original_filename", Text),
    Column("storage_key", Text),  # null until the url path has been fetched
    Column("size_bytes", BigInteger),
    Column("duration_s", REAL),
    Column("width", Integer),
    Column("height", Integer),
    Column("fps", REAL),
    _created_at(),
    # 0002 (T-085): what the coach told us + the worker's first-frame thumbnail.
    Column("sport", Text, nullable=False, server_default=text("'football'")),
    Column("title", Text),
    Column("thumbnail_key", Text),
    CheckConstraint(_in_list("source_type", ("upload", "url")), name="source_type_valid"),
    CheckConstraint("(source_type = 'url') = (source_url IS NOT NULL)", name="url_matches_source"),
    CheckConstraint(_in_list("sport", SPORTS), name="sport_valid"),
    CheckConstraint("char_length(title) <= 120", name="title_length"),
)

jobs = Table(
    "jobs",
    metadata,
    _uuid_pk(),
    Column(
        "user_id",
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "video_id",
        UUID(as_uuid=True),
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("status", Text, nullable=False, server_default=text("'queued'")),
    Column("progress", SmallInteger, nullable=False, server_default=text("0")),
    Column("stage", Text),  # fetching | decoding | detecting | saving
    Column("error_code", Text),
    Column("error_message", Text),
    Column("attempts", SmallInteger, nullable=False, server_default=text("0")),
    Column("max_attempts", SmallInteger, nullable=False, server_default=text("3")),
    Column("locked_by", Text),
    Column("lease_expires_at", TIMESTAMP(timezone=True)),
    Column("config", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    _created_at(),
    Column("started_at", TIMESTAMP(timezone=True)),
    Column("finished_at", TIMESTAMP(timezone=True)),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")),
    CheckConstraint(_in_list("status", JOB_STATUSES), name="status_valid"),
    CheckConstraint("progress BETWEEN 0 AND 100", name="progress_range"),
    CheckConstraint("attempts >= 0 AND max_attempts >= 1", name="attempts_valid"),
    CheckConstraint("status <> 'failed' OR error_code IS NOT NULL", name="failed_has_error"),
)

job_results = Table(
    "job_results",
    metadata,
    Column(
        "job_id",
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("stats", JSONB, nullable=False),
    Column("annotated_key", Text, nullable=False),
    _created_at(),
)

player_tracks = Table(
    "player_tracks",
    metadata,
    Column(
        "job_id",
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("track_id", Integer, nullable=False),
    Column("team", Text),
    Column("frames_visible", Integer, nullable=False),
    Column("distance_px", REAL, nullable=False),
    Column("distance_rel", REAL, nullable=False),
    Column("possession_frames", Integer, nullable=False, server_default=text("0")),
    Column("heatmap", JSONB, nullable=False),  # {"w": 32, "h": 18, "counts": [...], "max": n}
    Column("track", JSONB, nullable=False),  # [[t_s, nx, ny], ...] normalised
    # natural key: a retried job replaces its rows instead of duplicating them
    PrimaryKeyConstraint("job_id", "track_id"),
    CheckConstraint(f"team IS NULL OR {_in_list('team', TEAMS)}", name="team_valid"),
)

# Worker claim query: WHERE status IN ('queued','processing') ... ORDER BY created_at.
# Partial, so finished jobs drop out and the index stays small.
Index(
    "ix_jobs_claimable",
    jobs.c.created_at,
    postgresql_where=text("status IN ('queued', 'processing')"),
)
# "My jobs" list: WHERE user_id = :u ORDER BY created_at DESC.
Index("ix_jobs_user_created", jobs.c.user_id, jobs.c.created_at.desc())
# Logout-all / expired-session cleanup by user.
Index("ix_sessions_user", sessions.c.user_id)
