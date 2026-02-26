import uuid
from sqlalchemy import Column, Float, DateTime, ForeignKey, Index, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.core.database import Base


class SensorDataRaw(Base):

    __tablename__ = "sensor_data_raw"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    pond_id = Column(UUID(as_uuid=True), ForeignKey("ponds.id"), nullable=False)

    do = Column(Float)
    temperature = Column(Float)
    ph = Column(Float)
    turbidity = Column(Float)
    ammonia = Column(Float)
    nitrate = Column(Float)

    timestamp = Column(DateTime(timezone=True), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    is_processed = Column(Boolean, default=False)

    __table_args__ = (
        Index("idx_raw_pond_timestamp", "pond_id", "timestamp"),
    )