from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.auth_schema import UserRegister, UserLogin

from app.controllers.auth_controller import AuthController

from app.core.database import get_db


router = APIRouter(prefix="/auth")


@router.post("/register")
async def register(
    data: UserRegister,
    db: AsyncSession = Depends(get_db)
):

    return await AuthController.register(db, data)


@router.post("/login")
async def login(
    data: UserLogin,
    db: AsyncSession = Depends(get_db)
):

    return await AuthController.login(db, data)
