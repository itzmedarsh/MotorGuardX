
"""Train MotorGuard Decision Tree classifier."""

import joblib
import pandas as pd

from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix
)


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


# Load dataset
df = pd.read_csv("dataset.csv")

if df[FEATURES + ["status"]].isna().any().any():
    raise ValueError("Dataset contains missing values.")

X = df[FEATURES]
y = df["status"].astype(str)


# Split dataset
X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.20,
    random_state=42,
    stratify=y
)


# Train Decision Tree
model = DecisionTreeClassifier(
    max_depth=7,
    min_samples_leaf=3,
    class_weight="balanced",
    random_state=42
)

model.fit(X_train, y_train)


# Evaluate model
y_pred = model.predict(X_test)

accuracy = accuracy_score(y_test, y_pred)

print("\n========== MOTORGUARD ML RESULTS ==========")

print("Accuracy:", round(accuracy, 4))

print("\nClassification Report:")
print(
    classification_report(
        y_test,
        y_pred,
        zero_division=0
    )
)

print("\nConfusion Matrix:")
print("Class order:", list(model.classes_))

print(
    confusion_matrix(
        y_test,
        y_pred,
        labels=model.classes_
    )
)


# Test observed 0.35 A example.
test_case = pd.DataFrame([{
    "vib_rms": 0.40,
    "vib_mean": 0.25,
    "vib_std": 0.12,
    "current_rms": 0.35,
    "current_mean": 0.34,
    "current_std": 0.05,
    "rpm": 950,
    "temp_C": 40
}], columns=FEATURES)

prediction = model.predict(test_case)[0]

probabilities = model.predict_proba(test_case)[0]

print("\n0.35 A Test Prediction:", prediction)

print("\nPrediction Probabilities:")

for category, probability in zip(
    model.classes_,
    probabilities
):
    print(f"{category}: {probability * 100:.2f}%")


# Save trained model
joblib.dump(model, "modelDecision.pkl")

print("\nModel saved as modelDecision.pkl")
print("Feature order:", FEATURES)

print("==========================================")
