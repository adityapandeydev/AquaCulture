from sqlalchemy.ext.asyncio import AsyncSession

from app.models.water_quality_log import WaterQualityLog


class WaterQualityService:


    @staticmethod
    async def create(db: AsyncSession, data):

        log = WaterQualityLog(**data.dict())

        db.add(log)

        await db.commit()

        await db.refresh(log)

        return log
