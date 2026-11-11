"""Unified AI API; run python -m uvicorn main:app --host 127.0.0.1."""
from contextlib import asynccontextmanager
import hmac
import logging
import os
import sqlite3
from fastapi import FastAPI, Depends, Header, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from corecare import storage, registry, inference, monitoring
from corecare.schemas import (ReferralRequest, WorkloadRequest, DailySubmission, OutcomeSubmission,
                              Verification, RecommendationRequest, Selection, ReferralObservation)
from prediction.workload_api import WorkloadPredictionRequest
from prediction.workload_predict import predict_hospital_workload
from recommendation.hospital_recommender import recommend, record_selection

logger = logging.getLogger("corecare")


def check_api_key(x_api_key: str | None = Header(default=None)):
    expected = os.getenv("CORECARE_API_KEY")
    if expected and not hmac.compare_digest(x_api_key or "", expected):
        raise HTTPException(401, "Invalid service API key.")


def require_admin(x_admin_token: str | None = Header(default=None)):
    expected = os.getenv("CORECARE_ADMIN_TOKEN")
    if not expected:
        raise HTTPException(503, "Set CORECARE_ADMIN_TOKEN before verification operations.")
    if not hmac.compare_digest(x_admin_token or "", expected):
        raise HTTPException(403, "Administrator token required.")


def require_real_configuration(record_type):
    if record_type == "real" and not os.getenv("CORECARE_API_KEY"):
        raise HTTPException(503, "Configure CORECARE_API_KEY before collecting real operational data.")


@asynccontextmanager
async def lifespan(app):
    storage.initialize()
    registry.adopt_legacy()
    yield


app = FastAPI(title="RefHealth AI", version="2.0.0",
    description="Experimental referral coordination and hospital operations decision support.",
    lifespan=lifespan, dependencies=[Depends(check_api_key)])

from corecare.integration import router as integration_router
app.include_router(integration_router)


@app.exception_handler(RequestValidationError)
async def validation_error(request, error):
    details = [{"field": ".".join(str(x) for x in e["loc"]), "message": e["msg"]} for e in error.errors()]
    return JSONResponse(status_code=422, content={"success": False, "error": {"code": "validation_error", "details": details}})


@app.exception_handler(HTTPException)
async def http_error(request, error):
    return JSONResponse(status_code=error.status_code, content={"success": False, "error": {"message": error.detail}})


@app.exception_handler(Exception)
async def unexpected_error(request, error):
    logger.exception("AI request failed", exc_info=error)
    return JSONResponse(status_code=500, content={"success": False, "error": {"code": "internal_error", "message": "Request failed; consult service logs."}})


def execute(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except FileExistsError as error:
        raise HTTPException(409, str(error)) from error
    except FileNotFoundError as error:
        raise HTTPException(503, "Required model or data file is unavailable.") from error
    except LookupError as error:
        message = str(error)
        raise HTTPException(503 if "model found" in message else 404, message) from error
    except (ValueError, TypeError) as error:
        raise HTTPException(422, str(error)) from error
    except RuntimeError as error:
        raise HTTPException(503, str(error)) from error
    except sqlite3.Error as error:
        logger.exception("Database operation failed")
        raise HTTPException(503, "Prediction storage is unavailable.") from error


@app.get("/")
def home():
    return {"success": True, "message": "RefHealth AI", "version": "2.0.0", "docs": "/docs"}


@app.get("/health")
def health():
    result = monitoring.health()
    return JSONResponse(status_code=503 if result["status"] == "unhealthy" else 200,
                        content={"success": result["status"] != "unhealthy", **result})


@app.get("/models")
def models():
    return {"success": True, "data": registry.catalog()}


@app.post("/predict/delay")
def predict_delay(request: ReferralRequest):
    require_real_configuration(request.record_type)
    return execute(inference.predict_delay, request)


@app.post("/predict/workload")
def legacy_workload(request: WorkloadPredictionRequest):
    execute(inference.check_hospital, request.hospital_id)
    data = request.model_dump()
    result = execute(predict_hospital_workload, data)
    identifier = execute(storage.save_prediction, "workload_legacy", data, result, hospital_id=request.hospital_id)
    return {"success": True, "prediction_id": identifier, **result, "data": result,
            "notice": "Legacy demonstration schema; use /predict/workload/next-day for V6 and real daily history."}


@app.post("/predict/workload/next-day")
def next_day_workload(request: WorkloadRequest):
    require_real_configuration(request.record_type)
    return execute(inference.predict_workload, request)


@app.post("/recommendations")
def recommendations(request: RecommendationRequest):
    require_real_configuration(request.record_type)
    return execute(recommend, request)


@app.post("/recommendations/{prediction_id}/selection")
def selection(prediction_id: str, request: Selection):
    execute(record_selection, prediction_id, request)
    return {"success": True, "prediction_id": prediction_id, "data": request.model_dump()}


@app.post("/feedback/{prediction_id}/outcome")
def outcome(prediction_id: str, request: OutcomeSubmission):
    payload = execute(inference.validate_outcome, prediction_id, request)
    execute(storage.submit_outcome, prediction_id, payload)
    return {"success": True, "prediction_id": prediction_id, "actual_result": request.actual_result, "status": "pending_verification"}


@app.post("/feedback/{prediction_id}/verify", dependencies=[Depends(require_admin)])
def verify_outcome(prediction_id: str, request: Verification):
    execute(storage.verify_outcome, prediction_id, request.reviewer, request.evidence)
    return {"success": True, "prediction_id": prediction_id, "status": "verified"}


@app.post("/operations/daily")
def daily(request: DailySubmission):
    require_real_configuration(request.record_type)
    execute(inference.check_hospital, request.hospital_id)
    identifier = execute(storage.save_daily, request.model_dump(mode="json"))
    return {"success": True, "record_id": identifier, "status": "pending_verification"}


@app.post("/operations/daily/{record_id}/verify", dependencies=[Depends(require_admin)])
def verify_daily(record_id: str, request: Verification):
    execute(storage.verify_daily, record_id, request.reviewer, request.evidence)
    return {"success": True, "record_id": record_id, "status": "verified"}


@app.get("/monitoring", dependencies=[Depends(require_admin)])
def monitor():
    return {"success": True, "data": execute(monitoring.monitoring_report)}


@app.post("/operations/referrals")
def referral_observation(request: ReferralObservation):
    require_real_configuration(request.record_type)
    execute(inference.check_hospital, request.hospital_id)
    identifier = execute(storage.save_referral_observation, request.model_dump(mode="json"))
    return {"success": True, "observation_id": identifier, "status": "awaiting_outcome"}


@app.post("/operations/referrals/{observation_id}/outcome")
def referral_observation_outcome(observation_id: str, request: OutcomeSubmission):
    record = execute(storage.referral_observation, observation_id)
    payload = execute(inference.validate_record_outcome, record, request)
    execute(storage.submit_referral_outcome, observation_id, payload)
    return {"success": True, "observation_id": observation_id, "status": "pending_verification"}


@app.post("/operations/referrals/{observation_id}/verify", dependencies=[Depends(require_admin)])
def verify_referral_observation(observation_id: str, request: Verification):
    execute(storage.verify_referral_observation, observation_id, request.reviewer, request.evidence)
    return {"success": True, "observation_id": observation_id, "status": "verified"}


@app.get("/learning/status", dependencies=[Depends(require_admin)])
def learning_status():
    from training.learning_cycle import readiness
    return {"success": True, "data": execute(readiness)}
