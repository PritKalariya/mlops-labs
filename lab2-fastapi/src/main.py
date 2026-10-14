from typing import Literal

from fastapi import FastAPI, status, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from predict import predict_data


app = FastAPI()

SPECIES = ("setosa", "versicolor", "virginica")


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


@app.get("/", status_code=status.HTTP_200_OK)
async def health_ping():
    return {"status": "healthy"}


@app.post("/predict", response_model=IrisResponse)
async def predict_iris(iris_features: IrisData):
    """Predict the iris species from four measurements."""
    try:
        features = [[iris_features.sepal_length, iris_features.sepal_width,
                     iris_features.petal_length, iris_features.petal_width]]

        prediction = predict_data(features)
        class_id = int(prediction[0])
        return IrisResponse(species_id=class_id, species=SPECIES[class_id])

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
