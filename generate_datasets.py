
"""Generate MotorGuard synthetic training data.
Synthetic data is for pipeline testing only.
Replace with labelled real motor readings for production validation.
"""

import numpy as np
import pandas as pd

# Reproducible random generator
RNG = np.random.default_rng(42)

N = 1000

FEATURES = [
    "vib_rms",
    "vib_mean",
    "vib_std",
    "current_rms",
    "current_mean",
    "current_std",
    "rpm",
    "temp_C"
]

data = []


def add(label, ranges):
    """Generate N samples for one motor condition."""

    for _ in range(N):
        row = {}

        for feature in FEATURES:
            low, high = ranges[feature]
            row[feature] = float(RNG.uniform(low, high))

        row["status"] = label
        data.append(row)


# NORMAL
add("NORMAL", {
    "vib_rms": (.20, .60),
    "vib_mean": (.10, .40),
    "vib_std": (.05, .20),
    "current_rms": (.10, .25),
    "current_mean": (.08, .28),
    "current_std": (.01, .09),
    "rpm": (900, 1000),
    "temp_C": (25, 45)
})


# OVERCURRENT
add("OVERCURRENT", {
    "vib_rms": (.20, .70),
    "vib_mean": (.10, .40),
    "vib_std": (.05, .25),
    "current_rms": (.28, .80),
    "current_mean": (.30, .75),
    "current_std": (.03, .25),
    "rpm": (800, 1000),
    "temp_C": (30, 55)
})


# OVERHEAT
add("OVERHEAT", {
    "vib_rms": (.20, .70),
    "vib_mean": (.10, .40),
    "vib_std": (.05, .25),
    "current_rms": (.10, .30),
    "current_mean": (.08, .28),
    "current_std": (.01, .12),
    "rpm": (850, 1000),
    "temp_C": (60, 85)
})


# UNBALANCE
add("UNBALANCE", {
    "vib_rms": (1.50, 2.50),
    "vib_mean": (.50, 1.20),
    "vib_std": (.50, 1.00),
    "current_rms": (.10, .30),
    "current_mean": (.08, .28),
    "current_std": (.02, .15),
    "rpm": (700, 950),
    "temp_C": (30, 55)
})


# STOPPED
add("STOPPED", {
    "vib_rms": (0.00, .10),
    "vib_mean": (0.00, .05),
    "vib_std": (0.00, .05),
    "current_rms": (0.00, .09),
    "current_mean": (0.00, .08),
    "current_std": (0.00, .03),
    "rpm": (0, 20),
    "temp_C": (25, 45)
})


# Create DataFrame
df = pd.DataFrame(data)

# Shuffle dataset
df = df.sample(
    frac=1,
    random_state=42
).reset_index(drop=True)

# Validate dataset
if df.empty:
    raise ValueError("Generated dataset is empty!")

if df.isnull().any().any():
    raise ValueError("Dataset contains missing values!")

# Save dataset
df.to_csv("dataset.csv", index=False)

print("===================================")
print("MotorGuard Dataset Generated")
print("===================================")

print("Total samples:", len(df))
print("\nClass distribution:")
print(df["status"].value_counts())

print("\nCurrent RMS ranges:")
print(
    df.groupby("status")["current_rms"]
    .agg(["min", "max", "mean"])
    .round(3)
)

print("\nDataset saved successfully!")
