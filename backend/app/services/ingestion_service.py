from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc
import uuid
import joblib
import os

from app.models.sensor_data_raw import SensorDataRaw
from app.models.sensor_data_clean import SensorDataClean
from app.models.alerts import Alert
from app.models.forecast_logs import ForecastLog  # ✅ NEW IMPORT


# ----------------------------
# Load Imputation Models
# ----------------------------

PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)

IMPUTE_DIR = os.path.join(PROJECT_ROOT, "ml", "models", "imputation")

IMPUTE_MODELS = {
    "do": joblib.load(os.path.join(IMPUTE_DIR, "impute_do.pkl")),
    "temperature": joblib.load(os.path.join(IMPUTE_DIR, "impute_temperature.pkl")),
    "ph": joblib.load(os.path.join(IMPUTE_DIR, "impute_ph.pkl")),
    "turbidity": joblib.load(os.path.join(IMPUTE_DIR, "impute_turbidity.pkl")),
    "ammonia": joblib.load(os.path.join(IMPUTE_DIR, "impute_ammonia.pkl")),
    "nitrate": joblib.load(os.path.join(IMPUTE_DIR, "impute_nitrate.pkl")),
}

RANGES = {
    "do": (0, 20),
    "temperature": (0, 45),
    "ph": (3, 11),
    "turbidity": (0, 200),
    "ammonia": (0, 10),
    "nitrate": (0, 200),
}


