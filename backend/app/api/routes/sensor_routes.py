from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app.core.database import get_db
from app.models.sensor_data_raw import SensorDataRaw
from app.schemas.sensor_schema import SensorBatch
from app.services.orchestrator_service import OrchestratorService


router = APIRouter(prefix="/sensor")


@router.post("/ingest")
async def ingest_sensor_data(
    batch: SensorBatch,
    db: AsyncSession = Depends(get_db)
):

    for row in batch.rows:
        raw_entry = SensorDataRaw(
            id=uuid.uuid4(),
            pond_id=row.pond_id,
            do=row.do,
            temperature=row.temperature,
            ph=row.ph,
            turbidity=row.turbidity,
            ammonia=row.ammonia,
            nitrate=row.nitrate,
            timestamp=row.timestamp
        )
        db.add(raw_entry)

    await db.commit()

    await OrchestratorService.process_pending_raw_rows(db)

    return {"status": "ingestion completed"}

@router.post("/simulate/{pond_id}")
async def simulate(
    pond_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    result = await OrchestratorService.simulate_from_raw(db, pond_id)
    return result