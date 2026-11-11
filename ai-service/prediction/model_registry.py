"""Compatibility wrapper around the immutable managed delay registry."""
from corecare import registry, storage


def get_active_model():
    storage.initialize()
    registry.adopt_legacy()
    model, metadata = registry.load("delay")
    return model, metadata["version"]
