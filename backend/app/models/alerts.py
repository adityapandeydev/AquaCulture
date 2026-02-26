import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.core.database import Base


class Alert(Base):

    __tablename__ = "alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    pond_id = Column(UUID(as_uuid=True), ForeignKey("ponds.id"), nullable=False)

    alert_type = Column(String)  
    # "missing_data", "sensor_spike", "risk", "model_failure"

    severity = Column(String)  
    # "low", "medium", "high"

    message = Column(String)

    timestamp = Column(DateTime(timezone=True), nullable=False)

    resolved = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_alerts_pond_time", "pond_id", "timestamp"),
    )