from pathlib import Path
from datetime import datetime, timezone
from contextlib import redirect_stdout
from io import StringIO

from monitoring.model_monitor import monitor_models
from monitoring.drift_monitor import monitor_data_drift


BASE_DIR = Path(__file__).resolve().parent.parent

MODEL_PATH = BASE_DIR / "models" / "delay_prediction_model.joblib"

REPORT_DIR = BASE_DIR / "reports"


def run_monitor(function):

    output = StringIO()

    try:

        with redirect_stdout(output):
            function()

        return output.getvalue(), None

    except Exception as error:

        return output.getvalue(), str(error)


def check_model_health(output, error):

    if error:

        return "CRITICAL", "Model monitoring failed: " + error

    if not MODEL_PATH.exists():

        return "CRITICAL", "Active prediction model is missing."

    if "PERFORMANCE WARNING" in output:

        return "CRITICAL", "Model performance is below configured thresholds."

    if "INSUFFICIENT DATA" in output:

        return "WARNING", "Insufficient data for reliable performance monitoring."

    if "NO COMPLETED PREDICTIONS FOUND" in output:

        return "WARNING", "No completed predictions available."

    return "HEALTHY", "Model monitoring checks passed."


def check_drift_health(output, error):

    if error:

        return "CRITICAL", "Data drift monitoring failed: " + error

    if "POSSIBLE DATA DRIFT DETECTED" in output:

        return "CRITICAL", "Possible data drift detected."

    if (
        "NO RECORDS AVAILABLE" in output
        or "INSUFFICIENT BASELINE DATA" in output
        or "INSUFFICIENT RECENT DATA" in output
    ):

        return "WARNING", "Insufficient real referral data for drift monitoring."

    if "DRIFT MONITORING CANNOT CONTINUE" in output:

        return "WARNING", "Drift monitoring could not complete."

    return "HEALTHY", "No configured drift threshold was breached."


def get_overall_status(statuses):

    if "CRITICAL" in statuses:

        return "CRITICAL"

    if "WARNING" in statuses:

        return "WARNING"

    return "HEALTHY"


def generate_health_report():

    print("\nRefHealth AI")

    print("AI HEALTH STATUS AND ALERT SYSTEM")

    print("=" * 55)

    # Check model performance
    print("\nChecking model performance...")

    model_output, model_error = run_monitor(monitor_models)

    model_status, model_message = check_model_health(
        model_output,
        model_error
    )

    print("Model status:", model_status)

    # Check data drift
    print("\nChecking data drift...")

    drift_output, drift_error = run_monitor(monitor_data_drift)

    drift_status, drift_message = check_drift_health(
        drift_output,
        drift_error
    )

    print("Data drift status:", drift_status)

    # Check overall health
    statuses = [model_status, drift_status]

    overall_status = get_overall_status(statuses)

    # Create report
    current_time = datetime.now(timezone.utc)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = current_time.strftime("%Y%m%d_%H%M%S")

    report_path = REPORT_DIR / f"health_report_{timestamp}.txt"

    report = f"""
=======================================================
             RefHealth AI
             SYSTEM HEALTH REPORT
=======================================================

Generated at:
{current_time.isoformat()}

OVERALL SYSTEM STATUS:
{overall_status}

-------------------------------------------------------
1. MODEL PERFORMANCE STATUS
-------------------------------------------------------

Status: {model_status}

Details:
{model_message}

-------------------------------------------------------
2. DATA DRIFT STATUS
-------------------------------------------------------

Status: {drift_status}

Details:
{drift_message}

-------------------------------------------------------
3. ALERT SUMMARY
-------------------------------------------------------

"""

    if overall_status == "HEALTHY":

        report += "No monitoring alerts. System checks passed.\n"

    else:

        if model_status != "HEALTHY":

            report += f"MODEL ALERT: {model_message}\n"

        if drift_status != "HEALTHY":

            report += f"DATA DRIFT ALERT: {drift_message}\n"

    report += """
=======================================================
             END OF HEALTH REPORT
=======================================================
"""

    with open(report_path, "w", encoding="utf-8") as file:

        file.write(report)

    print("\nOVERALL SYSTEM STATUS:", overall_status)

    print("\nHEALTH REPORT GENERATED.")

    print("Report location:", report_path)

    print("\n" + report)


if __name__ == "__main__":

    generate_health_report()