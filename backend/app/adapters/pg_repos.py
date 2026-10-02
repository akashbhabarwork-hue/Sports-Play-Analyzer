"""Postgres repositories (SQLAlchemy Core). Each public method is one transaction.

User data is always filtered by `user_id` in SQL; `*_for_worker` methods are the only
exceptions and must never be reachable from an HTTP route (see core/ports.py).
"""

import functools
import logging
from collections.abc import Callable
from dataclasses import fields
from datetime import datetime
from typing import Any, ParamSpec, TypeVar
from uuid import UUID

from sqlalchemy import Engine, delete, func, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import RowMapping
from sqlalchemy.exc import SQLAlchemyError

from ..core.models import Job, JobResult, JobWithVideo, NewVideo, PlayerTrack, User, Video
from ..errors import ExternalServiceError
from .db_tables import job_results, jobs, player_tracks, sessions, users, videos

logger = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R")
T = TypeVar("T")


def db_errors(fn: Callable[P, R]) -> Callable[P, R]:
    @functools.wraps(fn)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return fn(*args, **kwargs)
        except SQLAlchemyError as e:
            logger.error("database call failed", extra={"op": fn.__qualname__})
            raise ExternalServiceError("Database operation failed") from e

    return wrapper


def row_to(cls: type[T], row: RowMapping | None) -> T | None:
    if row is None:
        return None
    return cls(**{f.name: row[f.name] for f in fields(cls)})


def rows_to(cls: type[T], rows: list[RowMapping]) -> list[T]:
    return [cls(**{f.name: r[f.name] for f in fields(cls)}) for r in rows]


class PostgresUserRepo:
    def __init__(self, engine: Engine):
        self.engine = engine

    @db_errors
    def upsert_from_oauth(
        self,
        provider: str,
        provider_sub: str,
        email: str | None,
        name: str | None,
        avatar_url: str | None,
    ) -> User:
        profile = {"email": email, "name": name, "avatar_url": avatar_url}
        stmt = (
            pg_insert(users)
            .values(provider=provider, provider_sub=provider_sub, **profile)
            .on_conflict_do_update(constraint="uq_users_provider_provider_sub", set_=profile)
            .returning(*users.c)
        )
        with self.engine.begin() as conn:
            return row_to(User, conn.execute(stmt).mappings().one())

    @db_errors
    def get(self, user_id: UUID) -> User | None:
        with self.engine.connect() as conn:
            row = conn.execute(select(users).where(users.c.id == user_id)).mappings().first()
        return row_to(User, row)


class PostgresSessionRepo:
    def __init__(self, engine: Engine):
        self.engine = engine

    @db_errors
    def create(self, token_hash: bytes, user_id: UUID, expires_at: datetime) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                insert(sessions).values(
                    token_hash=token_hash, user_id=user_id, expires_at=expires_at
                )
            )

    @db_errors
    def get_user_by_token(self, token_hash: bytes) -> User | None:
        stmt = (
            select(users)
            .join(sessions, sessions.c.user_id == users.c.id)
            .where(sessions.c.token_hash == token_hash, sessions.c.expires_at > func.now())
        )
        with self.engine.connect() as conn:
            return row_to(User, conn.execute(stmt).mappings().first())

    @db_errors
    def delete(self, token_hash: bytes) -> None:
        with self.engine.begin() as conn:
            conn.execute(delete(sessions).where(sessions.c.token_hash == token_hash))

    @db_errors
    def delete_all_for_user(self, user_id: UUID) -> int:
        with self.engine.begin() as conn:
            return conn.execute(delete(sessions).where(sessions.c.user_id == user_id)).rowcount

    @db_errors
    def delete_expired(self) -> int:
        with self.engine.begin() as conn:
            return conn.execute(
                delete(sessions).where(sessions.c.expires_at <= func.now())
            ).rowcount


class PostgresVideoRepo:
    def __init__(self, engine: Engine):
        self.engine = engine

    @db_errors
    def get(self, user_id: UUID, video_id: UUID) -> Video | None:
        stmt = select(videos).where(videos.c.id == video_id, videos.c.user_id == user_id)
        with self.engine.connect() as conn:
            return row_to(Video, conn.execute(stmt).mappings().first())

    @db_errors
    def get_for_worker(self, video_id: UUID) -> Video | None:
        with self.engine.connect() as conn:
            row = conn.execute(select(videos).where(videos.c.id == video_id)).mappings().first()
        return row_to(Video, row)

    @db_errors
    def set_media_for_worker(
        self,
        video_id: UUID,
        storage_key: str,
        size_bytes: int,
        duration_s: float,
        width: int,
        height: int,
        fps: float,
    ) -> None:
        stmt = (
            update(videos)
            .where(videos.c.id == video_id)
            .values(
                storage_key=storage_key,
                size_bytes=size_bytes,
                duration_s=duration_s,
                width=width,
                height=height,
                fps=fps,
            )
        )
        with self.engine.begin() as conn:
            conn.execute(stmt)

    @db_errors
    def set_thumbnail_for_worker(self, video_id: UUID, thumbnail_key: str) -> None:
        stmt = update(videos).where(videos.c.id == video_id).values(thumbnail_key=thumbnail_key)
        with self.engine.begin() as conn:
            conn.execute(stmt)


