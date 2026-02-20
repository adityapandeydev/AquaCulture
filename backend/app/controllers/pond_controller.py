from app.services.pond_service import PondService


class PondController:


    @staticmethod
    async def create(db, data, owner_id):

        return await PondService.create(
            db,
            data.name,
            owner_id
        )
