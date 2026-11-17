
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent

input_file = (
    ROOT / "outputs" / "tables" /
    "08_negative_port_stay_investigation.csv"
)

output_file = (
    ROOT / "outputs" / "tables" /
    "08d_timestamp_anomaly_classification.csv"
)

df = pd.read_csv(input_file, low_memory=False)

classifications = {
    "INDIVIDUAL": {
        "9416006": (
            "ESTIMATED_TIMESTAMP_INCONSISTENCY",
            "Actual timestamps show a positive stay. "
            "Retain source estimates and flag."
        )
    },
    "SCHEDULE": {
        "9416006": (
            "ESTIMATED_TIMESTAMP_INCONSISTENCY_AND_PORT_CODE_REVIEW",
            "Corresponding individual record exists, but "
            "UNLOCODE differs. Do not merge port codes."
        ),
        "9289192": (
            "ESTIMATED_TIMESTAMP_INCONSISTENCY",
            "Actual timestamps show a positive stay. "
            "Retain source estimates and flag."
        )
    }
}

def classify(row):
    dataset = str(row["Source_Dataset"]).upper()
    imo = str(row["IMO_Normalised"]).replace(".0", "")

    result = classifications.get(dataset, {}).get(imo)

    if result:
        return pd.Series(result)

    return pd.Series([
        "UNCLASSIFIED",
        "Requires further investigation."
    ])

df[["Anomaly_Classification", "Investigation_Notes"]] = (
    df.apply(classify, axis=1)
)

df["Resolution_Status"] = "FLAGGED_NOT_CORRECTED"

df.to_csv(output_file, index=False)

print("\nANOMALY CLASSIFICATION")
print("=" * 70)

print(
    df[
        [
            "Source_Dataset",
            "IMO_Normalised",
            "Anomaly_Classification",
            "Resolution_Status"
        ]
    ].to_string(index=False)
)

print("\nSaved:", output_file)