"""Integration tests use isolated databases/artifacts, never the project feedback data."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import joblib
import pandas as pd
import numpy as np
from fastapi.testclient import TestClient
from corecare import storage, registry
from corecare.config import ROOT
from corecare.features import build_features, inference_features, FEATURES
from corecare.schemas import LOCAL_TIME
from main import app
from training.audit_workload_v6_features import audit
from training.learning_cycle import run_cycle, datasets
from training.experiments import metrics
from corecare.evidence import assess_prediction, training_profile
from corecare.evaluation import promotion_checks


REFERRAL = {"distance_km": 12, "hospital_workload": "Low", "pending_referrals": 8,
            "service_available": 1, "submission_hour": 8, "submission_day": "Monday"}


def passing_evaluation(classes):
    """Artificial evaluation fixture for isolated registry lifecycle tests only."""
    actual = [c for c in classes for _ in range(20)]
    return {"held_out": metrics(actual, actual, classes=classes),
            "majority_baseline": metrics(actual, [classes[0]] * len(actual), classes=classes)}


class FeatureTests(unittest.TestCase):
    def test_complete_v6_audit(self):
        result = audit()
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["split"]["training"]["rows"], 1425)
        self.assertEqual(result["split"]["validation"]["rows"], 360)

    def test_gaps_duplicates_invalid_beds_and_missing_values(self):
        data = pd.read_csv(ROOT / "datasets/raw/hospital_daily_history_v6.csv").head(20)
        invalid = [data.drop(index=5), pd.concat([data,data.iloc[:1]])]
        for field,value in [("available_beds",99999),("patient_volume",None),("total_beds",0),("workload_level","Unknown")]:
            altered = data.copy()
            altered.loc[5,field] = value
            invalid.append(altered)
        for bad in invalid:
            with self.subTest(data=str(bad.iloc[0].to_dict())), self.assertRaises(ValueError):
                build_features(bad)

    def test_inference_training_parity(self):
        raw = pd.read_csv(ROOT / "datasets/raw/hospital_daily_history_v6.csv")
        single = raw[raw.hospital_id == "H001"].head(20)
        batch = build_features(single)
        row = inference_features(single.head(19).to_dict("records"), "H001", single.iloc[18].record_date)
        pd.testing.assert_frame_equal(row[FEATURES].reset_index(drop=True), batch.tail(1)[FEATURES].reset_index(drop=True))

    def test_history_cannot_contain_other_hospitals_or_future(self):
        raw = pd.read_csv(ROOT / "datasets/raw/hospital_daily_history_v6.csv").head(8)
        with self.assertRaises(ValueError):
            inference_features(raw.to_dict("records"), "H002", raw.iloc[-1].record_date)
        with self.assertRaises(ValueError):
            inference_features(raw.to_dict("records"), "H001", raw.iloc[-2].record_date)

    def test_confidence_never_hides_unsupported_evidence(self):
        assessment = assess_prediction({"0": .999, "1": .001}, REFERRAL,
            {"data_source": "synthetic", "calibrated": False})
        self.assertEqual(assessment["status"], "review_required")
        self.assertIn("model_not_trained_on_verified_real_data", assessment["reasons"])
        self.assertIn("probabilities_not_calibrated", assessment["reasons"])
        self.assertTrue(assessment["requires_human_review"])
        self.assertFalse(assessment["autonomous_use_supported"])

    def test_low_confidence_and_input_coverage_are_separate_signals(self):
        profile = training_profile(pd.DataFrame([REFERRAL]), list(REFERRAL), ["hospital_workload", "submission_day"])
        meta = {"data_source": "verified_real", "promotion_eligible": True,
                "calibrated": True, "training_profile": profile}
        assessment = assess_prediction({"0": .51, "1": .49}, {**REFERRAL, "distance_km": 10000}, meta)
        self.assertIn("low_model_confidence", assessment["reasons"])
        self.assertIn("similar_class_probabilities", assessment["reasons"])
        self.assertEqual(assessment["outside_training_features"], ["distance_km"])
        clear = assess_prediction({"0": .9, "1": .1}, REFERRAL, meta)
        self.assertEqual(clear["status"], "decision_support")
        self.assertTrue(clear["requires_human_review"])
        for probabilities in ({"0": .9, "1": .9}, {"0": float("nan"), "1": .1}):
            with self.assertRaises(RuntimeError):
                assess_prediction(probabilities, REFERRAL, meta)

    def test_better_average_score_cannot_hide_worse_critical_recall(self):
        report = passing_evaluation(["Low", "Medium", "High"])
        report["held_out"]["per_class"]["High"]["recall"] = .55
        report["persistence_baseline"] = passing_evaluation(["Low", "Medium", "High"])["held_out"]
        report["persistence_baseline"]["macro_f1"] = .7
        report["persistence_baseline"]["per_class"]["High"]["recall"] = .6
        checks = promotion_checks(report, ["Low", "Medium", "High"], "High", True)
        self.assertFalse(checks["passed"])
        self.assertEqual(checks["failure_reasons"], ["critical_recall_not_worse"])
        report["held_out"]["macro_f1"] = .9
        report["active"] = {**report["held_out"], "macro_f1": .95}
        self.assertFalse(promotion_checks(report, ["Low", "Medium", "High"], "High", True)["checks"]["active_macro_f1_not_worse"])
        self.assertEqual(metrics(["High", "Low", "Medium"], ["Medium", "High", "Medium"])["critical_events"]["missed"], 1)

    def test_always_positive_baseline_does_not_require_perfect_recall(self):
        actual = [0] * 20 + [1] * 20
        predicted = [0] * 15 + [1] * 5 + [0] * 5 + [1] * 15
        report = {"held_out": metrics(actual, predicted, classes=[0, 1]),
                  "majority_baseline": metrics(actual, [1] * 40, classes=[0, 1])}
        self.assertTrue(promotion_checks(report, [0, 1], 1, True)["passed"])

    def test_two_hour_boundary_and_optional_operational_context(self):
        from corecare.inference import validate_record_outcome
        from corecare.schemas import OutcomeSubmission, DailyMeasurements
        submitted = datetime.now(timezone.utc)-timedelta(hours=3)
        deadline = submitted+timedelta(hours=2)
        record = {"component": "delay", "record_type": "real", "inputs": {"submitted_at": submitted.isoformat()}}
        with self.assertRaises(ValueError):
            validate_record_outcome(record, OutcomeSubmission(actual_result=1, observed_until=deadline, source_reference="register"))
        valid = validate_record_outcome(record, OutcomeSubmission(actual_result=0, acknowledged_at=deadline, source_reference="register"))
        self.assertEqual(valid["actual_result"], 0)
        raw = {"hospital_id": "H001", "record_date": "2026-01-01", "patient_volume": 80,
               "incoming_referrals": 5, "pending_referrals": 3, "available_beds": 20,
               "total_beds": 60, "workload_level": "Medium", "staff_on_duty": 12, "staffed_beds": 50}
        self.assertEqual(DailyMeasurements(**raw).model_dump()["staff_on_duty"], 12)
        with self.assertRaises(ValueError):
            DailyMeasurements(**{**raw, "staffed_beds": 61})


class ServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        report = next((ROOT / "reports/experiments").glob("workload-*/evaluation.json"))
        cls.workload_metadata = json.loads(report.read_text())
        cls.workload_model = joblib.load(ROOT / "models/managed" / (cls.workload_metadata["version"] + ".joblib"))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="corecare-tests-")
        self.environment = patch.dict(os.environ, {"CORECARE_DATABASE": str(Path(self.temp.name)/"test.db"),
            "CORECARE_MODEL_DIR": str(Path(self.temp.name)/"models"), "CORECARE_REPORT_DIR": str(Path(self.temp.name)/"reports"),
            "CORECARE_ADMIN_TOKEN": "test-admin", "CORECARE_API_KEY": "test-service"})
        self.environment.start()
        self.client = TestClient(app)
        self.client.__enter__()
        self.client.headers["X-API-Key"] = "test-service"
        self.version = registry.register(self.workload_model, "workload", self.workload_metadata.copy())

    def tearDown(self):
        self.client.__exit__(None,None,None)
        self.environment.stop()
        self.temp.cleanup()

    def delay(self, **extras):
        response = self.client.post("/predict/delay", json={**REFERRAL, **extras})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_delay_prediction_and_version_tracking(self):
        result = self.delay()
        self.assertEqual(result["model_version"], "legacy-delay-v1")
        self.assertIn(result["data"]["prediction"], [0,1])
        self.assertAlmostEqual(sum(result["data"]["class_probabilities"].values()),1.)
        saved = storage.prediction(result["prediction_id"])
        self.assertEqual(saved["model_version"], result["model_version"])

    def test_invalid_and_missing_inputs(self):
        for data in [{}, {**REFERRAL,"distance_km":-1}, {**REFERRAL,"hospital_workload":"unknown"},
                     {**REFERRAL,"submission_day":"Notaday"}, {**REFERRAL,"pending_referrals":1.5}]:
            with self.subTest(data=data):
                self.assertEqual(self.client.post("/predict/delay",json=data).status_code,422)

    def test_unknown_hospital(self):
        self.assertEqual(self.client.post("/predict/delay",json={**REFERRAL,"hospital_id":"missing"}).status_code,404)

    def test_feedback_is_unverified_until_admin_review(self):
        identifier = self.delay()["prediction_id"]
        response = self.client.post(f"/feedback/{identifier}/outcome",json={"actual_result":0})
        self.assertEqual(response.json()["status"],"pending_verification")
        self.assertEqual(self.client.post(f"/feedback/{identifier}/outcome",json={"actual_result":0}).status_code,409)
        self.assertEqual(self.client.post("/feedback/missing/outcome",json={"actual_result":0}).status_code,404)
        payload = {"reviewer":"operator-1","evidence":"Verified source record."}
        self.assertEqual(self.client.post(f"/feedback/{identifier}/verify",json=payload).status_code,403)
        response = self.client.post(f"/feedback/{identifier}/verify",json=payload,headers={"X-Admin-Token":"test-admin"})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(len(storage.verified_delay()),0, "Verified test outcomes must not enter real training.")

    def test_real_referral_verification_and_timestamp_target(self):
        timestamp = datetime.now(timezone.utc)-timedelta(minutes=1)
        result = self.delay(hospital_id="H001",record_type="real",submitted_at=timestamp.isoformat(),
            feature_observed_at=timestamp.isoformat(),source_reference="referral-123")
        identifier = result["prediction_id"]
        payload = {"actual_result":1,"acknowledged_at":datetime.now(timezone.utc).isoformat(),"source_reference":"ack-log"}
        self.assertEqual(self.client.post(f"/feedback/{identifier}/outcome",json=payload).status_code,422)
        payload["actual_result"] = 0
        self.assertEqual(self.client.post(f"/feedback/{identifier}/outcome",json=payload).status_code,200)
        self.assertEqual(len(storage.verified_delay()),0)
        self.client.post(f"/feedback/{identifier}/verify",json={"reviewer":"operator","evidence":"Timestamp checked in source."},headers={"X-Admin-Token":"test-admin"})
        self.assertEqual(len(storage.verified_delay()),1)
        exported = datasets()["delay"]
        self.assertEqual(exported.iloc[0].prediction_id,identifier)
        self.assertEqual(exported.iloc[0].delayed,0)

    def test_future_features_and_stale_real_predictions_rejected(self):
        timestamp = datetime.now(timezone.utc)
        base = {**REFERRAL,"hospital_id":"H001","record_type":"real","source_reference":"source",
                "submitted_at":timestamp.isoformat(),"feature_observed_at":(timestamp+timedelta(hours=1)).isoformat()}
        self.assertEqual(self.client.post("/predict/delay",json=base).status_code,422)
        base["submitted_at"] = (timestamp-timedelta(days=1)).isoformat()
        base["feature_observed_at"] = base["submitted_at"]
        self.assertEqual(self.client.post("/predict/delay",json=base).status_code,422)

    def test_workload_candidate_is_explicit_and_not_active(self):
        request = {"hospital_id":"H001","as_of_date":"2026-11-04"}
        self.assertEqual(self.client.post("/predict/workload/next-day",json=request).status_code,503)
        request["model_version"] = self.version
        response = self.client.post("/predict/workload/next-day",json=request)
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()["prediction_date"],"2026-11-05")
        self.assertEqual(set(response.json()["class_probabilities"]),{"Low","Medium","High"})
        self.assertIsNone(registry.active_version("workload"))

    def test_legacy_workload_endpoint(self):
        data = {"hospital_id":"H001","day_of_week":"Monday","workload_level":"Medium","patient_volume":75,
                "incoming_referrals":8,"pending_referrals":6,"available_beds":20,"total_beds":60,
                "previous_patient_volume":70,"previous_pending_referrals":5,"previous_available_beds":22,
                "previous_workload_level":"Medium","average_3day_patient_volume":72.,"average_3day_pending_referrals":5.}
        response = self.client.post("/predict/workload",json=data)
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()["model_version"],"legacy-workload-v1")
        data["available_beds"] = 100
        self.assertEqual(self.client.post("/predict/workload",json=data).status_code,422)

    def test_recommendations_integrate_models_and_exclusions(self):
        request = {"required_service":"Surgery","submitted_at":"2026-11-05T08:00:00+03:00",
                   "workload_as_of_date":"2026-11-04","workload_model_version":self.version}
        response = self.client.post("/recommendations",json=request)
        self.assertEqual(response.status_code,200,response.text)
        data = response.json()["data"]
        self.assertTrue(data["workload_used_in_ranking"])
        self.assertEqual(len(data["ranked_hospitals"]),4)
        self.assertNotIn("H003",[r["hospital_id"] for r in data["ranked_hospitals"]])
        self.assertTrue(any(r["reason"]=="required_service_unavailable" for r in data["excluded"]))
        request["required_service"] = "Unavailable"
        self.assertEqual(self.client.post("/recommendations",json=request).json()["data"]["ranked_hospitals"],[])

    def test_selection_links_only_an_eligible_referral(self):
        response = self.client.post("/recommendations",json={"required_service":"Emergency","submitted_at":datetime.now(timezone.utc).isoformat()})
        identifier = response.json()["prediction_id"]
        referral = self.delay(hospital_id="H001")
        selected = self.client.post(f"/recommendations/{identifier}/selection",json={"hospital_id":"H001","referral_prediction_id":referral["prediction_id"]})
        self.assertEqual(selected.status_code,200,selected.text)

    def test_daily_intake_verification_and_duplicate(self):
        yesterday = datetime.now(LOCAL_TIME).date()-timedelta(days=1)
        data = {"hospital_id":"H001","record_date":str(yesterday),"patient_volume":70,"incoming_referrals":6,
                "pending_referrals":4,"available_beds":25,"total_beds":60,"workload_level":"Medium",
                "record_type":"real","observed_at":datetime.now(timezone.utc).isoformat(),"source_reference":"daily-register"}
        forecast = storage.save_prediction("workload",{}, {"model_version":"test","predicted_workload":"Low"},"real","H001",str(yesterday))
        response = self.client.post("/operations/daily",json=data)
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(self.client.post("/operations/daily",json=data).status_code,409)
        self.assertEqual(len(storage.verified_daily()),0)
        identifier = response.json()["record_id"]
        response = self.client.post(f"/operations/daily/{identifier}/verify",json={"reviewer":"operator","evidence":"Daily register checked."},headers={"X-Admin-Token":"test-admin"})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(len(storage.verified_daily()),1)
        with storage.connection() as db:
            outcome = db.execute("SELECT * FROM ai_outcomes WHERE prediction_id=?",(forecast,)).fetchone()
            self.assertEqual(outcome["status"],"verified")
            self.assertEqual(json.loads(outcome["payload"])["actual_result"],"Medium")

    def test_learning_waits_for_verified_data_and_never_promotes(self):
        before = registry.active_version("delay")
        result = run_cycle()
        self.assertEqual(result["delay"]["status"],"awaiting_verified_data")
        self.assertEqual(result["workload"]["status"],"awaiting_verified_data")
        self.assertEqual(registry.active_version("delay"),before)

    def test_model_integrity_and_error_handling(self):
        with storage.connection() as db:
            path = db.execute("SELECT artifact FROM model_versions WHERE version='legacy-delay-v1'").fetchone()[0]
        Path(path).write_bytes(b"corrupt test artifact")
        self.assertEqual(self.client.post("/predict/delay",json=REFERRAL).status_code,503)
        self.assertEqual(self.client.get("/health").json()["status"],"degraded")

    def test_promotion_rejects_failed_candidate(self):
        with self.assertRaises(ValueError):
            registry.promote("workload",self.version,"reviewer","Review",allow_experimental=True)
        self.assertIsNone(registry.active_version("workload"))

    def test_explicit_approval_and_rollback(self):
        model,meta = registry.load("delay")
        candidate = registry.register(model,"delay",{**meta,"status":"candidate","evaluation":passing_evaluation([0,1]),
            "promotion_eligible":True,"compared_active_version":"legacy-delay-v1"})
        with self.assertRaises(ValueError):
            registry.promote("delay",candidate,"operator","Demo review")
        registry.promote("delay",candidate,"operator","Demo review",allow_experimental=True)
        self.assertEqual(registry.active_version("delay"),candidate)
        self.assertEqual(registry.rollback("delay","operator","Rollback test"),"legacy-delay-v1")

    def test_monitoring_and_auth(self):
        self.assertEqual(self.client.get("/monitoring").status_code,403)
        response = self.client.get("/monitoring",headers={"X-Admin-Token":"test-admin"})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()["data"]["drift"][0]["status"],"insufficient_data")
        self.assertEqual(self.client.get("/models",headers={"X-API-Key":"wrong"}).status_code,401)

    def test_real_workload_uses_verified_daily_history(self):
        metadata = {**self.workload_metadata, "promotion_eligible":True, "compared_active_version":None,
                    "evaluation": passing_evaluation(["Low", "Medium", "High"])}
        version = registry.register(self.workload_model,"workload",metadata)
        registry.promote("workload",version,"test-operator","Isolated workflow fixture",allow_experimental=True)
        yesterday = datetime.now(LOCAL_TIME).date()-timedelta(days=1)
        for offset in range(7):
            payload = {"hospital_id":"H001","record_date":str(yesterday-timedelta(days=6-offset)),
                "patient_volume":70+offset,"incoming_referrals":8,"pending_referrals":5,"available_beds":25,
                "total_beds":60,"workload_level":"Medium","record_type":"real",
                "observed_at":datetime.now(timezone.utc).isoformat(),"source_reference":f"register-{offset}"}
            identifier = storage.save_daily(payload)
            if offset < 6:
                storage.verify_daily(identifier,"operator","Source record verified.")
        request = {"hospital_id":"H001","as_of_date":str(yesterday),"record_type":"real"}
        self.assertEqual(self.client.post("/predict/workload/next-day",json=request).status_code,422)
        storage.verify_daily(identifier,"operator","Final record verified.")
        response = self.client.post("/predict/workload/next-day",json=request)
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()["prediction_date"],str(yesterday+timedelta(days=1)))
        self.assertEqual(storage.prediction(response.json()["prediction_id"])["record_type"],"real")

    def test_capacity_is_distinguished_from_service_eligibility(self):
        candidate = {"hospital_id":"H001","hospital_name":"Demo","service":"Emergency","service_available":1,
            "available_beds":0,"distance_km":5,"hospital_workload":"High","pending_referrals":25}
        request = {"required_service":"Emergency","submitted_at":datetime.now(timezone.utc).isoformat(),"candidates":[candidate]}
        response = self.client.post("/recommendations",json=request)
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()["data"]["ranked_hospitals"][0]["operational_status"],"limited_capacity")
        self.assertEqual(response.json()["data"]["excluded"],[])

    def test_daily_learning_creates_candidate_once_without_activation(self):
        model,metadata = registry.load("delay")
        frame = pd.DataFrame([{**REFERRAL,"hospital_id":"H001","delayed":0,"record_date":"2026-01-01","target_date":"2026-01-02"}])
        state = {"delay":{"ready":True,"verified_records":100,"reasons":[]}}
        def fake_train(data,component,source,source_fingerprint):
            version = registry.register(model,component,{**metadata,"data_source":source,"source_fingerprint":source_fingerprint,"status":"candidate"})
            return {"version":version,"status":"candidate_only"}
        with patch("training.learning_cycle.readiness",return_value=state), patch("training.learning_cycle.datasets",return_value={"delay":frame}), patch("training.learning_cycle.train_temporal",side_effect=fake_train) as train:
            first = run_cycle("delay")
            second = run_cycle("delay")
            self.assertEqual(first["delay"]["status"],"candidate_only")
            self.assertEqual(second["delay"]["status"],"unchanged_verified_data")
            self.assertEqual(train.call_count,1)
        self.assertEqual(registry.active_version("delay"),"legacy-delay-v1")

    def test_artifact_registration_cannot_overwrite(self):
        model,metadata = registry.load("delay")
        with self.assertRaises(FileExistsError):
            registry.register(model,"delay",metadata,"legacy-delay-v1")
        registry.load("delay")

    def test_stale_approval_and_empty_reviewer_are_rejected(self):
        model,metadata = registry.load("delay")
        version = registry.register(model,"delay",{**metadata,"promotion_eligible":True,"evaluation":{"fixture":True},"compared_active_version":"obsolete"})
        with self.assertRaises(ValueError):
            registry.promote("delay",version,"reviewer","Review",allow_experimental=True)
        with self.assertRaises(ValueError):
            registry.promote("delay",version,"","Review",allow_experimental=True)

    def test_review_evidence_is_returned_and_persisted(self):
        result = self.delay()
        self.assertEqual(result["data"]["review"]["status"], "review_required")
        self.assertEqual(storage.prediction(result["prediction_id"])["result"]["review"], result["data"]["review"])
        response = self.client.post("/predict/workload/next-day", json={"hospital_id": "H001",
            "as_of_date": "2026-11-04", "model_version": self.version})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn("model_evaluation_gates_not_passed", response.json()["data"]["review"]["reasons"])

    def test_collect_referral_without_a_model_and_verify_for_learning(self):
        with storage.connection() as db:
            db.execute("DELETE FROM active_models WHERE component='delay'")
        timestamp = datetime.now(timezone.utc)-timedelta(minutes=1)
        request = {**REFERRAL, "hospital_id": "H001", "record_type": "real",
                   "submitted_at": timestamp.isoformat(), "feature_observed_at": timestamp.isoformat(),
                   "source_reference": "register-referral-001"}
        response = self.client.post("/operations/referrals", json=request)
        self.assertEqual(response.status_code, 200, response.text)
        identifier = response.json()["observation_id"]
        self.assertEqual(self.client.post("/operations/referrals", json=request).status_code, 409)
        verification = {"reviewer": "operator", "evidence": "Checked the referral register."}
        headers = {"X-Admin-Token": "test-admin"}
        route = f"/operations/referrals/{identifier}"
        self.assertEqual(self.client.post(route+"/verify", json=verification, headers=headers).status_code, 422)
        outcome = {"actual_result": 0, "acknowledged_at": datetime.now(timezone.utc).isoformat(), "source_reference": "ack-001"}
        self.assertEqual(self.client.post(route+"/outcome", json={**outcome, "actual_result": 1}).status_code, 422)
        self.assertEqual(self.client.post(route+"/outcome", json={**outcome, "observed_until": outcome["acknowledged_at"]}).status_code, 422)
        self.assertEqual(self.client.post(route+"/outcome", json=outcome).status_code, 200)
        self.assertTrue(datasets()["delay"].empty)
        self.assertEqual(self.client.post(route+"/verify", json=verification).status_code, 403)
        self.assertEqual(self.client.post(route+"/verify", json=verification, headers=headers).status_code, 200)
        self.assertEqual(len(datasets()["delay"]), 1)
        self.assertEqual(self.client.post(route+"/verify", json=verification, headers=headers).status_code, 409)
        self.assertEqual(self.client.post(route+"/outcome", json=outcome).status_code, 409)
        status = self.client.get("/learning/status", headers=headers).json()["data"]["delay"]
        self.assertFalse(status["ready"])
        self.assertEqual(status["per_hospital"][0]["observed_class_counts"], {"0": 1})

    def test_observation_and_shadow_prediction_are_not_double_counted(self):
        timestamp = datetime.now(timezone.utc)-timedelta(minutes=1)
        request = {**REFERRAL, "hospital_id": "H001", "record_type": "real",
                   "submitted_at": timestamp.isoformat(), "feature_observed_at": timestamp.isoformat(),
                   "source_reference": "shared-referral"}
        prediction = self.client.post("/predict/delay", json=request).json()["prediction_id"]
        observation = self.client.post("/operations/referrals", json=request).json()["observation_id"]
        outcome = {"actual_result": 0, "acknowledged_at": datetime.now(timezone.utc).isoformat(), "source_reference": "ack"}
        verification = {"reviewer": "operator", "evidence": "Source timestamps checked."}
        for route in (f"/feedback/{prediction}", f"/operations/referrals/{observation}"):
            self.assertEqual(self.client.post(route+"/outcome", json=outcome).status_code, 200)
            self.assertEqual(self.client.post(route+"/verify", json=verification, headers={"X-Admin-Token": "test-admin"}).status_code, 200)
        self.assertEqual(len(datasets()["delay"]), 1)
        # Corrupt only this isolated fixture to confirm contradictory sources stop learning.
        with storage.connection() as db:
            altered = {**request, "distance_km": 99}
            db.execute("UPDATE referral_observations SET inputs=? WHERE observation_id=?", (json.dumps(altered), observation))
        with self.assertRaisesRegex(ValueError, "Conflicting verified"):
            datasets()

    def test_verified_test_observation_never_enters_real_training(self):
        response = self.client.post("/operations/referrals", json={**REFERRAL, "hospital_id": "H001", "source_reference": "test-only"})
        identifier = response.json()["observation_id"]
        self.client.post(f"/operations/referrals/{identifier}/outcome", json={"actual_result": 0})
        self.client.post(f"/operations/referrals/{identifier}/verify", json={"reviewer": "operator", "evidence": "Test evidence only."}, headers={"X-Admin-Token": "test-admin"})
        self.assertTrue(datasets()["delay"].empty)

    def test_travel_time_requires_comparable_coverage(self):
        first = {"hospital_id": "H001", "hospital_name": "A", "service": "Emergency", "service_available": 1,
                 "available_beds": 10, "distance_km": 5, "hospital_workload": "Low", "pending_referrals": 2,
                 "estimated_travel_minutes": 90}
        second = {**first, "hospital_id": "H002", "hospital_name": "B", "estimated_travel_minutes": 15}
        request = {"required_service": "Emergency", "submitted_at": datetime.now(timezone.utc).isoformat(), "candidates": [first, second]}
        response = self.client.post("/recommendations", json=request)
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()["data"]
        self.assertEqual(data["travel_measure"], "estimated_travel_minutes")
        self.assertEqual(data["ranked_hospitals"][0]["hospital_id"], "H002")
        self.assertTrue(data["review"]["requires_human_review"])
        second.pop("estimated_travel_minutes")
        response = self.client.post("/recommendations", json=request)
        self.assertEqual(response.json()["data"]["travel_measure"], "distance_km")

    def test_recent_monitoring_counts_misses_and_excludes_old_and_test_records(self):
        for hospital, kind, days, count in (("H001", "real", 1, 60), ("H002", "real", 1, 1),
                                            ("H001", "real", 45, 3), ("H001", "test", 1, 3)):
            for index in range(count):
                actual = ["Low", "Medium", "High"][index % 3]
                predicted = "Medium" if actual == "High" else actual
                result = {"model_version": "monitor-fixture", "predicted_workload": predicted,
                          "class_probabilities": {c: .8 if c == predicted else .1 for c in ("Low", "Medium", "High")},
                          "review": {"requires_human_review": True}}
                identifier = storage.save_prediction("workload", {"features": {"workload_level": actual}}, result, kind, hospital)
                storage.submit_outcome(identifier, {"actual_result": actual})
                storage.verify_outcome(identifier, "operator", "Isolated monitoring fixture.")
                with storage.connection() as db:
                    db.execute("UPDATE ai_predictions SET predicted_at=? WHERE prediction_id=?",
                               ((datetime.now(timezone.utc)-timedelta(days=days)).isoformat(), identifier))
        storage.save_prediction("delay", REFERRAL, {"model_version": "pending-fixture", "prediction": 0}, "real", "H001")
        response = self.client.get("/monitoring", headers={"X-Admin-Token": "test-admin"})
        self.assertEqual(response.status_code, 200, response.text)
        report = response.json()["data"]
        recent = next(r for r in report["recent_performance"] if r["hospital_id"] == "H001" and r["window_days"] == 7)
        self.assertEqual(recent["records"], 60)
        self.assertEqual(recent["critical_events"]["missed"], 20)
        self.assertEqual(recent["critical_events"]["false_alarms"], 0)
        self.assertIn("worse_than_persistence", recent["alerts"])
        self.assertEqual(recent["probability_quality"]["records"], 60)
        small = next(r for r in report["recent_performance"] if r["hospital_id"] == "H002")
        self.assertEqual(small["status"], "insufficient_data")
        self.assertEqual(report["outcome_coverage"][0]["without_outcome"], 1)
        self.assertEqual(report["outcome_coverage"][0]["verified_outcomes"], 61)

    def test_current_promotion_gates_recheck_old_eligibility_flag(self):
        metadata = {**self.workload_metadata, "promotion_eligible": True, "compared_active_version": None}
        version = registry.register(self.workload_model, "workload", metadata)
        with self.assertRaisesRegex(ValueError, "current promotion gates"):
            registry.promote("workload", version, "operator", "Old flag cannot bypass new checks", allow_experimental=True)
        self.assertIsNone(registry.active_version("workload"))

    def test_training_experiment_is_isolated_and_profiles_only_fitting_data(self):
        from training.experiments import train_temporal
        rng = np.random.default_rng(42)
        records = []
        for hospital in ("H001", "H002", "H003"):
            for index, day in enumerate(pd.date_range("2026-04-01", periods=180)):
                if hospital == "H003" and day < pd.Timestamp("2026-08-24"):
                    continue
                records.append({"hospital_id": hospital, "record_date": str(day.date()),
                    "patient_volume": 10000 if day >= pd.Timestamp("2026-08-24") else int(rng.integers(50, 100)),
                    "incoming_referrals": 8, "pending_referrals": index % 10,
                    "available_beds": 20 + index % 5, "total_beds": 60,
                    "workload_level": ["Low", "Medium", "High"][(index // 2) % 3]})
        # Synthetic execution fixture; it is not an estimate of hospital performance.
        result = train_temporal(pd.DataFrame(records), "workload", "synthetic")
        _, metadata = registry.load("workload", result["version"])
        self.assertLess(metadata["training_profile"]["numeric"]["patient_volume"]["max"], 10000)
        self.assertEqual(metadata["known_hospitals"], ["H001", "H002"])
        self.assertIn("high_sensitive_forest", metadata["evaluation"]["development_macro_f1"])
        self.assertEqual(metadata["evaluation"]["engineering_gates"]["version"], "engineering-v2")
        self.assertTrue(Path(result["report"]).is_relative_to(self.temp.name))
        self.assertIsNone(registry.active_version("workload"))


if __name__ == "__main__":
    unittest.main()
