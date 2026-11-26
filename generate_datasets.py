
"""Generate MotorGuard synthetic training data.
Synthetic data is for pipeline testing only.
Replace with labelled real motor readings for production validation.
"""

import numpy as np
import pandas as pd

RNG = np.random.default_rng(42)
N = 1000

def u(low, high):
    return RNG.uniform(low, high, N)

rows = []

def add(label, ranges):
    columns = [
        "vib_rms", "vib_mean", "vib_std",
        "current_rms", "current_mean", "current_std",
        "rpm", "temp_C"
    ]

    values = [u(*ranges[column]) for column in columns]

    for sample in zip(*values):
        rows.append([*sample, label])


# NORMAL
add("NORMAL", {
    "vib_rms": (.20, .60),
    "vib_mean": (.10, .40),
    "vib_std": (.05, .20),
    "current_rms "=random.uniform(0.10, 0.25),
    "current_mean": (.08, .28),
    "current_std": (.01, .09),
    "rpm": (900, 1000),
    "temp_C": (25, 45)
})


# OVERCURRENT
# Includes the observed 0.35 A test reading.
add("OVERCURRENT", {
    "vib_rms": (.20, .70),
    "vib_mean": (.10, .40),
    "vib_std": (.05, .25),
    "current_rms"=random.uniform(0.28, 0.80),
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


columns = [
    "vib_rms",
    "vib_mean",
    "vib_std",
    "current_rms",
    "current_mean",
    "current_std",
    "rpm",
    "temp_C",
    "status"
]

df = pd.DataFrame(rows, columns=columns)

df = df.sample(
    frac=1,
    random_state=42
).reset_index(drop=True)

df.to_csv("dataset.csv", index=False)

print("Dataset created successfully!")
print("Total samples:", len(df))
print("\nClass distribution:")
print(df["status"].value_counts())

print("\nCurrent RMS ranges:")
print(
    df.groupby("status")["current_rms"]
    .agg(["min", "max", "mean"])
    .round(3)
)
