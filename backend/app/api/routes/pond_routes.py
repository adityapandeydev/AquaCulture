from fastapi import APIRouter, Depends

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.pond_schema import PondCreate

from app.controllers.pond_controller import PondController

from app.core.database import get_db


router = APIRouter(prefix="/ponds")


from app.core.security import get_current_user
from app.models.user import User

@router.post("/")
async def create_pond(
    data: PondCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    return await PondController.create(
        db,
        data,
        current_user.id
    )
