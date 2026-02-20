from fastapi import FastAPI

from app.api.routes.health_routes import router as health_router
from app.api.routes.auth_routes import router as auth_router
from app.api.routes.pond_routes import router as pond_router
from app.api.routes.water_quality_routes import router as water_router
from app.api.routes.prediction_routes import router as prediction_router

app = FastAPI(
    title="AquaTech Backend",
    version="1.0"
)


app.include_router(
    health_router,
    prefix="/api/v1"
)

app.include_router(
    auth_router,
    prefix="/api/v1"
)


@app.get("/")
async def root():

    return {
        "message": "AquaTech API Running"
    }

app.include_router(health_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(pond_router, prefix="/api/v1")
app.include_router(water_router, prefix="/api/v1")
app.include_router(prediction_router, prefix="/api/v1")
