"""Immutable model artifacts with explicit approval and auditable rollback."""
import hashlib
import importlib.metadata
import json
import os
import uuid
from pathlib import Path
import joblib
from corecare.config import ROOT, model_directory
from corecare.storage import connection, now


def register(model, component, metadata, version=None):
    version = version or f"{component}-{uuid.uuid4().hex[:16]}"
    if not version.replace("-", "").replace("_", "").isalnum():
        raise ValueError("Invalid model version.")
    directory = model_directory().resolve()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{version}.joblib"
    # Exclusive creation prevents overwriting any registered or unregistered artifact.
    with path.open("xb") as file:
        joblib.dump(model, file)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    metadata = {**metadata, "version": version, "component": component,
                "packages": {p: importlib.metadata.version(p) for p in ("scikit-learn", "pandas", "numpy", "joblib")}}
    source = hashlib.sha256()
    for folder in ("corecare", "training"):
        for file in sorted((ROOT / folder).glob("*.py")):
            source.update(str(file.relative_to(ROOT)).encode())
            source.update(file.read_bytes())
    metadata["source_sha256"] = source.hexdigest()
    with connection() as db:
        db.execute("INSERT INTO model_versions VALUES (?,?,?,?,?,?)",
                   (version, component, str(path), digest, json.dumps(metadata, allow_nan=False), now()))
    return version


def catalog():
    with connection() as db:
        rows = db.execute("""SELECT v.*, a.version IS NOT NULL AS active FROM model_versions v
          LEFT JOIN active_models a ON v.version=a.version ORDER BY v.created_at""").fetchall()
    return [{"version": r["version"], "component": r["component"], "active": bool(r["active"]),
             "sha256": r["sha256"], "created_at": r["created_at"], "metadata": json.loads(r["metadata"])} for r in rows]


def load(component, version=None):
    with connection() as db:
        if version is None:
            row = db.execute("SELECT v.* FROM model_versions v JOIN active_models a ON v.version=a.version WHERE a.component=?", (component,)).fetchone()
        else:
            row = db.execute("SELECT * FROM model_versions WHERE component=? AND version=?", (component, version)).fetchone()
    if not row:
        raise LookupError(f"No {'active ' if version is None else ''}{component} model found.")
    path = Path(row["artifact"])
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != row["sha256"]:
        raise RuntimeError("Model artifact missing or checksum mismatch.")
    return joblib.load(path), json.loads(row["metadata"])


def active_version(component):
    with connection() as db:
        row = db.execute("SELECT version FROM active_models WHERE component=?", (component,)).fetchone()
    return row["version"] if row else None


def adopt_legacy():
    # Copy the already served models once; never activate a newly trained candidate.
    definitions = [("delay", "delay_prediction_model.joblib", "legacy-delay-v1"),
                   ("workload_legacy", "workload_prediction_feature_engineered_tuned_candidate.joblib", "legacy-workload-v1")]
    for component, filename, version in definitions:
        if active_version(component):
            continue
        with connection() as db:
            exists = db.execute("SELECT 1 FROM model_versions WHERE version=?", (version,)).fetchone()
        if not exists:
            path = ROOT / "models" / filename
            if not path.exists():
                continue
            model = joblib.load(path)
            register(model, component, {"status": "legacy_experimental", "data_source": "synthetic",
                    "features": list(model.feature_names_in_), "known_hospitals": [f"H00{i}" for i in range(1, 6)],
                    "calibrated": False, "source_file": filename, "promotion_eligible": False}, version)
        with connection() as db:
            db.execute("INSERT OR IGNORE INTO active_models VALUES (?,?)", (component, version))


def promote(component, version, reviewer, reason, *, allow_experimental=False):
    if not reviewer.strip() or not reason.strip():
        raise ValueError("Reviewer and approval reason are required.")
    _, metadata = load(component, version)
    experimental = metadata.get("data_source") != "verified_real"
    if experimental and not allow_experimental:
        raise ValueError("Synthetic candidates require explicit experimental approval.")
    if not metadata.get("evaluation"):
        raise ValueError("Candidate has no evaluation report.")
    if not metadata.get("promotion_eligible", False):
        raise ValueError("Candidate did not meet the documented evaluation gates.")
    # Recheck current policy, including old candidates, rather than trusting a stored flag.
    from corecare.evaluation import promotion_checks
    from corecare.config import CLASSES
    classes = CLASSES if component == "workload" else [0, 1]
    try:
        current_gates = promotion_checks(metadata["evaluation"], classes,
                                        "High" if component == "workload" else 1, True)
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("Candidate needs a complete evaluation under current promotion gates.") from error
    if not current_gates["passed"]:
        raise ValueError("Candidate fails current promotion gates: " + ", ".join(current_gates["failure_reasons"]))
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT version FROM active_models WHERE component=?", (component,)).fetchone()
        previous = row["version"] if row else None
        if previous != metadata.get("compared_active_version"):
            raise ValueError("Active model changed since evaluation; compare the candidate again.")
        db.execute("INSERT INTO active_models VALUES (?,?) ON CONFLICT(component) DO UPDATE SET version=excluded.version", (component, version))
        db.execute("INSERT INTO model_events VALUES (?,?,?,?,?,?,?,?)",
                   (str(uuid.uuid4()), component, previous, version, "promote", reviewer, reason, now()))


def rollback(component, reviewer, reason):
    if not reviewer.strip() or not reason.strip():
        raise ValueError("Reviewer and rollback reason are required.")
    current = active_version(component)
    with connection() as db:
        event = db.execute("SELECT * FROM model_events WHERE component=? AND version=? AND action='promote' ORDER BY at DESC LIMIT 1", (component, current)).fetchone()
    if not event or not event["previous_version"]:
        raise ValueError("No previous approved model is available for rollback.")
    previous = event["previous_version"]
    load(component, previous)
    with connection() as db:
        changed = db.execute("UPDATE active_models SET version=? WHERE component=? AND version=?", (previous, component, current))
        if changed.rowcount != 1:
            raise ValueError("Active model changed during rollback; review the current version.")
        db.execute("INSERT INTO model_events VALUES (?,?,?,?,?,?,?,?)", (str(uuid.uuid4()), component, current, previous, "rollback", reviewer, reason, now()))
    return previous
