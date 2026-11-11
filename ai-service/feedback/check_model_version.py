import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DATABASE_PATH = BASE_DIR / "datasets" / "feedback.db"

prediction_id = input("Enter prediction ID: ").strip()

connection = sqlite3.connect(DATABASE_PATH)

cursor = connection.cursor()

cursor.execute("""
    SELECT
        prediction_id,
        predicted_result,
        delay_probability,
        model_version,
        predicted_at,
        record_type
    FROM predictions
    WHERE prediction_id = ?
""", (prediction_id,))

record = cursor.fetchone()

connection.close()

print("\nRefHealth AI")
print("PREDICTION MODEL VERSION CHECK")
print("=" * 45)

if record:

    print("Prediction ID:", record[0])
    print("Predicted Result:", record[1])
    print("Delay Probability:", record[2])
    print("Model Version:", record[3])
    print("Prediction Time:", record[4])
    print("Record Type:", record[5])

    print("\nDATABASE VERIFICATION SUCCESSFUL.")

else:

    print("\nPREDICTION RECORD NOT FOUND.")