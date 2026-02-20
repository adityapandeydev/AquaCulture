from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func

from app.core.database import Base


class Pond(Base):

    __tablename__ = "ponds"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String, nullable=False)

    owner_id = Column(Integer, ForeignKey("users.id"))

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )
