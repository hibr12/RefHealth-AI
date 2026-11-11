import sqlite3
import json
import uuid

from pathlib import Path
from datetime import datetime, timezone


BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_PATH = BASE_DIR / "datasets" / "feedback.db"


def get_connection():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DATABASE_PATH)


def initialize_database():
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS predictions (
                prediction_id TEXT PRIMARY KEY,
                referral_data TEXT NOT NULL,
                predicted_result INTEGER NOT NULL,
                delay_probability REAL NOT NULL,
                model_version TEXT NOT NULL,
                predicted_at TEXT NOT NULL,
                actual_result INTEGER,
                outcome_recorded_at TEXT,
                record_type TEXT NOT NULL DEFAULT 'test'
            )
        """)

        # Check whether record_type already exists.
        cursor.execute("PRAGMA table_info(predictions)")
        columns = [column[1] for column in cursor.fetchall()]

        # Upgrade an older database if necessary.
        if "record_type" not in columns:
            cursor.execute("""
                ALTER TABLE predictions
                ADD COLUMN record_type TEXT NOT NULL DEFAULT 'test'
            """)

        connection.commit()

    finally:
        connection.close()


def save_prediction(
    referral_data,
    predicted_result,
    delay_probability,
    model_version,
    record_type="test"
):
    initialize_database()
    if predicted_result not in (0, 1):
        raise ValueError("predicted_result must be 0 or 1")

    if not 0 <= delay_probability <= 1:
        raise ValueError("delay_probability must be between 0 and 1")

    if record_type not in ("test", "real"):
        raise ValueError("record_type must be 'test' or 'real'")

    prediction_id = str(uuid.uuid4())

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO predictions (
                prediction_id,
                referral_data,
                predicted_result,
                delay_probability,
                model_version,
                predicted_at,
                record_type
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            prediction_id,
            json.dumps(referral_data),
            int(predicted_result),
            float(delay_probability),
            model_version,
            datetime.now(timezone.utc).isoformat(),
            record_type
        ))

        connection.commit()

    finally:
        connection.close()

    return prediction_id


def record_actual_outcome(prediction_id, actual_result):
    initialize_database()

    if actual_result not in (0, 1):
        raise ValueError("actual_result must be 0 or 1")

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            UPDATE predictions
            SET actual_result = ?,
                outcome_recorded_at = ?
            WHERE prediction_id = ?
            AND actual_result IS NULL
        """, (
            int(actual_result),
            datetime.now(timezone.utc).isoformat(),
            prediction_id
        ))

        updated_rows = cursor.rowcount

        connection.commit()

        return updated_rows == 1

    finally:
        connection.close()


