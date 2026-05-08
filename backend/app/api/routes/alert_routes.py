from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc
import uuid

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.alerts import Alert
from app.models.pond import Pond
from app.models.user import User

router = APIRouter(prefix="/alerts")


@router.get("/{pond_id}")
async def get_alerts(
    pond_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    pond_result = await db.execute(
        select(Pond).where(
            Pond.id == pond_id,
            Pond.owner_id == current_user.id
        )
    )
    pond = pond_result.scalar_one_or_none()
    if not pond:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied for pond {pond_id}"
        )

    result = await db.execute(
        select(Alert)
        .where(Alert.pond_id == pond_id)
        .order_by(desc(Alert.timestamp))
        .limit(50)
    )

    alerts = result.scalars().all()

    return alerts