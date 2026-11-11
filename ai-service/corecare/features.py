"""One feature implementation for V6 training and next-day inference.

Prediction cutoff: after all measurements for record_date have been finalized.
Hospital identity is an explicit categorical feature, never a unique record ID.
"""
import numpy as np
import pandas as pd
from corecare.config import CLASSES

OPERATIONS = ["patient_volume", "incoming_referrals", "pending_referrals", "available_beds"]
ROLLING = ["patient_volume", "pending_referrals", "incoming_referrals", "available_beds"]
RAW_COLUMNS = ["hospital_id", "record_date", *OPERATIONS, "total_beds", "workload_level"]
CATEGORICAL = ["hospital_id", "workload_level", "previous_workload_level", "next_day_of_week"]
FEATURES = ["hospital_id", *OPERATIONS, "total_beds", "workload_level",
            "bed_occupancy_rate", "pending_per_bed", "referral_to_patient_ratio",
            *[f"previous_{c}" for c in OPERATIONS], "previous_workload_level",
            *[f"average_{n}day_{c}" for c in ROLLING for n in (3, 7)],
            "patient_volume_trend", "pending_referrals_trend", "next_day_of_week", "next_day_month"]
TARGET = "next_day_workload"


def validate_history(data):
    if data.empty or not set(RAW_COLUMNS).issubset(data.columns):
        raise ValueError("Daily history is empty or missing required columns.")
    if data.columns.duplicated().any() or data[RAW_COLUMNS].isna().any().any():
        raise ValueError("Daily history contains duplicate columns or missing values.")
    df = data.copy()
    df["record_date"] = pd.to_datetime(df["record_date"], errors="raise")
    if (df.record_date != df.record_date.dt.normalize()).any():
        raise ValueError("record_date must be a date, without a time.")
    if df.hospital_id.astype(str).str.strip().eq("").any():
        raise ValueError("hospital_id cannot be empty.")
    if df.duplicated(["hospital_id", "record_date"]).any():
        raise ValueError("Duplicate hospital/date records.")
    for col in [*OPERATIONS, "total_beds"]:
        values = pd.to_numeric(df[col], errors="raise")
        if not np.isfinite(values).all() or (values < 0).any() or (values % 1 != 0).any():
            raise ValueError(f"{col} must contain finite nonnegative integers.")
        df[col] = values
    if (df.total_beds <= 0).any() or (df.available_beds > df.total_beds).any():
        raise ValueError("Invalid bed capacity.")
    if not df.workload_level.isin(CLASSES).all():
        raise ValueError("Invalid workload label.")
    df = df.sort_values(["hospital_id", "record_date"]).reset_index(drop=True)
    gaps = df.groupby("hospital_id").record_date.diff().dropna()
    if (gaps != pd.Timedelta(days=1)).any():
        raise ValueError("Daily history must be consecutive within each hospital.")
    return df


def build_features(data, *, training=True):
    df = validate_history(data)
    grouped = df.groupby("hospital_id", sort=False)
    df["target_date"] = df.record_date + pd.Timedelta(days=1)
    if training:
        df[TARGET] = grouped.workload_level.shift(-1)
    df["bed_occupancy_rate"] = (df.total_beds - df.available_beds) / df.total_beds
    df["pending_per_bed"] = df.pending_referrals / df.total_beds
    df["referral_to_patient_ratio"] = df.incoming_referrals / df.patient_volume.clip(lower=1)
    for column in [*OPERATIONS, "workload_level"]:
        df[f"previous_{column}"] = grouped[column].shift(1)
    for column in ROLLING:
        for days in (3, 7):
            df[f"average_{days}day_{column}"] = grouped[column].transform(
                lambda values: values.rolling(days, min_periods=days).mean())
    for column in ["patient_volume", "pending_referrals"]:
        df[f"{column}_trend"] = df[column] - df[f"previous_{column}"]
    df["next_day_of_week"] = df.target_date.dt.day_name()
    df["next_day_month"] = df.target_date.dt.month
    return df.dropna(subset=FEATURES + ([TARGET] if training else [])).reset_index(drop=True)


def chronological_split(df, validation_start=None, train_fraction=.8):
    dates = sorted(df.record_date.unique())
    if len(dates) < 10:
        raise ValueError("At least ten feature dates are needed for chronological evaluation.")
    start = pd.Timestamp(validation_start) if validation_start else pd.Timestamp(dates[int(len(dates)*train_fraction)])
    # No training outcome reaches the first validation observation date.
    train = df[df.target_date < start].copy()
    validation = df[df.record_date >= start].copy()
    excluded = df[(df.record_date < start) & (df.target_date >= start)].copy()
    if train.empty or validation.empty or train.target_date.max() >= validation.record_date.min():
        raise ValueError("Invalid chronological split.")
    return train, validation, excluded


def inference_features(history, hospital_id, as_of_date):
    data = pd.DataFrame(history)
    if data.empty or "hospital_id" not in data:
        raise ValueError("At least seven consecutive daily records are required.")
    if set(data.hospital_id) != {hospital_id}:
        raise ValueError("History must belong only to the requested hospital.")
    if pd.to_datetime(data.record_date).max() != pd.Timestamp(as_of_date):
        raise ValueError("History must end at as_of_date; future or stale records are invalid.")
    result = build_features(data, training=False)
    row = result[result.record_date == pd.Timestamp(as_of_date)]
    if len(row) != 1:
        raise ValueError("At least seven consecutive daily records are required.")
    return row
