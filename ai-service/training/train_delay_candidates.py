import json
from corecare import registry, storage
from training.experiments import train_delay_demo


def main():
    storage.initialize()
    registry.adopt_legacy()
    print(json.dumps(train_delay_demo(), indent=2))


if __name__ == "__main__":
    main()
