from datetime import datetime
from pydantic import BaseModel
from uuid import UUID

class PondCreate(BaseModel):

    name: str
    timezone: str = "UTC"


class PondUpdate(BaseModel):
    name: str | None = None
    timezone: str | None = None


class PondResponse(BaseModel):

    id: UUID

    name: str

    owner_id: UUID
    timezone: str
    created_at: datetime

    class Config:

        from_attributes = True
