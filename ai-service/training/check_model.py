import joblib
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

MODEL_PATH = BASE_DIR / "models" / "delay_prediction_model.joblib"

# Load the saved model
model = joblib.load(MODEL_PATH)

print("MODEL LOADED SUCCESSFULLY!")

print("\nMODEL INFORMATION:")
print(model)

print("\nMODEL CLASSES:")
print(model.classes_)