"""Additive SQLite storage. Existing prototype tables are preserved."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import sqlite3
import uuid
from corecare.config import database_path


def now():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connection():
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    try:
        with db:
            yield db
    finally:
        db.close()


def initialize():
    with connection() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS ai_predictions (
          prediction_id TEXT PRIMARY KEY, component TEXT NOT NULL,
          hospital_id TEXT, model_version TEXT NOT NULL, record_type TEXT NOT NULL,
          predicted_at TEXT NOT NULL, target_date TEXT, inputs TEXT NOT NULL, result TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS ai_outcomes (
          prediction_id TEXT PRIMARY KEY REFERENCES ai_predictions(prediction_id),
          payload TEXT NOT NULL, submitted_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
          verified_by TEXT, verified_at TEXT, evidence TEXT);
        CREATE TABLE IF NOT EXISTS daily_operations (
          record_id TEXT PRIMARY KEY, hospital_id TEXT NOT NULL, record_date TEXT NOT NULL,
          record_type TEXT NOT NULL, payload TEXT NOT NULL, received_at TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'pending', verified_by TEXT, verified_at TEXT, evidence TEXT,
          UNIQUE(hospital_id,record_date,record_type));
        CREATE TABLE IF NOT EXISTS model_versions (
          version TEXT PRIMARY KEY, component TEXT NOT NULL, artifact TEXT NOT NULL,
          sha256 TEXT NOT NULL, metadata TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS active_models (
          component TEXT PRIMARY KEY, version TEXT NOT NULL REFERENCES model_versions(version));
        CREATE TABLE IF NOT EXISTS model_events (
          event_id TEXT PRIMARY KEY, component TEXT NOT NULL, previous_version TEXT,
          version TEXT NOT NULL, action TEXT NOT NULL, reviewer TEXT NOT NULL, reason TEXT NOT NULL, at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS recommendation_selections (
          prediction_id TEXT PRIMARY KEY REFERENCES ai_predictions(prediction_id),
          hospital_id TEXT NOT NULL, referral_prediction_id TEXT NOT NULL REFERENCES ai_predictions(prediction_id), at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS ai_prediction_component_time ON ai_predictions(component,predicted_at);
        CREATE INDEX IF NOT EXISTS daily_verified ON daily_operations(record_type,status,record_date);
        CREATE TABLE IF NOT EXISTS referral_observations (
          observation_id TEXT PRIMARY KEY, hospital_id TEXT NOT NULL, record_type TEXT NOT NULL,
          source_reference TEXT NOT NULL, inputs TEXT NOT NULL, received_at TEXT NOT NULL,
          outcome TEXT, status TEXT NOT NULL DEFAULT 'awaiting_outcome',
          verified_by TEXT, verified_at TEXT, evidence TEXT,
          UNIQUE(hospital_id,record_type,source_reference));
        """)
        # Historical prototype records remain available under their original IDs.
        # They remain test data and their outcomes remain unverified after migration.
        legacy = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='predictions'").fetchone()
        if legacy:
            for row in db.execute("SELECT * FROM predictions").fetchall():
                inputs = json.loads(row["referral_data"])
                inputs["legacy_import"] = True
                result = {"prediction": row["predicted_result"], "delay_probability": row["delay_probability"], "model_version": row["model_version"]}
                db.execute("INSERT OR IGNORE INTO ai_predictions VALUES (?,?,?,?,?,?,?,?,?)",
                    (row["prediction_id"], "delay", inputs.get("hospital_id"), row["model_version"], "test",
                     row["predicted_at"], None, json.dumps(inputs), json.dumps(result)))
                if row["actual_result"] is not None:
                    db.execute("INSERT OR IGNORE INTO ai_outcomes(prediction_id,payload,submitted_at) VALUES (?,?,?)",
                        (row["prediction_id"], json.dumps({"actual_result": row["actual_result"], "legacy_import": True}), row["outcome_recorded_at"] or row["predicted_at"]))


def save_prediction(component, inputs, result, record_type="test", hospital_id=None, target_date=None):
    prediction_id = str(uuid.uuid4())
    with connection() as db:
        db.execute("INSERT INTO ai_predictions VALUES (?,?,?,?,?,?,?,?,?)",
                   (prediction_id, component, hospital_id, result["model_version"], record_type,
                    now(), target_date, json.dumps(inputs), json.dumps(result)))
    return prediction_id


def prediction(prediction_id):
    with connection() as db:
        row = db.execute("SELECT * FROM ai_predictions WHERE prediction_id=?", (prediction_id,)).fetchone()
    if row is None:
        raise LookupError("Prediction not found.")
    result = dict(row)
    for key in ("inputs", "result"):
        result[key] = json.loads(result[key])
    return result


def submit_outcome(prediction_id, payload):
    prediction(prediction_id)
    with connection() as db:
        try:
            db.execute("INSERT INTO ai_outcomes(prediction_id,payload,submitted_at) VALUES (?,?,?)",
                       (prediction_id, json.dumps(payload), now()))
        except sqlite3.IntegrityError as error:
            raise FileExistsError("An outcome already exists for this prediction.") from error


def verify_outcome(prediction_id, reviewer, evidence):
    if not reviewer.strip() or not evidence.strip():
        raise ValueError("Reviewer and evidence are required.")
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT * FROM ai_outcomes WHERE prediction_id=?", (prediction_id,)).fetchone()
        if not row:
            raise LookupError("Outcome not found.")
        if row["status"] != "pending":
            raise FileExistsError("Outcome has already been verified.")
        db.execute("UPDATE ai_outcomes SET status='verified',verified_by=?,verified_at=?,evidence=? WHERE prediction_id=?",
                   (reviewer, now(), evidence, prediction_id))


