from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
from typing import List


class SensorRow(BaseModel):
    pond_id: UUID
    do: float | None
    temperature: float | None
    ph: float | None
    turbidity: float | None
    ammonia: float | None
    nitrate: float | None
    timestamp: datetime


class SensorBatch(BaseModel):
    rows: List[SensorRow]