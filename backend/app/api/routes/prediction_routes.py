from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers.prediction_controller import PredictionController
from app.core.database import get_db


# THIS LINE IS CRITICAL
router = APIRouter(prefix="/predict", tags=["Prediction"])


@router.get("/{pond_id}")
async def predict(
    pond_id: int,
    db: AsyncSession = Depends(get_db)
):
    return await PredictionController.predict(
        db,
        pond_id
    )
