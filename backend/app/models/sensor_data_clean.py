import uuid
from sqlalchemy import Column, Float, DateTime, ForeignKey, Boolean, String, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.core.database import Base


class SensorDataClean(Base):

    __tablename__ = "sensor_data_clean"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    pond_id = Column(UUID(as_uuid=True), ForeignKey("ponds.id"), nullable=False)

    raw_id = Column(UUID(as_uuid=True), ForeignKey("sensor_data_raw.id"))

    do = Column(Float)
    temperature = Column(Float)
    ph = Column(Float)
    turbidity = Column(Float)
    ammonia = Column(Float)
    nitrate = Column(Float)

    is_imputed = Column(Boolean, default=False)
    quality_flag = Column(String)  
    # "valid", "spike_corrected", "model_imputed", "missing", etc.

    timestamp = Column(DateTime(timezone=True), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_clean_pond_timestamp", "pond_id", "timestamp"),
    )