import sys
import os

sys.path.append(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../../")
    )
)

import numpy as np

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.models.water_quality_log import WaterQualityLog

# import ML predictor
from ml.inference.predictor import predict_from_window


class PredictionService:

    @staticmethod
    async def predict(db: AsyncSession, pond_id: int):

        # Fetch latest 48 records
        query = (
            select(WaterQualityLog)
            .where(WaterQualityLog.pond_id == pond_id)
            .order_by(desc(WaterQualityLog.timestamp))
            .limit(48)
        )

        result = await db.execute(query)
        rows = result.scalars().all()

        if len(rows) < 48:
            raise Exception("Not enough data for prediction")

        # Reverse to chronological order
        rows = rows[::-1]

        raw_window = []
        timestamps = []

        for r in rows:

            # IMPORTANT: order must match training
            raw_window.append([
                r.nitrate,
                r.ph,
                r.ammonia,
                r.temperature,
                r.do,
                r.turbidity,
                r.manganese   # <-- now included
            ])

            timestamps.append(r.timestamp)

        raw_window = np.array(raw_window, dtype=np.float32)

        # Call ML predictor with timestamps
        prediction = predict_from_window(
            raw_window,
            timestamps
        )

        return prediction