class PostgresJobRepo:
    def __init__(self, engine: Engine):
        self.engine = engine

    @db_errors
    def create_with_video(self, user_id: UUID, new_video: NewVideo, config: dict[str, Any]) -> Job:
        # One transaction: a failed job insert must not leave an orphan video row.
        with self.engine.begin() as conn:
            values = {
                "user_id": user_id,
                "source_type": new_video.source_type,
                "source_url": new_video.source_url,
                "original_filename": new_video.original_filename,
                "storage_key": new_video.storage_key,
                "size_bytes": new_video.size_bytes,
                "duration_s": new_video.duration_s,
                "width": new_video.width,
                "height": new_video.height,
                "fps": new_video.fps,
                "sport": new_video.sport,
                "title": new_video.title,
            }
            if new_video.id is not None:
                values["id"] = new_video.id
            video_id = conn.execute(
                insert(videos).values(**values).returning(videos.c.id)
            ).scalar_one()
            row = (
                conn.execute(
                    insert(jobs)
                    .values(user_id=user_id, video_id=video_id, config=config)
                    .returning(*jobs.c)
                )
                .mappings()
                .one()
            )
        return row_to(Job, row)

    @db_errors
    def get(self, user_id: UUID, job_id: UUID) -> Job | None:
        stmt = select(jobs).where(jobs.c.id == job_id, jobs.c.user_id == user_id)
        with self.engine.connect() as conn:
            return row_to(Job, conn.execute(stmt).mappings().first())

    @db_errors
    def list_for_user(self, user_id: UUID, limit: int = 50) -> list[Job]:
        # Served by ix_jobs_user_created (user_id, created_at DESC).
        stmt = (
            select(jobs)
            .where(jobs.c.user_id == user_id)
            .order_by(jobs.c.created_at.desc(), jobs.c.id.desc())
            .limit(limit)
        )
        with self.engine.connect() as conn:
            return rows_to(Job, conn.execute(stmt).mappings().all())

    def _with_video(self, user_id: UUID):
        # Both tables are filtered on user_id: a job can only point at its owner's video, and
        # repeating the filter keeps that true even if a bug ever broke the FK pairing.
        cols = [c.label(f"j_{c.name}") for c in jobs.c] + [c.label(f"v_{c.name}") for c in videos.c]
        return (
            select(*cols)
            .join(videos, videos.c.id == jobs.c.video_id)
            .where(jobs.c.user_id == user_id, videos.c.user_id == user_id)
        )

    @db_errors
    def get_with_video(self, user_id: UUID, job_id: UUID) -> JobWithVideo | None:
        stmt = self._with_video(user_id).where(jobs.c.id == job_id)
        with self.engine.connect() as conn:
            row = conn.execute(stmt).mappings().first()
        return _job_with_video(row) if row else None

    @db_errors
    def list_with_videos(self, user_id: UUID, limit: int = 50) -> list[JobWithVideo]:
        # Same index as list_for_user (ix_jobs_user_created); the join is by primary key.
        stmt = (
            self._with_video(user_id)
            .order_by(jobs.c.created_at.desc(), jobs.c.id.desc())
            .limit(limit)
        )
        with self.engine.connect() as conn:
            return [_job_with_video(r) for r in conn.execute(stmt).mappings().all()]

    @db_errors
    def get_for_worker(self, job_id: UUID) -> Job | None:
        with self.engine.connect() as conn:
            return row_to(
                Job, conn.execute(select(jobs).where(jobs.c.id == job_id)).mappings().first()
            )


def _prefixed(cls: type[T], row: RowMapping, prefix: str) -> T:
    return cls(**{f.name: row[f"{prefix}{f.name}"] for f in fields(cls)})


def _job_with_video(row: RowMapping) -> JobWithVideo:
    return JobWithVideo(job=_prefixed(Job, row, "j_"), video=_prefixed(Video, row, "v_"))


class PostgresResultRepo:
    def __init__(self, engine: Engine):
        self.engine = engine

    @db_errors
    def get(self, user_id: UUID, job_id: UUID) -> JobResult | None:
        stmt = (
            select(job_results)
            .join(jobs, jobs.c.id == job_results.c.job_id)
            .where(job_results.c.job_id == job_id, jobs.c.user_id == user_id)
        )
        with self.engine.connect() as conn:
            return row_to(JobResult, conn.execute(stmt).mappings().first())

    @db_errors
    def list_tracks(self, user_id: UUID, job_id: UUID) -> list[PlayerTrack]:
        stmt = (
            select(player_tracks)
            .join(jobs, jobs.c.id == player_tracks.c.job_id)
            .where(player_tracks.c.job_id == job_id, jobs.c.user_id == user_id)
            .order_by(player_tracks.c.track_id)
        )
        with self.engine.connect() as conn:
            return rows_to(PlayerTrack, conn.execute(stmt).mappings().all())

    @db_errors
    def get_track(self, user_id: UUID, job_id: UUID, track_id: int) -> PlayerTrack | None:
        stmt = (
            select(player_tracks)
            .join(jobs, jobs.c.id == player_tracks.c.job_id)
            .where(
                player_tracks.c.job_id == job_id,
                player_tracks.c.track_id == track_id,
                jobs.c.user_id == user_id,
            )
        )
        with self.engine.connect() as conn:
            return row_to(PlayerTrack, conn.execute(stmt).mappings().first())
