import uuid
from fastapi import APIRouter, Depends

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.pond_schema import PondCreate, PondUpdate

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


@router.get("/")
async def list_ponds(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await PondController.list_for_owner(db, current_user.id)


@router.get("/{pond_id}")
async def get_pond(
    pond_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await PondController.get_for_owner(db, pond_id, current_user.id)


@router.patch("/{pond_id}")
async def update_pond(
    pond_id: uuid.UUID,
    data: PondUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await PondController.update_for_owner(db, pond_id, current_user.id, data)


@router.delete("/{pond_id}")
async def delete_pond(
    pond_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await PondController.delete_for_owner(db, pond_id, current_user.id)
