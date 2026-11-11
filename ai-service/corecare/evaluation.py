"""Explicit false-negative accounting and versioned engineering promotion gates."""
import numpy as np


def critical_events(actual, predicted, positive):
    actual = np.asarray(actual) == positive
    predicted = np.asarray(predicted) == positive
    tp = int(np.sum(actual & predicted))
    fn = int(np.sum(actual & ~predicted))
    fp = int(np.sum(~actual & predicted))
    tn = int(np.sum(~actual & ~predicted))
    return {"class": str(positive), "actual_events": tp + fn, "detected": tp,
            "missed": fn, "false_alarms": fp, "non_events": tn + fp,
            "recall": tp / (tp + fn) if tp + fn else None,
            "false_alarm_rate": fp / (fp + tn) if fp + tn else None}


def promotion_checks(report, classes, positive, improves_active):
    held = report["held_out"]
    # An always-positive majority classifier has recall 1 by construction; it is
    # compared by macro F1, not used to require perfect critical-event recall.
    comparisons = {key: report[key] for key in ("persistence_baseline", "active") if key in report}
    baseline = max(report[key]["macro_f1"] for key in ("majority_baseline", "persistence_baseline") if key in report)
    positive_recall = held["per_class"][str(positive)]["recall"]
    checks = {
        "active_macro_f1_not_worse": bool(improves_active) and "active_comparison" not in report
            and ("active" not in report or held["macro_f1"] >= report["active"]["macro_f1"]),
        "sufficient_class_support": all(held["per_class"][str(c)]["support"] >= 10 for c in classes),
        "minimum_class_recall": all(held["per_class"][str(c)]["recall"] >= .2 for c in classes),
        "macro_f1_improves_baseline": held["macro_f1"] >= baseline + .01,
        "critical_recall_at_least_half": positive_recall >= .5,
        "critical_recall_not_worse": all(positive_recall >= r["per_class"][str(positive)]["recall"] for r in comparisons.values()),
    }
    return {"version": "engineering-v2", "minimum_per_class_support": 10,
            "minimum_per_class_recall": .2, "minimum_critical_recall": .5,
            "critical_class": str(positive), "required_macro_f1_gain_over_baseline": .01,
            "checks": checks, "failure_reasons": [name for name, passed in checks.items() if not passed],
            "passed": all(checks.values()),
            "note": "Engineering checks only; operating teams must approve acceptable misses and false alarms."}
