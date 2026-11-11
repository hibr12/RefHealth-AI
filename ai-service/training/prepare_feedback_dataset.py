"""Export only independently verified real outcomes, preserving provenance."""
from pathlib import Path
from corecare.config import ROOT
from corecare.storage import initialize
from training.learning_cycle import datasets


def prepare_feedback_dataset(output=None):
    initialize()
    data = datasets()["delay"]
    if data.empty:
        print("No verified real referral records. No training dataset was written.")
        return data
    path = Path(output or ROOT / "datasets/processed/verified_referrals.csv")
    path.parent.mkdir(parents=True, exist_ok=True)
    data.to_csv(path, index=False)
    print(f"Exported {len(data)} verified real referrals to {path}")
    return data


if __name__ == "__main__":
    prepare_feedback_dataset()
