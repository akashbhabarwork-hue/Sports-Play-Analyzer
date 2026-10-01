"""HTTP response/request models. Pydantic lives only here (the boundary)."""

from uuid import UUID

from pydantic import BaseModel, Field


class MeResponse(BaseModel):
    id: UUID
    email: str | None
    name: str | None
    avatar_url: str | None


class JobAccepted(BaseModel):
    job_id: UUID
    status: str


class UrlSubmit(BaseModel):
    url: str = Field(min_length=1, max_length=2048)
