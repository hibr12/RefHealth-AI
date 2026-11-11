from pathlib import Path
from datetime import datetime, timezone
from contextlib import redirect_stdout
from io import StringIO

from monitoring.model_monitor import monitor_models
from monitoring.drift_monitor import monitor_data_drift


BASE_DIR = Path(__file__).resolve().parent.parent

REPORT_DIR = BASE_DIR / "reports"


def capture_monitoring_output(monitor_function):

    output = StringIO()

    with redirect_stdout(output):
        monitor_function()

    return output.getvalue()


def generate_report():

    print("\nRefHealth AI")
    print("AUTOMATED MONITORING REPORT GENERATOR")
    print("=" * 50)

    # Create reports folder if it does not exist
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    # Generate timestamp
    current_time = datetime.now(timezone.utc)

    timestamp = current_time.strftime("%Y%m%d_%H%M%S")

    # Run model performance monitoring
    print("\nRunning model performance monitoring...")

    model_report = capture_monitoring_output(
        monitor_models
    )

    print("Model monitoring completed.")

    # Run data drift monitoring
    print("\nRunning data drift monitoring...")

    drift_report = capture_monitoring_output(
        monitor_data_drift
    )

    print("Data drift monitoring completed.")

    # Combine monitoring results
    final_report = f"""
==================================================
          RefHealth AI
          AUTOMATED MONITORING REPORT
==================================================

REPORT GENERATED AT:
{current_time.isoformat()}

==================================================
          1. MODEL PERFORMANCE MONITORING
==================================================

{model_report}


==================================================
          2. DATA DRIFT MONITORING
==================================================

{drift_report}


==================================================
          END OF MONITORING REPORT
==================================================
"""

    # Save report
    report_path = REPORT_DIR / f"monitoring_report_{timestamp}.txt"

    with open(report_path, "w", encoding="utf-8") as file:

        file.write(final_report)

    print("\nREPORT GENERATED SUCCESSFULLY.")

    print("REPORT LOCATION:", report_path)

    print("\nMONITORING REPORT:")
    print("=" * 50)

    print(final_report)


if __name__ == "__main__":

    try:

        generate_report()

    except Exception as error:

        print("\nREPORT GENERATION FAILED:", error)