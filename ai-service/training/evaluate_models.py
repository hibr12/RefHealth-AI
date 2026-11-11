"""Display immutable candidate evaluations without resplitting their datasets."""
import json
from corecare import storage, registry


def compare_models():
    storage.initialize()
    results = [{"version": m["version"], "active": m["active"], "evaluation": m["metadata"].get("evaluation")}
               for m in registry.catalog() if m["component"] == "delay"]
    print(json.dumps(results, indent=2))
    return results


if __name__ == "__main__":
    compare_models()
