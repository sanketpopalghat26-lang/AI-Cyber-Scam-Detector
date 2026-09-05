"""
Train the production scam detection model.
==========================================
Trains a TF-IDF + Logistic Regression pipeline on the SMS Spam Collection
dataset and saves the complete pipeline to models/exports/best_model.pkl.

The saved artifact is a complete scikit-learn Pipeline (TfidfVectorizer +
LogisticRegression) so preprocessing and inference always match.
"""

import os
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

# Project root
ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "data" / "smsspamcollection" / "SMSSpamCollection"
OUTPUT_PATH = ROOT / "models" / "exports" / "best_model.pkl"


def load_dataset(path: Path) -> pd.DataFrame:
    """Load the SMS Spam Collection dataset."""
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found at {path}")
    df = pd.read_csv(path, sep="\t", header=None, names=["label", "text"])
    # Map labels: ham -> safe, spam -> scam
    df["label"] = df["label"].map({"ham": "safe", "spam": "scam"})
    df = df.dropna(subset=["text", "label"]).reset_index(drop=True)
    return df


def train_model(df: pd.DataFrame) -> tuple[Pipeline, dict]:
    """Train the model and return the pipeline plus metrics."""
    X = df["text"].astype(str)
    y = df["label"]

    # Train/test split (stratified to preserve class balance)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # Build pipeline: TF-IDF + Logistic Regression
    pipeline = Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    max_features=50000,
                    ngram_range=(1, 2),
                    sublinear_tf=True,
                    min_df=2,
                    stop_words="english",
                ),
            ),
            (
                "clf",
                LogisticRegression(
                    C=1.0,
                    max_iter=2000,
                    class_weight="balanced",
                    solver="liblinear",
                    random_state=42,
                ),
            ),
        ]
    )

    # Train
    pipeline.fit(X_train, y_train)

    # Evaluate
    y_pred = pipeline.predict(X_test)
    y_proba = pipeline.predict_proba(X_test)

    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "precision": float(precision_score(y_test, y_pred, pos_label="scam")),
        "recall": float(recall_score(y_test, y_pred, pos_label="scam")),
        "f1": float(f1_score(y_test, y_pred, pos_label="scam")),
        "classes": list(pipeline.classes_),
        "confusion_matrix": confusion_matrix(y_test, y_pred).tolist(),
        "train_samples": int(len(X_train)),
        "test_samples": int(len(X_test)),
    }

    print("=" * 60)
    print("MODEL TRAINING COMPLETE")
    print("=" * 60)
    print(f"Classes: {list(pipeline.classes_)}")
    print(f"Accuracy:  {metrics['accuracy']:.4f}")
    print(f"Precision: {metrics['precision']:.4f}")
    print(f"Recall:    {metrics['recall']:.4f}")
    print(f"F1 Score:  {metrics['f1']:.4f}")
    print(f"Confusion Matrix:\n{confusion_matrix(y_test, y_pred)}")
    print(f"Train samples: {metrics['train_samples']}, Test samples: {metrics['test_samples']}")
    print(classification_report(y_test, y_pred, target_names=["safe", "scam"]))

    return pipeline, metrics


def verify_predictions(pipeline: Pipeline) -> None:
    """Verify the model on known scam/safe examples."""
    test_cases = [
        ("Congratulations! You won £1000 cash. Call now to claim your prize.", "scam"),
        ("Hey, are you free this evening? Let's meet tomorrow.", "safe"),
        ("Your account has been selected for a reward. Click the link immediately to claim.", "scam"),
        ("Can you send me the project report before 5 PM?", "safe"),
        ("URGENT: Your bank account has been suspended. Verify your details now or it will be closed.", "scam"),
        ("Hi John, just checking in about the meeting tomorrow at 10am.", "safe"),
    ]

    print("\n" + "=" * 60)
    print("PREDICTION VERIFICATION")
    print("=" * 60)
    for text, expected in test_cases:
        proba = pipeline.predict_proba([text])[0]
        idx = int(np.argmax(proba))
        label = pipeline.classes_[idx]
        confidence = float(proba[idx])
        status = "PASS" if label == expected else "FAIL"
        print(f"{status} Expected={expected:5s} Got={label:5s} Confidence={confidence:.3f} | {text[:60]}...")


def main() -> None:
    """Train and save the model."""
    print(f"Loading dataset from {DATA_PATH}")
    df = load_dataset(DATA_PATH)
    print(f"Dataset loaded: {len(df)} samples")
    print(f"Class distribution:\n{df['label'].value_counts()}")

    pipeline, metrics = train_model(df)

    # Save the complete pipeline
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, OUTPUT_PATH)
    print(f"\nModel saved to {OUTPUT_PATH} ({OUTPUT_PATH.stat().st_size} bytes)")

    # Also save metrics for reference
    metrics_path = ROOT / "models" / "exports" / "metrics.json"
    import json

    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"Metrics saved to {metrics_path}")

    verify_predictions(pipeline)


if __name__ == "__main__":
    main()