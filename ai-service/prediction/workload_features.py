def calculate_workload_features(data):

    features = data.copy()

    # 1. Estimated bed occupancy rate
    features["bed_occupancy_rate"] = (
        (features["total_beds"] - features["available_beds"])
        / features["total_beds"]
    )

    # 2. Pending referrals per available bed
    features["pending_per_available_bed"] = (
        features["pending_referrals"]
        / features["available_beds"].clip(lower=1)
    )

    # 3. Incoming referrals relative to patient volume
    features["referral_to_patient_ratio"] = (
        features["incoming_referrals"]
        / features["patient_volume"].clip(lower=1)
    )

    # 4. Workload trend
    workload_mapping = {
        "Low": 1,
        "Medium": 2,
        "High": 3
    }

    current_workload = features["workload_level"].map(
        workload_mapping
    )

    previous_workload = features["previous_workload_level"].map(
        workload_mapping
    )

    features["workload_trend"] = (
        current_workload - previous_workload
    )

    return features