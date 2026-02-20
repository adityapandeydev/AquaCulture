from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey
from sqlalchemy.sql import func

from app.core.database import Base


class WaterQualityLog(Base):

    __tablename__ = "water_quality_logs"

    id = Column(Integer, primary_key=True, index=True)

    pond_id = Column(Integer, ForeignKey("ponds.id"))

    do = Column(Float)

    temperature = Column(Float)

    ph = Column(Float)

    turbidity = Column(Float)

    ammonia = Column(Float)

    nitrate = Column(Float)

    manganese = Column(Float)

    timestamp = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )
