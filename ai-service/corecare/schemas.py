from datetime import date, datetime, timezone, timedelta
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, AwareDatetime, model_validator

Workload = Literal["Low", "Medium", "High"]
RecordType = Literal["test", "real"]
LOCAL_TIME = timezone(timedelta(hours=3))


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class ReferralFeatures(StrictModel):
    distance_km: float = Field(ge=0)
    hospital_workload: Workload
    pending_referrals: int = Field(ge=0)
    service_available: Literal[0, 1]
    submission_hour: int = Field(ge=0, le=23)
    submission_day: Literal["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


class ReferralRequest(ReferralFeatures):
    hospital_id: str | None = None
    record_type: RecordType = "test"
    submitted_at: AwareDatetime | None = None
    feature_observed_at: AwareDatetime | None = None
    source_reference: str | None = None
    model_version: str | None = None

    @model_validator(mode="after")
    def real_provenance(self):
        if self.record_type == "real":
            if not all([self.hospital_id, self.submitted_at, self.feature_observed_at, self.source_reference]):
                raise ValueError("Real referrals require hospital_id, submitted_at, feature_observed_at and source_reference.")
            if self.feature_observed_at > self.submitted_at or self.submitted_at > datetime.now(timezone.utc):
                raise ValueError("Features must be observed by submission time; future submissions are invalid.")
            if self.submitted_at-self.feature_observed_at > timedelta(hours=2):
                raise ValueError("Operational features must be at most two hours old.")
            # Reject stale replay as prospective feedback. Backtests use record_type=test.
            if datetime.now(timezone.utc) - self.submitted_at > timedelta(minutes=15):
                raise ValueError("Real predictions must be requested within 15 minutes of submission.")
            local = self.submitted_at.astimezone(LOCAL_TIME)
            self.submission_hour = local.hour
            self.submission_day = local.strftime("%A")
        return self


class DailyMeasurements(StrictModel):
    hospital_id: str = Field(min_length=1)
    record_date: date
    patient_volume: int = Field(ge=0)
    incoming_referrals: int = Field(ge=0)
    pending_referrals: int = Field(ge=0)
    available_beds: int = Field(ge=0)
    total_beds: int = Field(gt=0)
    workload_level: Workload
    staff_on_duty: int | None = Field(default=None, ge=0)
    staffed_beds: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def beds(self):
        if self.available_beds > self.total_beds:
            raise ValueError("Available beds cannot exceed total beds.")
        if self.staffed_beds is not None and self.staffed_beds > self.total_beds:
            raise ValueError("Staffed beds cannot exceed total beds.")
        return self


class ReferralObservation(ReferralRequest):
    hospital_id: str = Field(min_length=1)
    source_reference: str = Field(min_length=1, max_length=500)
    model_version: None = None


class DailySubmission(DailyMeasurements):
    record_type: RecordType = "test"
    observed_at: AwareDatetime
    source_reference: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def finalized(self):
        if self.observed_at > datetime.now(timezone.utc):
            raise ValueError("Observation cannot be in the future.")
        if self.record_type == "real" and self.observed_at.astimezone(LOCAL_TIME).date() <= self.record_date:
            raise ValueError("Submit finalized daily measurements after the record day ends.")
        return self


class WorkloadRequest(StrictModel):
    hospital_id: str = Field(min_length=1)
    as_of_date: date
    record_type: RecordType = "test"
    history: list[DailyMeasurements] | None = Field(default=None, min_length=7, max_length=366)
    model_version: str | None = None


class OutcomeSubmission(StrictModel):
    actual_result: Literal[0, 1, "Low", "Medium", "High"]
    acknowledged_at: AwareDatetime | None = None
    observed_until: AwareDatetime | None = None
    target_date: date | None = None
    source_reference: str | None = None


class Verification(StrictModel):
    reviewer: str = Field(min_length=3, max_length=200)
    evidence: str = Field(min_length=5, max_length=2000)


class HospitalCandidate(StrictModel):
    hospital_id: str = Field(min_length=1)
    hospital_name: str = Field(min_length=1)
    service: str = Field(min_length=1)
    service_available: Literal[0, 1]
    available_beds: int = Field(ge=0)
    distance_km: float = Field(ge=0)
    hospital_workload: Workload
    pending_referrals: int = Field(ge=0)
    estimated_travel_minutes: float | None = Field(default=None, ge=0)


class RecommendationRequest(StrictModel):
    required_service: str = Field(min_length=1)
    record_type: RecordType = "test"
    submitted_at: AwareDatetime
    candidates: list[HospitalCandidate] | None = Field(default=None, min_length=1, max_length=100)
    operational_snapshot_at: AwareDatetime | None = None
    source_reference: str | None = None
    workload_as_of_date: date | None = None
    delay_model_version: str | None = None
    workload_model_version: str | None = None


class Selection(StrictModel):
    hospital_id: str
    referral_prediction_id: str


class Promotion(Verification):
    allow_experimental: bool = False
