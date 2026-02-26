from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pond import Pond


class PondService:


    @staticmethod
    async def create(db: AsyncSession, name: str, owner_id):

        pond = Pond(
            name=name,
            owner_id=owner_id
        )

        db.add(pond)

        await db.commit()

        await db.refresh(pond)

        return pond
