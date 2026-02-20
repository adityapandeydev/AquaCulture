from app.services.water_quality_service import WaterQualityService


class WaterQualityController:


    @staticmethod
    async def create(db, data):

        return await WaterQualityService.create(
            db,
            data
        )
