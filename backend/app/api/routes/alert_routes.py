from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc

from app.core.database import get_db
from app.models.alerts import Alert

router = APIRouter(prefix="/alerts")


@router.get("/{pond_id}")
async def get_alerts(pond_id: str, db: AsyncSession = Depends(get_db)):

    result = await db.execute(
        select(Alert)
        .where(Alert.pond_id == pond_id)
        .order_by(desc(Alert.timestamp))
        .limit(50)
    )

    alerts = result.scalars().all()

    return alerts