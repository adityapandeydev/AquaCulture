from pydantic import BaseModel


class WaterQualityCreate(BaseModel):

    pond_id: int

    do: float

    temperature: float

    ph: float

    turbidity: float

    ammonia: float

    nitrate: float
