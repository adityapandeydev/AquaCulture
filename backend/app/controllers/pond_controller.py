from app.services.pond_service import PondService


class PondController:


    @staticmethod
    async def create(db, data, owner_id):

        return await PondService.create(
            db,
            data.name,
            data.timezone,
            owner_id
        )

    @staticmethod
    async def list_for_owner(db, owner_id):
        return await PondService.list_for_owner(db, owner_id)

    @staticmethod
    async def get_for_owner(db, pond_id, owner_id):
        return await PondService.get_for_owner(db, pond_id, owner_id)

    @staticmethod
    async def update_for_owner(db, pond_id, owner_id, data):
        return await PondService.update_for_owner(
            db,
            pond_id,
            owner_id,
            data.name,
            data.timezone
        )

    @staticmethod
    async def delete_for_owner(db, pond_id, owner_id):
        await PondService.delete_for_owner(db, pond_id, owner_id)
        return {"status": "Pond deleted"}
