from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.user import User
from app.core.security import hash_password, verify_password, create_access_token


class AuthService:


    @staticmethod
    async def register(db: AsyncSession, email: str, password: str):

        result = await db.execute(
            select(User).where(User.email == email)
        )

        user = result.scalar_one_or_none()

        if user:
            raise Exception("User already exists")

        new_user = User(
            email=email,
            hashed_password=hash_password(password)
        )

        db.add(new_user)

        await db.commit()

        return {"message": "User created"}


    @staticmethod
    async def login(db: AsyncSession, email: str, password: str):

        result = await db.execute(
            select(User).where(User.email == email)
        )

        user = result.scalar_one_or_none()

        if not user:
            raise Exception("Invalid credentials")

        if not verify_password(password, user.hashed_password):
            raise Exception("Invalid credentials")

        token = create_access_token(
            {"sub": user.email}
        )

        return {
            "access_token": token
        }
