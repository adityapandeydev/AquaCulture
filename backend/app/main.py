from fastapi import FastAPI

from app.api.routes.health_routes import router as health_router
from app.api.routes.auth_routes import router as auth_router
from app.api.routes.pond_routes import router as pond_router
from app.api.routes.sensor_routes import router as sensor_router
from app.api.routes.alert_routes import router as alert_router
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="AquaTech Backend",
    version="1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # later restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
app.include_router(sensor_router, prefix="/api/v1")
app.include_router(alert_router, prefix="/api/v1")