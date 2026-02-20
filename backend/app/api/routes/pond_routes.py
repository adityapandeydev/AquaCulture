from fastapi import APIRouter, Depends

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.pond_schema import PondCreate

from app.controllers.pond_controller import PondController

from app.core.database import get_db


router = APIRouter(prefix="/ponds")


@router.post("/")
async def create_pond(
    data: PondCreate,
    db: AsyncSession = Depends(get_db)
):

    owner_id = 1  # temporary

    return await PondController.create(
        db,
        data,
        owner_id
    )
