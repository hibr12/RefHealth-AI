import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DATASET_PATH = (
    BASE_DIR
    / "datasets"
    / "raw"
    / "hospital_daily_history_v4.csv"
)

df = pd.read_csv(DATASET_PATH)

print("\nRefHealth AI")
print("V4 DATASET QUALITY VALIDATION")
print("=" * 65)

# 1. Dataset dimensions
print("\n1. DATASET SHAPE")
print(df.shape)

# 2. Missing values
print("\n2. MISSING VALUES")
print(df.isnull().sum())

# 3. Duplicate records
print("\n3. DUPLICATE RECORDS")
print("Duplicate rows:", df.duplicated().sum())

print(
    "Duplicate record IDs:",
    df["record_id"].duplicated().sum()
)

# 4. Negative numerical values
print("\n4. NEGATIVE NUMERICAL VALUES")

numeric_columns = df.select_dtypes(
    include="number"
).columns

for column in numeric_columns:
    print(
        f"{column}:",
        (df[column] < 0).sum()
    )

# 5. Bed validation
print("\n5. BED VALIDATION")

invalid_beds = (
    (df["available_beds"] > df["total_beds"])
    | (df["available_beds"] < 0)
    | (df["total_beds"] <= 0)
).sum()

print("Invalid bed records:", invalid_beds)

# 6. Hospital coverage
print("\n6. RECORDS PER HOSPITAL")

print(df.groupby("hospital_id").size().to_string())

# 7. Overall workload distribution
print("\n7. OVERALL WORKLOAD DISTRIBUTION")

counts = df["workload_level"].value_counts()

percentages = (
    df["workload_level"]
    .value_counts(normalize=True)
    * 100
)

print(
    pd.DataFrame({
        "records": counts,
        "percentage": percentages.round(2)
    }).to_string()
)

# 8. Workload distribution by hospital
print("\n8. WORKLOAD DISTRIBUTION BY HOSPITAL")

print(
    pd.crosstab(
        df["hospital_id"],
        df["workload_level"]
    ).to_string()
)

# 9. Operational statistics
print("\n9. OPERATIONAL STATISTICS")

print(
    df.groupby("hospital_id")[
        [
            "patient_volume",
            "incoming_referrals",
            "pending_referrals",
            "available_beds",
            "total_beds"
        ]
    ]
    .mean()
    .round(2)
    .to_string()
)

# 10. Workload transition analysis
print("\n10. WORKLOAD TRANSITIONS")

df = df.sort_values(
    ["hospital_id", "record_date"]
)

df["next_workload"] = (
    df.groupby("hospital_id")["workload_level"]
    .shift(-1)
)

transitions = pd.crosstab(
    df["workload_level"],
    df["next_workload"],
    normalize="index"
) * 100

print(transitions.round(2).to_string())

# 11. Date coverage
print("\n11. DATE COVERAGE")

df["record_date"] = pd.to_datetime(
    df["record_date"]
)

print("Start:", df["record_date"].min())
print("End:", df["record_date"].max())

print("\nVALIDATION COMPLETED.")