import pandas as pd
import joblib

from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent

MODEL_PATH = (
    BASE_DIR
    / "models"
    / "workload_prediction_candidate.joblib"
)


def analyze_workload_features():

    print("\nRefHealth AI")
    print("HOSPITAL WORKLOAD FEATURE IMPORTANCE")
    print("=" * 60)

    # Load trained model
    model = joblib.load(MODEL_PATH)

    # Get preprocessing and classifier
    preprocessing = model.named_steps["preprocessing"]

    classifier = model.named_steps["classifier"]

    # Get transformed feature names
    feature_names = preprocessing.get_feature_names_out()

    # Get feature importance scores
    importance_scores = classifier.feature_importances_

    # Create importance dataframe
    importance_df = pd.DataFrame({
        "feature": feature_names,
        "importance": importance_scores
    })

    # Sort by importance
    importance_df = importance_df.sort_values(
        by="importance",
        ascending=False
    )

    print("\nTOP 20 MOST IMPORTANT FEATURES")

    print(
        importance_df.head(20).to_string(
            index=False
        )
    )

    print("\nLEAST IMPORTANT FEATURES")

    print(
        importance_df.tail(10).to_string(
            index=False
        )
    )

    # Save results
    output_path = (
        BASE_DIR
        / "datasets"
        / "processed"
        / "workload_feature_importance.csv"
    )

    importance_df.to_csv(
        output_path,
        index=False
    )

    print("\nFEATURE IMPORTANCE ANALYSIS COMPLETED.")

    print("RESULTS SAVED TO:")
    print(output_path)


if __name__ == "__main__":

    analyze_workload_features()