from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, model_validator

from prediction.workload_predict import (
    predict_hospital_workload
)


router = APIRouter()


class WorkloadPredictionRequest(BaseModel):

    hospital_id: str = Field(min_length=1)

    day_of_week: Literal[
        "Monday", "Tuesday", "Wednesday",
        "Thursday", "Friday", "Saturday", "Sunday"
    ]

    workload_level: Literal["Low", "Medium", "High"]

    patient_volume: int = Field(ge=0)

    incoming_referrals: int = Field(ge=0)

    pending_referrals: int = Field(ge=0)

    available_beds: int = Field(ge=0)

    total_beds: int = Field(ge=1)

    previous_patient_volume: int = Field(ge=0)

    previous_pending_referrals: int = Field(ge=0)

    previous_available_beds: int = Field(ge=0)

    previous_workload_level: Literal[
        "Low", "Medium", "High"
    ]

    average_3day_patient_volume: float = Field(ge=0)

    average_3day_pending_referrals: float = Field(ge=0)

    @model_validator(mode="after")
    def validate_bed_capacity(self):

        if self.available_beds > self.total_beds:

            raise ValueError(
                "Available beds cannot exceed total beds."
            )

        if self.previous_available_beds > self.total_beds:

            raise ValueError(
                "Previous available beds cannot exceed total beds."
            )

        return self


@router.post("/predict/workload")
def predict_workload(
    request: WorkloadPredictionRequest
):

    try:

        hospital_data = request.model_dump()

        result = predict_hospital_workload(
            hospital_data
        )

        return result

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=str(error)
        )