from app.services.prediction_service import PredictionService


class PredictionController:


    @staticmethod
    async def predict(db, pond_id):

        return await PredictionService.predict(
            db,
            pond_id
        )
