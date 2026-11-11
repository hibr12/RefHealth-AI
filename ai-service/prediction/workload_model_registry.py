"""The legacy workload API stays pinned to its original artifact snapshot."""
from corecare import registry, storage


def get_active_workload_model():
    storage.initialize()
    registry.adopt_legacy()
    model, metadata = registry.load("workload_legacy")
    return model, metadata["version"]
