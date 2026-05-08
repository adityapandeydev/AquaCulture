from datetime import datetime, timedelta, timezone
import random
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc
import uuid

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.pond import Pond
from app.models.sensor_data_raw import SensorDataRaw
from app.models.sensor_data_clean import SensorDataClean
from app.models.forecast_logs import ForecastLog
from app.schemas.sensor_schema import SensorBatch
from app.services.orchestrator_service import OrchestratorService


router = APIRouter(prefix="/sensor")


async def _get_owned_pond_or_none(db: AsyncSession, pond_id: uuid.UUID, owner_id):
    result = await db.execute(
        select(Pond).where(
            Pond.id == pond_id,
            Pond.owner_id == owner_id
        )
    )
    return result.scalar_one_or_none()


@router.post("/ingest")
async def ingest_sensor_data(
    batch: SensorBatch,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    if not batch.rows:
        return {"status": "no rows provided"}

    pond_ids = {row.pond_id for row in batch.rows}
    for pond_id in pond_ids:
        owned = await _get_owned_pond_or_none(db, pond_id, current_user.id)
        if not owned:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied for pond {pond_id}"
            )

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

    processed = await OrchestratorService.process_pending_raw_rows(db)

    return {
        "status": "ingestion completed",
        "processed_rows": processed["processed_rows"]
    }

@router.post("/simulate/{pond_id}")
async def simulate(
    pond_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    owned = await _get_owned_pond_or_none(db, pond_id, current_user.id)
    if not owned:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied for pond {pond_id}"
        )

    result = await OrchestratorService.simulate_from_raw(db, pond_id)
    return result


@router.post("/simulate-feed/{pond_id}")
async def simulate_sensor_feed(
    pond_id: uuid.UUID,
    hours: int = 24,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    owned = await _get_owned_pond_or_none(db, pond_id, current_user.id)
    if not owned:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied for pond {pond_id}"
        )

    if hours < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="hours must be >= 1"
        )

    end_time = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    start_time = end_time - timedelta(hours=hours - 1)

    rows_created = 0
    for step in range(hours):
        ts = start_time + timedelta(hours=step)
        raw_entry = SensorDataRaw(
            id=uuid.uuid4(),
            pond_id=pond_id,
            do=round(random.uniform(4.5, 8.5), 2),
            temperature=round(random.uniform(24.0, 32.0), 2),
            ph=round(random.uniform(6.6, 8.4), 2),
            turbidity=round(random.uniform(10.0, 90.0), 2),
            ammonia=round(random.uniform(0.1, 1.8), 3),
            nitrate=round(random.uniform(3.0, 35.0), 2),
            timestamp=ts
        )
        db.add(raw_entry)
        rows_created += 1

    await db.commit()

    return {
        "status": "simulated sensor feed inserted",
        "pond_id": str(pond_id),
        "rows_created": rows_created,
        "from": str(start_time),
        "to": str(end_time)
    }


@router.get("/pond/{pond_id}/raw")
async def get_pond_raw_data(
    pond_id: uuid.UUID,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    owned = await _get_owned_pond_or_none(db, pond_id, current_user.id)
    if not owned:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied for pond {pond_id}"
        )

    result = await db.execute(
        select(SensorDataRaw)
        .where(SensorDataRaw.pond_id == pond_id)
        .order_by(desc(SensorDataRaw.timestamp))
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/pond/{pond_id}/clean")
async def get_pond_clean_data(
    pond_id: uuid.UUID,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    owned = await _get_owned_pond_or_none(db, pond_id, current_user.id)
    if not owned:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied for pond {pond_id}"
        )

    result = await db.execute(
        select(SensorDataClean)
        .where(SensorDataClean.pond_id == pond_id)
        .order_by(desc(SensorDataClean.timestamp))
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/pond/{pond_id}/forecasts")
async def get_pond_forecasts(
    pond_id: uuid.UUID,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    owned = await _get_owned_pond_or_none(db, pond_id, current_user.id)
    if not owned:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied for pond {pond_id}"
        )

    result = await db.execute(
        select(ForecastLog)
        .where(ForecastLog.pond_id == pond_id)
        .order_by(desc(ForecastLog.forecast_for))
        .limit(limit)
    )
    return result.scalars().all()