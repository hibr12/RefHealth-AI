"""Reproducible candidate experiments. This module never promotes a model."""
import hashlib
import json
from pathlib import Path
import uuid
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier, ExtraTreesClassifier, HistGradientBoostingClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score, log_loss
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from corecare.config import ROOT, CLASSES, DELAY_FEATURES
from corecare.features import FEATURES, CATEGORICAL, TARGET, build_features, chronological_split
from corecare import registry
from corecare.evidence import training_profile
from corecare.evaluation import critical_events, promotion_checks


def pipeline(classifier, categorical, features):
    preprocessor = ColumnTransformer([
        ("categorical", OneHotEncoder(handle_unknown="ignore", sparse_output=False), categorical),
        ("numeric", StandardScaler(), [c for c in features if c not in categorical])])
    return Pipeline([("preprocessor", preprocessor), ("classifier", classifier)])


def metrics(actual, predicted, probabilities=None, classes=None):
    classes = classes or CLASSES
    report = {"records": len(actual), "accuracy": float(accuracy_score(actual, predicted)),
              "macro_f1": float(f1_score(actual, predicted, labels=classes, average="macro", zero_division=0)),
              "weighted_f1": float(f1_score(actual, predicted, labels=classes, average="weighted", zero_division=0)),
              "per_class": classification_report(actual, predicted, labels=classes, output_dict=True, zero_division=0),
              "confusion_matrix": confusion_matrix(actual, predicted, labels=classes).tolist(), "class_order": classes}
    report["critical_events"] = critical_events(actual, predicted, "High" if "High" in classes else 1)
    if probabilities is not None:
        ordered = sorted(classes)
        truth = np.array([[int(label == c) for c in ordered] for label in actual])
        report.update(log_loss=float(log_loss(actual, probabilities, labels=ordered)),
                      multiclass_brier=float(np.mean(np.sum((probabilities-truth)**2, axis=1))))
        confidence = np.max(probabilities, axis=1)
        report["confidence_bins"] = [{"lower": lo, "upper": hi, "count": int(((confidence >= lo) & (confidence <= hi if hi == 1 else confidence < hi)).sum()),
            "accuracy": float(np.mean(np.asarray(actual)[mask] == np.asarray(predicted)[mask])) if mask.any() else None}
            for lo, hi in [(0., .5), (.5, .7), (.7, .9), (.9, 1.)]
            for mask in [((confidence >= lo) & (confidence <= hi if hi == 1 else confidence < hi))]]
    return report


def finish(model, component, metadata, snapshot, report):
    version = f"{component}-{uuid.uuid4().hex[:16]}"
    import os
    directory = Path(os.getenv("CORECARE_REPORT_DIR", str(ROOT / "reports/experiments"))) / version
    directory.mkdir(parents=True)
    snapshot_path = directory / "training_snapshot.csv"
    snapshot.to_csv(snapshot_path, index=False)
    metadata.update(dataset_sha256=hashlib.sha256(snapshot_path.read_bytes()).hexdigest(),
                    snapshot=str(snapshot_path), evaluation=report, features=metadata["features"])
    version = registry.register(model, component, metadata, version)
    (directory / "evaluation.json").write_text(json.dumps({"version": version, **metadata}, indent=2, allow_nan=False), encoding="utf-8")
    return {"version": version, "report": str(directory / "evaluation.json"), "promotion_eligible": metadata["promotion_eligible"],
            "held_out": report.get("held_out"), "status": "candidate_only"}


def compare_active(component, test, target, report, data_source):
    version = registry.active_version(component)
    if not version:
        return None, True
    model, metadata = registry.load(component)
    # A previous real model must have been fitted entirely before this holdout.
    if data_source == "verified_real" and metadata.get("data_source") == "verified_real":
        if metadata.get("training_end", "9999") >= str(test.record_date.min().date()):
            report["active_comparison"] = "Insufficient new holdout after active model training; promotion blocked."
            return version, False
    columns = metadata["features"]
    if not set(columns).issubset(test.columns):
        report["active_comparison"] = "Incompatible schema; promotion blocked."
        return version, False
    actual = test[target]
    report["active"] = metrics(actual, model.predict(test[columns]), classes=CLASSES if component == "workload" else [0, 1])
    return version, report["held_out"]["macro_f1"] >= report["active"]["macro_f1"]


