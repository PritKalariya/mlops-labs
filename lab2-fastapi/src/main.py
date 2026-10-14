import logging
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, Request, status
from pydantic import BaseModel, ConfigDict, Field

from model_loader import Settings, load_model

logger = logging.getLogger("uvicorn.error")
SPECIES = ("setosa", "versicolor", "virginica")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings()
    app.state.loaded = load_model(settings)
    logger.info("loaded model %s from %s", app.state.loaded.version, settings.artifact_uri)
    yield


app = FastAPI(lifespan=lifespan)


class IrisData(BaseModel):
    """Iris flower measurements in centimeters."""
    model_config = ConfigDict(extra="forbid")

    sepal_length: float = Field(gt=0, le=30, description="cm")
    sepal_width: float = Field(gt=0, le=30, description="cm")
    petal_length: float = Field(gt=0, le=30, description="cm")
    petal_width: float = Field(gt=0, le=30, description="cm")


class IrisResponse(BaseModel):
    species_id: int = Field(ge=0, le=2)
    species: Literal["setosa", "versicolor", "virginica"]
    model_version: str


@app.get("/", status_code=status.HTTP_200_OK)
async def health_ping():
    return {"status": "healthy"}


@app.post("/predict", response_model=IrisResponse)
def predict_iris(iris_features: IrisData, request: Request):
    """Predict the iris species from four measurements."""
    loaded = request.app.state.loaded
    features = [[iris_features.sepal_length, iris_features.sepal_width,
                 iris_features.petal_length, iris_features.petal_width]]
    class_id = int(loaded.model.predict(features)[0])
    return IrisResponse(species_id=class_id, species=SPECIES[class_id],
                        model_version=loaded.version)
