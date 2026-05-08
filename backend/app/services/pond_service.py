from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import HTTPException, status

from app.models.pond import Pond


class PondService:


    @staticmethod
    async def create(db: AsyncSession, name: str, timezone: str, owner_id):

        pond = Pond(
            name=name,
            timezone=timezone,
            owner_id=owner_id
        )

        db.add(pond)

        await db.commit()

        await db.refresh(pond)

        return pond

    @staticmethod
    async def list_for_owner(db: AsyncSession, owner_id):
        result = await db.execute(
            select(Pond)
            .where(Pond.owner_id == owner_id)
            .order_by(Pond.created_at.desc())
        )
        return result.scalars().all()

    @staticmethod
    async def get_for_owner(db: AsyncSession, pond_id, owner_id):
        result = await db.execute(
            select(Pond).where(
                Pond.id == pond_id,
                Pond.owner_id == owner_id
            )
        )
        pond = result.scalar_one_or_none()
        if not pond:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pond not found"
            )
        return pond

    @staticmethod
    async def update_for_owner(db: AsyncSession, pond_id, owner_id, name=None, timezone=None):
        pond = await PondService.get_for_owner(db, pond_id, owner_id)
        if name is not None:
            pond.name = name
        if timezone is not None:
            pond.timezone = timezone
        db.add(pond)
        await db.commit()
        await db.refresh(pond)
        return pond

    @staticmethod
    async def delete_for_owner(db: AsyncSession, pond_id, owner_id):
        pond = await PondService.get_for_owner(db, pond_id, owner_id)
        await db.delete(pond)
        await db.commit()
