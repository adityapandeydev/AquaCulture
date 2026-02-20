from pydantic import BaseModel


class PondCreate(BaseModel):

    name: str


class PondResponse(BaseModel):

    id: int

    name: str

    owner_id: int

    class Config:

        from_attributes = True
