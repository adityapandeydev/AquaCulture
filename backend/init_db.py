import asyncio

from app.core.database import engine, Base

# IMPORTANT: import all models here
from app.models.user import User
from app.models.pond import Pond
from app.models.water_quality_log import WaterQualityLog


async def init():

    async with engine.begin() as conn:

        await conn.run_sync(Base.metadata.create_all)

    print("All tables created successfully.")


asyncio.run(init())
