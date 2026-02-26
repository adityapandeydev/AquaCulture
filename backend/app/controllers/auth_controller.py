from sqlalchemy.ext.asyncio import AsyncSession

from app.services.auth_service import AuthService


class AuthController:


    @staticmethod
    async def register(db: AsyncSession, data):

        return await AuthService.register(
            db,
            data.name,
            data.email,
            data.password
        )


    @staticmethod
    async def login(db: AsyncSession, email: str, password: str):
        return await AuthService.login(db, email, password)
