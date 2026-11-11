"""Paths are configurable so tests and integrations never need the live database."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def database_path():
    return Path(os.getenv("CORECARE_DATABASE", str(ROOT / "datasets/feedback.db")))


def model_directory():
    return Path(os.getenv("CORECARE_MODEL_DIR", str(ROOT / "models/managed")))


CLASSES = ["Low", "Medium", "High"]
DELAY_FEATURES = ["distance_km", "hospital_workload", "pending_referrals",
                  "service_available", "submission_hour", "submission_day"]
LIMITATION = "Experimental decision support; synthetic results are not evidence of real hospital performance."
