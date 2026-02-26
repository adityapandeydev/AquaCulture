import sys
import os

sys.path.append(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../../")
    )
)

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc
from datetime import timedelta
from zoneinfo import ZoneInfo
import uuid
import numpy as np

from app.models.sensor_data_raw import SensorDataRaw
from app.models.sensor_data_clean import SensorDataClean
from app.models.forecast_logs import ForecastLog
from app.models.pond import Pond

from app.services.ingestion_service import IngestionService
from ml.inference.predictor import predict_from_window, LOOKBACK


class OrchestratorService:

    @staticmethod
    async def simulate_from_raw(db: AsyncSession, pond_id: uuid.UUID):

        # ---------------------------------------------
        # 1️⃣ Fetch RAW rows (historical replay)
        # ---------------------------------------------
        result = await db.execute(
            select(SensorDataRaw)
            .where(SensorDataRaw.pond_id == pond_id)
            .order_by(SensorDataRaw.timestamp.asc())
        )
        raw_rows = result.scalars().all()

        if len(raw_rows) < LOOKBACK:
            return {"status": "Not enough raw data"}

        # ---------------------------------------------
        # 2️⃣ Fetch pond timezone once
        # ---------------------------------------------
        pond_result = await db.execute(
            select(Pond).where(Pond.id == pond_id)
        )
        pond = pond_result.scalar_one()
        pond_tz = ZoneInfo(pond.timezone)

        hourly_predictions = []
        rolling_clean_buffer = []

        # ---------------------------------------------
        # 3️⃣ Sequential simulation (like real-time)
        # ---------------------------------------------
        for raw in raw_rows:

            # ---- Ingestion step ----
            await IngestionService.process_raw_row(db, raw.id)

            raw.is_processed = True
            db.add(raw)

            # Fetch the clean row that was just inserted
            result = await db.execute(
                select(SensorDataClean)
                .where(SensorDataClean.raw_id == raw.id)
            )
            clean_row = result.scalar_one_or_none()

            if not clean_row:
                continue

            rolling_clean_buffer.append(clean_row)

            # Maintain rolling window size
            if len(rolling_clean_buffer) > LOOKBACK:
                rolling_clean_buffer.pop(0)

            # Not enough window yet
            if len(rolling_clean_buffer) < LOOKBACK:
                continue

            # ---------------------------------------------
            # 4️⃣ Build window + predict (Every Hour)
            # ---------------------------------------------
            raw_window = np.array([
                [
                    row.nitrate,
                    row.ph,
                    row.ammonia,
                    row.temperature,
                    row.do,
                    row.turbidity,
                ]
                for row in rolling_clean_buffer
            ])

            timestamps = [row.timestamp for row in rolling_clean_buffer]

            prediction_result = predict_from_window(raw_window, timestamps)

            water_forecast = np.array(prediction_result["water_forecast"])
            nitrogen_forecast = np.array(prediction_result["nitrogen_forecast"])
            risk_states = prediction_result["risk"]["risk_states"]

            latest_clean = rolling_clean_buffer[-1]
            local_time = latest_clean.timestamp.astimezone(pond_tz)

            # Store EVERY hourly prediction for JSON display
            hourly_predictions.append({
                "window_end": str(latest_clean.timestamp),
                "water_forecast": water_forecast.tolist(),
                "nitrogen_forecast": nitrogen_forecast.tolist(),
                "risk": prediction_result["risk"]
            })

            # ---------------------------------------------
            # 5️⃣ Store only at 6-hour boundary
            # ---------------------------------------------
            if local_time.hour % 6 != 0:
                continue

            # Check last stored forecast to avoid overlap
            result = await db.execute(
                select(ForecastLog)
                .where(ForecastLog.pond_id == pond_id)
                .order_by(desc(ForecastLog.forecast_for))
                .limit(1)
            )
            last_forecast = result.scalar_one_or_none()

            if last_forecast:
                block_start = last_forecast.forecast_for
                if last_forecast.forecast_for >= latest_clean.timestamp:
                    continue
            else:
                block_start = latest_clean.timestamp

            # Store 6-hour block
            for step in range(6):

                forecast_time = block_start + timedelta(hours=step + 1)

                forecast_entry = ForecastLog(
                    id=uuid.uuid4(),
                    pond_id=pond_id,
                    forecast_block_start=block_start,
                    forecast_for=forecast_time,
                    horizon_step=step + 1,
                    pred_do=water_forecast[step][0],
                    pred_temperature=water_forecast[step][1],
                    pred_ph=water_forecast[step][2],
                    pred_turbidity=water_forecast[step][3],
                    pred_ammonia=nitrogen_forecast[step][0],
                    pred_nitrate=nitrogen_forecast[step][1],
                    risk_state=risk_states[step]
                )

                db.add(forecast_entry)

        await db.commit()

        return {
            "status": "Simulation complete",
            "total_hourly_predictions": len(hourly_predictions),
            "hourly_predictions": hourly_predictions
        }