def train_temporal(data, component, data_source="synthetic", source_fingerprint=None):
    workload = component == "workload"
    features = FEATURES if workload else DELAY_FEATURES
    categorical = CATEGORICAL if workload else ["hospital_workload", "submission_day"]
    target = TARGET if workload else "delayed"
    classes = CLASSES if workload else [0, 1]
    df = build_features(data) if workload else data.copy()
    df["record_date"] = pd.to_datetime(df.record_date)
    df["target_date"] = pd.to_datetime(df.target_date)
    train, test, embargo = chronological_split(df, "2026-08-24" if workload and data_source == "synthetic" else None)
    if set(train[target]) != set(classes) or set(test[target]) != set(classes):
        raise ValueError("Training and final validation must contain every target class.")
    dates = sorted(train.record_date.unique())
    if len(dates) < 30:
        raise ValueError("At least 30 training dates are needed for chronological development folds.")
    candidates = {
        "random_forest": RandomForestClassifier(n_estimators=160, max_depth=8, min_samples_leaf=3, class_weight="balanced", random_state=42, n_jobs=2),
        "extra_trees": ExtraTreesClassifier(n_estimators=160, max_depth=8, min_samples_leaf=3, class_weight="balanced", random_state=42, n_jobs=2),
        "hist_gradient_boosting": HistGradientBoostingClassifier(max_iter=100, max_leaf_nodes=15, l2_regularization=1, random_state=42),
        "gradient_boosting": GradientBoostingClassifier(n_estimators=100, max_depth=2, learning_rate=.05, random_state=42)}
    if workload:
        # Exploratory weights are selected on development data, never on final validation.
        candidates["high_sensitive_forest"] = RandomForestClassifier(n_estimators=160, max_depth=8,
            min_samples_leaf=3, class_weight={"Low": 1, "Medium": 1, "High": 6}, random_state=42, n_jobs=2)
        candidates["high_sensitive_extra_trees"] = ExtraTreesClassifier(n_estimators=160, max_depth=8,
            min_samples_leaf=3, class_weight={"Low": 1, "Medium": 1, "High": 6}, random_state=42, n_jobs=2)
    scores = {}
    critical_scores = {}
    reference_recalls = []
    positive = "High" if workload else 1
    for name, classifier in candidates.items():
        scores[name] = []
        critical_scores[name] = []
        for fraction in (.6, .8):
            boundary = pd.Timestamp(dates[int(len(dates)*fraction)])
            end = pd.Timestamp(dates[min(len(dates)-1, int(len(dates)*(fraction+.2))-1)])
            fit = train[train.target_date < boundary]
            val = train[(train.record_date >= boundary) & (train.record_date <= end)]
            if set(fit[target]) != set(classes) or set(val[target]) != set(classes):
                raise ValueError("Every chronological development fold must contain all target classes.")
            model = pipeline(clone(classifier), categorical, features)
            model.fit(fit[features], fit[target])
            fold = metrics(val[target], model.predict(val[features]), classes=classes)
            scores[name].append(fold["macro_f1"])
            critical_scores[name].append(fold["per_class"][str(positive)]["recall"])
            if name == "random_forest" and workload:
                reference_recalls.append(metrics(val[target], val.workload_level, classes=classes)["per_class"][str(positive)]["recall"])
    critical_floor = max(.5, float(np.mean(reference_recalls))) if reference_recalls else .5
    eligible_names = [name for name in scores if np.mean(critical_scores[name]) >= critical_floor]
    winner = max(eligible_names or list(scores), key=lambda name: (np.mean(scores[name]), -np.std(scores[name])))
    # Reserve a chronological tail of the training partition for sigmoid calibration.
    cal_start = pd.Timestamp(dates[int(len(dates)*.8)])
    fit_indices = np.flatnonzero((train.target_date < cal_start).to_numpy())
    cal_indices = np.flatnonzero((train.record_date >= cal_start).to_numpy())
    if set(train.iloc[fit_indices][target]) != set(classes) or set(train.iloc[cal_indices][target]) != set(classes):
        raise ValueError("Temporal calibration requires all classes in fit and calibration partitions.")
    model = CalibratedClassifierCV(pipeline(clone(candidates[winner]), categorical, features),
                                  method="sigmoid", cv=[(fit_indices, cal_indices)], ensemble=True)
    model.fit(train[features], train[target])
    predictions = model.predict(test[features])
    report = {"selection": "Prefer models meeting development critical-recall floors, then mean macro F1 on two chronological folds. Final validation is not used for selection.",
              "development_macro_f1": scores, "selected_algorithm": winner,
              "development_critical_recall": critical_scores, "development_reference_recall": reference_recalls,
              "development_critical_recall_floor": critical_floor,
              "development_critical_floor_met": bool(eligible_names),
              "calibration": {"method": "sigmoid", "fit_rows": len(fit_indices), "calibration_rows": len(cal_indices)},
              "held_out": metrics(test[target], predictions, model.predict_proba(test[features]), classes),
              "training_rows": len(train), "validation_rows": len(test), "boundary_rows_excluded": len(embargo),
              "validation_start": str(test.record_date.min().date()), "validation_end": str(test.record_date.max().date()),
              "majority_baseline": metrics(test[target], np.repeat(train[target].mode().iloc[0],len(test)), classes=classes)}
    if workload:
        report["persistence_baseline"] = metrics(test[target], test.workload_level, classes=classes)
    report["per_hospital"] = {str(h): metrics(group[target], model.predict(group[features]), classes=classes)
                             for h, group in test.groupby("hospital_id")}
    # Importance is measured on development data by the selected pipeline, not on final holdout.
    from sklearn.inspection import permutation_importance
    development_model = pipeline(clone(candidates[winner]), categorical, features)
    development_model.fit(train.iloc[fit_indices][features], train.iloc[fit_indices][target])
    importance = permutation_importance(development_model, train.iloc[cal_indices][features], train.iloc[cal_indices][target],
                                       scoring="f1_macro", n_repeats=2, random_state=42)
    report["development_permutation_importance"] = dict(zip(features, importance.importances_mean.tolist()))
    active, improves_active = compare_active(component, test, target, report, data_source)
    report["engineering_gates"] = promotion_checks(report, classes, positive, improves_active)
    eligible = report["engineering_gates"]["passed"]
    return finish(model, component, {"features": features, "data_source": data_source, "status": "candidate",
        "known_hospitals": sorted(train.iloc[fit_indices].hospital_id.unique().tolist()), "calibrated": True,
        "training_end": str(train.target_date.max().date()), "compared_active_version": active,
        "source_fingerprint": source_fingerprint,
        "training_profile": training_profile(train.iloc[fit_indices], features, categorical),
        "promotion_eligible": eligible}, df, report)


