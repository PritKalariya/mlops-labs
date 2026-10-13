from fastapi import FastAPI, status, HTTPException
from pydantic import BaseModel
from predict import predict_data


app = FastAPI()

class IrisData(BaseModel):
    """
    Pydantic BaseModel representing iris flower measurements.

    Attributes:
        petal_length (float): The length of the iris flower's petal in centimeters.
        sepal_length (float): The length of the iris flower's sepal in centimeters.
        petal_width (float): The width of the iris flower's petal in centimeters.
        sepal_width (float): The width of the iris flower's sepal in centimeters.
    """
    petal_length: float
    sepal_length: float
    petal_width: float
    sepal_width: float

class IrisResponse(BaseModel):
    response:int



"""Modern web apps use a technique named routing. This helps the user remember the URLs. 
For instance, instead of having /booking.php they see /booking/. Instead of /account.asp?id=1234/ 
they’d see /account/1234/."""

@app.get("/", status_code=status.HTTP_200_OK)
async def health_ping():
    """Concurrent (multiple tasks can run simultaneously)"""
    return {"status": "healthy"}

@app.post("/predict", response_model=IrisResponse)
async def predict_iris(iris_features: IrisData):
    """
    Predict the iris flower species based on provided features.
    This endpoint accepts iris flower measurements and returns the predicted species class.
    Args:
        iris_features (IrisData): An IrisData object containing:
            - sepal_length (float): Length of the sepal in cm
            - sepal_width (float): Width of the sepal in cm
            - petal_length (float): Length of the petal in cm
            - petal_width (float): Width of the petal in cm
    Returns:
        IrisResponse: A response object containing:
            - response (int): The predicted iris species class (0, 1, or 2)
    Raises:
        HTTPException: Returns a 500 status code with error details if prediction fails.
    Example:
        POST /predict
        {
            "sepal_length": 5.1,
            "sepal_width": 3.5,
            "petal_length": 1.4,
            "petal_width": 0.2
        }
        Response:
        {
            "response": 0
        }
    """
    try:
        features = [[iris_features.sepal_length, iris_features.sepal_width,
                    iris_features.petal_length, iris_features.petal_width]]

        prediction = predict_data(features)
        return IrisResponse(response=int(prediction[0]))
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    


    