def save_daily(payload):
    identifier = str(uuid.uuid4())
    with connection() as db:
        try:
            db.execute("INSERT INTO daily_operations(record_id,hospital_id,record_date,record_type,payload,received_at) VALUES (?,?,?,?,?,?)",
                       (identifier, payload["hospital_id"], payload["record_date"], payload["record_type"], json.dumps(payload), now()))
        except sqlite3.IntegrityError as error:
            raise FileExistsError("Daily record already exists for this hospital, date and record type.") from error
    return identifier


def verify_daily(record_id, reviewer, evidence):
    if not reviewer.strip() or not evidence.strip():
        raise ValueError("Reviewer and evidence are required.")
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT * FROM daily_operations WHERE record_id=?", (record_id,)).fetchone()
        if not row:
            raise LookupError("Daily record not found.")
        if row["status"] != "pending":
            raise FileExistsError("Daily record has already been verified.")
        db.execute("UPDATE daily_operations SET status='verified',verified_by=?,verified_at=?,evidence=? WHERE record_id=?",
                   (reviewer, now(), evidence, record_id))
        # A verified completed day is also the observed outcome of matching forecasts.
        if row["record_type"] == "real":
            payload = json.loads(row["payload"])
            predictions = db.execute("SELECT prediction_id FROM ai_predictions WHERE component='workload' AND hospital_id=? AND target_date=? AND record_type='real'",
                                     (row["hospital_id"], row["record_date"])).fetchall()
            for prediction_row in predictions:
                identifier = prediction_row["prediction_id"]
                existing = db.execute("SELECT payload FROM ai_outcomes WHERE prediction_id=?", (identifier,)).fetchone()
                if existing and json.loads(existing["payload"])["actual_result"] != payload["workload_level"]:
                    raise ValueError("Daily workload conflicts with an existing forecast outcome; resolve the source records first.")
                actual = {"actual_result": payload["workload_level"], "target_date": row["record_date"], "source_reference": record_id}
                db.execute("""INSERT INTO ai_outcomes VALUES (?,?,?,'verified',?,?,?)
                  ON CONFLICT(prediction_id) DO UPDATE SET status='verified',verified_by=excluded.verified_by,
                  verified_at=excluded.verified_at,evidence=excluded.evidence""",
                  (identifier, json.dumps(actual), now(), reviewer, now(), evidence))


def verified_daily(hospital_id=None, end=None):
    query = "SELECT * FROM daily_operations WHERE status='verified' AND record_type='real'"
    args = []
    if hospital_id:
        query += " AND hospital_id=?"
        args.append(hospital_id)
    if end:
        query += " AND record_date<=?"
        args.append(str(end))
    with connection() as db:
        rows = db.execute(query + " ORDER BY hospital_id,record_date", args).fetchall()
    return [{**json.loads(row["payload"]), "record_id": row["record_id"], "verified_at": row["verified_at"]} for row in rows]


def verified_delay():
    with connection() as db:
        rows = db.execute("""SELECT p.*,o.payload,o.verified_at,o.verified_by FROM ai_predictions p
          JOIN ai_outcomes o USING(prediction_id)
          WHERE p.component='delay' AND p.record_type='real' AND o.status='verified'
          ORDER BY p.predicted_at,p.prediction_id""").fetchall()
    return [{**dict(row), "inputs": json.loads(row["inputs"]), "outcome": json.loads(row["payload"])} for row in rows]


def save_referral_observation(payload):
    identifier = str(uuid.uuid4())
    with connection() as db:
        try:
            db.execute("""INSERT INTO referral_observations
              (observation_id,hospital_id,record_type,source_reference,inputs,received_at)
              VALUES (?,?,?,?,?,?)""", (identifier, payload["hospital_id"], payload["record_type"],
                  payload["source_reference"], json.dumps(payload), now()))
        except sqlite3.IntegrityError as error:
            raise FileExistsError("Referral observation already exists for this hospital and source.") from error
    return identifier


def referral_observation(identifier):
    with connection() as db:
        row = db.execute("SELECT * FROM referral_observations WHERE observation_id=?", (identifier,)).fetchone()
    if row is None:
        raise LookupError("Referral observation not found.")
    return {**dict(row), "component": "delay", "inputs": json.loads(row["inputs"]),
            "outcome": json.loads(row["outcome"]) if row["outcome"] else None}


def submit_referral_outcome(identifier, payload):
    referral_observation(identifier)
    with connection() as db:
        changed = db.execute("""UPDATE referral_observations SET outcome=?,status='pending'
          WHERE observation_id=? AND status='awaiting_outcome'""", (json.dumps(payload), identifier))
        if changed.rowcount != 1:
            raise FileExistsError("An outcome already exists for this referral observation.")


def verify_referral_observation(identifier, reviewer, evidence):
    if not reviewer.strip() or not evidence.strip():
        raise ValueError("Reviewer and evidence are required.")
    record = referral_observation(identifier)
    if record["status"] == "awaiting_outcome":
        raise ValueError("Submit an observed referral outcome before verification.")
    with connection() as db:
        changed = db.execute("""UPDATE referral_observations SET status='verified',verified_by=?,
          verified_at=?,evidence=? WHERE observation_id=? AND status='pending'""",
          (reviewer, now(), evidence, identifier))
        if changed.rowcount != 1:
            raise FileExistsError("Referral observation has already been verified.")


def verified_referral_observations():
    with connection() as db:
        rows = db.execute("""SELECT * FROM referral_observations
          WHERE record_type='real' AND status='verified' ORDER BY received_at,observation_id""").fetchall()
    return [{**dict(row), "inputs": json.loads(row["inputs"]), "outcome": json.loads(row["outcome"]),
             "prediction_id": "observation:" + row["observation_id"]} for row in rows]
