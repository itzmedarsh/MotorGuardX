import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import accuracy_score, classification_report
import joblib

df = pd.read_csv("dataset.csv")

features = [
    "vib_rms",
    "vib_mean",
    "vib_std",
    "current_rms",
    "current_mean",
    "current_std",
    "rpm",
    "temp_C"
]

X = df[features]
y = df["status"]
X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=42,
    stratify=y
)
model = DecisionTreeClassifier(
    max_depth=5,
    random_state=42
)

model.fit(X_train, y_train)

y_pred = model.predict(X_test)

accuracy = accuracy_score(y_test, y_pred)

print("Accuracy:", accuracy)

print("\nClassification Report:")
print(classification_report(y_test, y_pred))
joblib.dump(model, "modelDecision.pkl")

new_data = pd.DataFrame([{
    "vib_rms": 0.40,
    "vib_mean": 0.25,
    "vib_std": 0.12,
    "current_rms": 1.80,
    "current_mean": 1.60,
    "current_std": 0.30,
    "rpm": 950,
    "temp_C": 40
}])

prediction = model.predict(new_data)
print("Prediction:", prediction[0])

from sklearn.tree import export_text

rules = export_text(model, feature_names=features)

print("\n DECISION TREE Thresholds")
print(rules)