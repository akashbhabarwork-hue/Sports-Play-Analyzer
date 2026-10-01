"""HTTP response/request models. Pydantic lives only here (the boundary)."""

from uuid import UUID

from pydantic import BaseModel


class MeResponse(BaseModel):
    id: UUID
    email: str | None
    name: str | None
    avatar_url: str | None


class JobAccepted(BaseModel):
    job_id: UUID
    status: str
