import json
import joblib

from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent

MODEL_DIR = BASE_DIR / "models"

ACTIVE_MODEL_PATH = (
    MODEL_DIR / "workload_prediction_tuned_candidate.joblib"
)

METADATA_PATH = (
    MODEL_DIR / "workload_model_metadata.json"
)


# Cached model information
_cached_model = None
_cached_model_version = None
_cached_modified_time = None


def get_active_workload_model():

    global _cached_model
    global _cached_model_version
    global _cached_modified_time

    if not ACTIVE_MODEL_PATH.exists():

        raise FileNotFoundError(
            "Active workload prediction model not found."
        )

    modified_time = ACTIVE_MODEL_PATH.stat().st_mtime

    # Read model metadata
    if METADATA_PATH.exists():

        with open(
            METADATA_PATH,
            "r",
            encoding="utf-8"
        ) as file:

            metadata = json.load(file)

        model_version = metadata.get(
            "model_version",
            "workload_random_forest_tuned_v1"
        )

    else:

        model_version = "workload_random_forest_tuned_v1"

    # Reload model when necessary
    if (
        _cached_model is None
        or _cached_modified_time != modified_time
        or _cached_model_version != model_version
    ):

        print("\nLOADING ACTIVE WORKLOAD MODEL...")

        _cached_model = joblib.load(
            ACTIVE_MODEL_PATH
        )

        _cached_modified_time = modified_time

        _cached_model_version = model_version

        print(
            "WORKLOAD MODEL LOADED:",
            model_version
        )

    return _cached_model, _cached_model_version