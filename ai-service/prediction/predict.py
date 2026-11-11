"""Compatibility prediction function used by the original CLI prototypes."""
from corecare import registry, storage
from corecare.inference import delay_result


def predict_referral_delay(referral_data):
    storage.initialize()
    registry.adopt_legacy()
    return delay_result(referral_data)
