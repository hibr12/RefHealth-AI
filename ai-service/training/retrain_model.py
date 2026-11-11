"""Compatibility entry point for the controlled learning cycle."""
import json
from training.learning_cycle import run_cycle


def retrain_model():
    result = run_cycle("delay")
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    retrain_model()
