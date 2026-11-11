import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DATASET_PATH = (
    BASE_DIR
    / "datasets"
    / "raw"
    / "hospital_daily_history_v3.csv"
)

df = pd.read_csv(DATASET_PATH)

print("\nRefHealth AI")
print("V3 DATASET QUALITY VALIDATION")
print("=" * 65)

# 1. Dataset dimensions
print("\n1. DATASET SHAPE")
print(df.shape)

# 2. Missing values
print("\n2. MISSING VALUES")
print(df.isnull().sum())

# 3. Duplicate records
print("\n3. DUPLICATE RECORDS")
print(df.duplicated().sum())

# 4. Negative numerical values
print("\n4. NEGATIVE NUMERICAL VALUES")

numeric_columns = df.select_dtypes(
    include="number"
).columns

for column in numeric_columns:
    negative_count = (df[column] < 0).sum()
    print(f"{column}: {negative_count}")

# 5. Bed availability validation
print("\n5. BED AVAILABILITY VALIDATION")

invalid_beds = (
    (df["available_beds"] > df["total_beds"])
    | (df["available_beds"] < 0)
).sum()

print("Invalid bed records:", invalid_beds)

# 6. Hospital record distribution
print("\n6. RECORDS PER HOSPITAL")

print(
    df.groupby("hospital_id")
    .size()
    .to_string()
)

# 7. Workload distribution
print("\n7. WORKLOAD DISTRIBUTION")

workload_counts = df["workload_level"].value_counts()

workload_percentages = (
    df["workload_level"]
    .value_counts(normalize=True)
    * 100
)

distribution = pd.DataFrame({
    "records": workload_counts,
    "percentage": workload_percentages.round(2)
})

print(distribution.to_string())

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

# 10. Date coverage
print("\n10. DATE COVERAGE")

df["record_date"] = pd.to_datetime(df["record_date"])

print("Start date:", df["record_date"].min())
print("End date:", df["record_date"].max())

print("\nVALIDATION COMPLETED.")