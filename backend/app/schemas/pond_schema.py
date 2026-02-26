from pydantic import BaseModel
from uuid import UUID

class PondCreate(BaseModel):

    name: str


class PondResponse(BaseModel):

    id: UUID

    name: str

    owner_id: UUID

    class Config:

        from_attributes = True