def train_delay_demo():
    data = pd.read_csv(ROOT / "datasets/raw/referrals.csv")
    if data.isna().any().any() or not data.delayed.isin([0,1]).all():
        raise ValueError("Invalid synthetic referral dataset.")
    from corecare.schemas import ReferralFeatures
    for row in data[DELAY_FEATURES].to_dict("records"):
        ReferralFeatures.model_validate(row)
    models = {"random_forest": RandomForestClassifier(n_estimators=100, class_weight="balanced", random_state=42),
              "extra_trees": ExtraTreesClassifier(n_estimators=100, class_weight="balanced", random_state=42),
              "logistic_regression": LogisticRegression(class_weight="balanced", max_iter=1000, random_state=42)}
    reports = {}
    fitted = {}
    for name, classifier in models.items():
        model = pipeline(classifier, ["hospital_workload", "submission_day"], DELAY_FEATURES)
        probabilities = cross_val_predict(model, data[DELAY_FEATURES], data.delayed,
            cv=StratifiedKFold(3, shuffle=True, random_state=42), method="predict_proba")
        reports[name] = metrics(data.delayed, np.argmax(probabilities, axis=1), probabilities, [0,1])
        fitted[name] = model.fit(data[DELAY_FEATURES], data.delayed)
    winner = max(reports, key=lambda k: reports[k]["macro_f1"])
    return finish(fitted[winner], "delay", {"features": DELAY_FEATURES, "data_source": "synthetic",
        "status": "candidate", "calibrated": False, "promotion_eligible": False,
        "compared_active_version": registry.active_version("delay")}, data,
        {"exploratory_cross_validation": reports, "selected_algorithm": winner,
         "limitations": ["Only 15 synthetic records", "No timestamp-derived labels", "No independent final evaluation",
                         "Selection uses the same exploratory folds", "Insufficient data for reliable calibration"]})
