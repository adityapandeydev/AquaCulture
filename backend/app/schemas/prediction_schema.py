from pydantic import BaseModel


class PredictionResponse(BaseModel):

    water_forecast: list

    nitrogen_forecast: list
