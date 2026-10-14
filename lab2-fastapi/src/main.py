import logging
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
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


app = FastAPI(title="Iris API", version="1.0.0", lifespan=lifespan)


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


class ReadyResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    model_version: str | None = None


class ErrorResponse(BaseModel):
    detail: str


def get_loaded(request: Request):
    return getattr(request.app.state, "loaded", None)


@app.get("/health/live")
async def live():
    """Process is up. Says nothing about the model."""
    return {"status": "alive"}


@app.get("/health/ready", response_model=ReadyResponse,
         responses={503: {"model": ReadyResponse, "description": "Model not loaded"}})
async def ready(request: Request):
    """Ready to serve predictions."""
    loaded = get_loaded(request)
    if loaded is None:
        return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            content={"status": "not_ready", "model_version": None})
    return ReadyResponse(status="ready", model_version=loaded.version)


@app.post("/v1/predict", response_model=IrisResponse,
          responses={503: {"model": ErrorResponse, "description": "Model not loaded"}})
def predict_iris(iris_features: IrisData, request: Request):
    """Predict the iris species from four measurements."""
    loaded = get_loaded(request)
    if loaded is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="model not loaded")
    features = [[iris_features.sepal_length, iris_features.sepal_width,
                 iris_features.petal_length, iris_features.petal_width]]
    class_id = int(loaded.model.predict(features)[0])
    return IrisResponse(species_id=class_id, species=SPECIES[class_id],
                        model_version=loaded.version)