class IngestionService:

    @staticmethod
    async def process_raw_row(db: AsyncSession, raw_id: uuid.UUID):

        # --------------------------------------------------
        # Fetch raw row
        # --------------------------------------------------
        result = await db.execute(
            select(SensorDataRaw).where(SensorDataRaw.id == raw_id)
        )
        raw = result.scalar_one_or_none()

        if not raw:
            return

        values = {
            "do": raw.do,
            "temperature": raw.temperature,
            "ph": raw.ph,
            "turbidity": raw.turbidity,
            "ammonia": raw.ammonia,
            "nitrate": raw.nitrate,
        }

        missing_fields = [k for k, v in values.items() if v is None]

        # ----------------------------------
        # Faulty sensor detection
        # Trigger alert when a metric is empty/out-of-range
        # for 5 consecutive rows.
        # ----------------------------------
        for key, value in values.items():
            if IngestionService._is_faulty_value(key, value):
                await IngestionService._check_and_raise_faulty_sensor_alert(
                    db=db,
                    raw=raw,
                    metric_key=key,
                )

        # ----------------------------------
        # STOP if more than one missing
        # ----------------------------------
        if len(missing_fields) > 1:
            await IngestionService._create_alert(
                db,
                raw.pond_id,
                "multiple_missing_values",
                "critical",
                f"Multiple missing values at {raw.timestamp}",
                raw.timestamp
            )
            return

        is_imputed = False
        quality_flag = "valid"

        # ----------------------------------
        # Handle single missing
        # ----------------------------------
        if len(missing_fields) == 1:
            field = missing_fields[0]
            imputed_value = IngestionService._impute_value(field, values)
            values[field] = imputed_value
            is_imputed = True
            quality_flag = "ml_imputed_single"

        # ----------------------------------
        # Hard range validation
        # ----------------------------------
        for key, value in values.items():
            min_v, max_v = RANGES[key]

            if value < min_v or value > max_v:
                imputed_value = IngestionService._impute_value(key, values)
                values[key] = imputed_value
                is_imputed = True
                quality_flag = "hard_range_corrected"

                await IngestionService._create_alert(
                    db,
                    raw.pond_id,
                    "hard_range_violation",
                    "high",
                    f"{key} out of range at {raw.timestamp}",
                    raw.timestamp
                )

        # ----------------------------------
        # Spike detection
        # ----------------------------------
        last_result = await db.execute(
            select(SensorDataClean)
            .where(SensorDataClean.pond_id == raw.pond_id)
            .order_by(desc(SensorDataClean.timestamp))
            .limit(1)
        )
        last_clean = last_result.scalar_one_or_none()

        if last_clean:
            for key in values:
                prev = getattr(last_clean, key)
                curr = values[key]

                if prev and prev != 0:
                    ratio = abs(curr - prev) / abs(prev)

                    if ratio > 0.3:
                        severity = (
                            "low" if ratio < 0.6
                            else "medium" if ratio < 1.0
                            else "high"
                        )

                        await IngestionService._create_alert(
                            db,
                            raw.pond_id,
                            "anomaly_detected",
                            severity,
                            f"{key} anomaly at {raw.timestamp}",
                            raw.timestamp
                        )

                        quality_flag = "anomaly_detected"

        # ----------------------------------
        # Insert clean row
        # ----------------------------------
        clean_row = SensorDataClean(
            id=uuid.uuid4(),
            pond_id=raw.pond_id,
            raw_id=raw.id,
            do=values["do"],
            temperature=values["temperature"],
            ph=values["ph"],
            turbidity=values["turbidity"],
            ammonia=values["ammonia"],
            nitrate=values["nitrate"],
            is_imputed=is_imputed,
            quality_flag=quality_flag,
            timestamp=raw.timestamp
        )

        db.add(clean_row)

        # --------------------------------------------------
        # 🔥 Backfill Forecast Actual Values
        # --------------------------------------------------
        forecast_result = await db.execute(
            select(ForecastLog)
            .where(
                ForecastLog.pond_id == raw.pond_id,
                ForecastLog.forecast_for == raw.timestamp
            )
        )

        forecast_entry = forecast_result.scalar_one_or_none()

        if forecast_entry:
            forecast_entry.actual_do = values["do"]
            forecast_entry.actual_temperature = values["temperature"]
            forecast_entry.actual_ph = values["ph"]
            forecast_entry.actual_turbidity = values["turbidity"]
            forecast_entry.actual_ammonia = values["ammonia"]
            forecast_entry.actual_nitrate = values["nitrate"]

            db.add(forecast_entry)

        # ❗ No commit here (Orchestrator handles commit)

    # ----------------------------
    # ML Imputation
    # ----------------------------
    @staticmethod
    def _impute_value(field, values):
        model = IMPUTE_MODELS[field]
        X = [[v for k, v in values.items() if k != field]]
        return float(model.predict(X)[0])

    # ----------------------------
    # Alert Creation
    # ----------------------------
    @staticmethod
    async def _create_alert(
        db,
        pond_id,
        alert_type,
        severity,
        message,
        event_timestamp
    ):
        alert = Alert(
            id=uuid.uuid4(),
            pond_id=pond_id,
            alert_type=alert_type,
            severity=severity,
            message=message,
            timestamp=event_timestamp,
            resolved=False
        )

        db.add(alert)

    @staticmethod
    def _is_faulty_value(metric_key: str, value) -> bool:
        if value is None:
            return True

        min_v, max_v = RANGES[metric_key]
        return value < min_v or value > max_v

    @staticmethod
    async def _check_and_raise_faulty_sensor_alert(
        db: AsyncSession,
        raw: SensorDataRaw,
        metric_key: str,
    ) -> None:
        previous_rows_result = await db.execute(
            select(SensorDataRaw)
            .where(
                SensorDataRaw.pond_id == raw.pond_id,
                SensorDataRaw.timestamp < raw.timestamp,
            )
            .order_by(desc(SensorDataRaw.timestamp))
            .limit(4)
        )
        previous_rows = previous_rows_result.scalars().all()

        if len(previous_rows) < 4:
            return

        if not all(
            IngestionService._is_faulty_value(metric_key, getattr(row, metric_key))
            for row in previous_rows
        ):
            return

        alert_message = (
            f"Faulty sensor suspected for {metric_key}: "
            "5 consecutive empty/out-of-range rows."
        )

        existing_alert_result = await db.execute(
            select(Alert)
            .where(
                Alert.pond_id == raw.pond_id,
                Alert.alert_type == "sensor_faulty_consecutive",
                Alert.message == alert_message,
                Alert.resolved.is_(False),
            )
            .order_by(desc(Alert.timestamp))
            .limit(1)
        )
        existing_alert = existing_alert_result.scalar_one_or_none()

        if existing_alert:
            return

        await IngestionService._create_alert(
            db=db,
            pond_id=raw.pond_id,
            alert_type="sensor_faulty_consecutive",
            severity="high",
            message=alert_message,
            event_timestamp=raw.timestamp,
        )