import pandas as pd
from pathlib import Path
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer

# Project directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Dataset path
DATASET_PATH = BASE_DIR / "datasets" / "raw" / "referrals.csv"

# Load dataset
data = pd.read_csv(DATASET_PATH)

print("\nORIGINAL DATASET")
print(data.head())

# Separate input features and target
X = data.drop("delayed", axis=1)
y = data["delayed"]

# Identify categorical and numerical columns
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

# Create preprocessing transformer
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

# Transform input features
X_processed = preprocessor.fit_transform(X)

# Convert transformed data into a DataFrame
feature_names = preprocessor.get_feature_names_out()

X_processed = pd.DataFrame(
    X_processed,
    columns=feature_names
)

print("\nPROCESSED DATASET")
print(X_processed.head())

print("\nTARGET VARIABLE")
print(y.head())

print("\nPROCESSED DATASET SHAPE")
print(X_processed.shape)

# Save processed dataset
X_processed.to_csv(
    BASE_DIR / "datasets" / "processed" / "X_processed.csv",
    index=False
)

y.to_csv(
    BASE_DIR / "datasets" / "processed" / "y.csv",
    index=False
)

print("\nDATA PREPROCESSING COMPLETED SUCCESSFULLY!")