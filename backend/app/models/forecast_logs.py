import uuid
from sqlalchemy import Column, Float, DateTime, ForeignKey, Integer, String, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.core.database import Base


class ForecastLog(Base):

    __tablename__ = "forecast_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    pond_id = Column(UUID(as_uuid=True), ForeignKey("ponds.id"), nullable=False)

    forecast_block_start = Column(DateTime(timezone=True), nullable=False)

    forecast_for = Column(DateTime(timezone=True), nullable=False)

    horizon_step = Column(Integer, nullable=False)

    # Predicted values
    pred_do = Column(Float)
    pred_temperature = Column(Float)
    pred_ph = Column(Float)
    pred_turbidity = Column(Float)
    pred_ammonia = Column(Float)
    pred_nitrate = Column(Float)

    # Actual values (filled later)
    actual_do = Column(Float)
    actual_temperature = Column(Float)
    actual_ph = Column(Float)
    actual_turbidity = Column(Float)
    actual_ammonia = Column(Float)
    actual_nitrate = Column(Float)

    risk_state = Column(String)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_forecast_pond_time", "pond_id", "forecast_for"),
    )