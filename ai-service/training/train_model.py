import pandas as pd
import joblib

from pathlib import Path

from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
from sklearn.pipeline import Pipeline

from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix
)


# Project paths
BASE_DIR = Path(__file__).resolve().parent.parent

DATASET_PATH = BASE_DIR / "datasets" / "raw" / "referrals.csv"

MODEL_PATH = BASE_DIR / "models" / "legacy_delay_training_candidate.joblib"


# 1. Load dataset
data = pd.read_csv(DATASET_PATH)

print("\nDATASET LOADED SUCCESSFULLY")
print(data.head())


# 2. Separate features and target
X = data.drop("delayed", axis=1)

y = data["delayed"]


# 3. Identify categorical and numerical columns
categorical_columns = [
    "hospital_workload",
    "submission_day"
]

numerical_columns = [
    "distance_km",
    "pending_referrals",
    "service_available",
    "submission_hour"
]


# 4. Preprocess categorical data
preprocessor = ColumnTransformer(
    transformers=[
        (
            "categorical",
            OneHotEncoder(handle_unknown="ignore"),
            categorical_columns
        )
    ],
    remainder="passthrough"
)


# 5. Create Random Forest model
random_forest = RandomForestClassifier(
    n_estimators=100,
    random_state=42,
    class_weight="balanced"
)


# 6. Combine preprocessing and model
model = Pipeline(
    steps=[
        ("preprocessor", preprocessor),
        ("classifier", random_forest)
    ]
)


# 7. Split dataset into training and testing data
X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=42,
    stratify=y
)


print("\nTRAINING DATA SIZE:", len(X_train))
print("TESTING DATA SIZE:", len(X_test))


# 8. Train the model
print("\nTRAINING RANDOM FOREST MODEL...")

model.fit(X_train, y_train)

print("MODEL TRAINING COMPLETED!")


# 9. Make predictions
predictions = model.predict(X_test)


# 10. Evaluate model
accuracy = accuracy_score(y_test, predictions)

print("\nMODEL ACCURACY:")
print(accuracy)

print("\nCLASSIFICATION REPORT:")
print(
    classification_report(
        y_test,
        predictions,
        zero_division=0
    )
)

print("\nCONFUSION MATRIX:")
print(confusion_matrix(y_test, predictions))


# 11. Save trained model
joblib.dump(model, MODEL_PATH)

print("\nMODEL SAVED SUCCESSFULLY!")
print(MODEL_PATH)
