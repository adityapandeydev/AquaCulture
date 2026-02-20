from fastapi import APIRouter, Depends

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.water_quality_schema import WaterQualityCreate

from app.controllers.water_quality_controller import WaterQualityController

from app.core.database import get_db


router = APIRouter(prefix="/water-quality")


@router.post("/")
async def create_log(
    data: WaterQualityCreate,
    db: AsyncSession = Depends(get_db)
):

    return await WaterQualityController.create(
        db,
        data
    )
