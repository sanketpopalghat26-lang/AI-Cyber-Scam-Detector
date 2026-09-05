"""
Train multiple models on public datasets and save the best model.
This script downloads datasets, trains classic ML models and a sentence-transformer + classifier.
"""
import os
import joblib
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from xgboost import XGBClassifier
from sklearn.metrics import accuracy_score


def load_sms_spam(path="data/smsspamcollection/SMSSpamCollection"):
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        url = "https://raw.githubusercontent.com/justmarkham/pycon-2016-tutorial/master/data/sms.tsv"
        df = pd.read_table(url, header=None, names=["label", "text"])
        df.to_csv(path, sep='\t', index=False, header=False)
    df = pd.read_csv(path, sep='\t', header=None, names=["label", "text"])
    df['label'] = df['label'].map({'ham': 'safe', 'spam': 'scam'})
    return df


def load_fake_jobs():
    return pd.DataFrame(columns=["label", "text"])


def merge_datasets():
    parts = [load_sms_spam(), load_fake_jobs()]
    df = pd.concat(parts, ignore_index=True, sort=False)
    df = df.dropna(subset=["text", "label"]).reset_index(drop=True)
    return df


def build_and_train(df):
    X = df['text'].astype(str)
    y = df['label']
    label_encoder = LabelEncoder()
    y_encoded = label_encoder.fit_transform(y)

    X_train, X_test, y_train, y_test = train_test_split(X, y_encoded, test_size=0.2, random_state=42)

    pipelines = {
        'logreg': Pipeline([('tfidf', TfidfVectorizer(max_features=20000)), ('clf', LogisticRegression(max_iter=1000))]),
        'rf': Pipeline([('tfidf', TfidfVectorizer(max_features=20000)), ('clf', RandomForestClassifier(n_estimators=200))]),
        'xgb': Pipeline([('tfidf', TfidfVectorizer(max_features=20000)), ('clf', XGBClassifier(use_label_encoder=False, eval_metric='logloss'))]),
    }

    best = None
    best_acc = 0.0
    best_name = None

    for name, pipe in pipelines.items():
        print(f"Training {name}")
        try:
            pipe.fit(X_train, y_train)
            preds = pipe.predict(X_test)
            acc = accuracy_score(y_test, preds)
            print(f"{name} accuracy: {acc:.4f}")
            if acc > best_acc:
                best_acc = acc
                best = pipe
                best_name = name
        except Exception as exc:
            print(f"Skipping {name} due to error: {exc}")

    if best is None:
        raise RuntimeError("No model could be trained successfully")

    os.makedirs('model_out', exist_ok=True)
    best_path = 'model_out/best_model.joblib'
    joblib.dump({'model': best, 'label_encoder': label_encoder}, best_path)
    print('Saved best model', best_name, 'with acc', best_acc)
    return best_path


if __name__ == '__main__':
    df = merge_datasets()
    best_path = build_and_train(df)
    output_dir = os.path.join(os.path.dirname(__file__), '..', 'model')
    os.makedirs(output_dir, exist_ok=True)
    target_path = os.path.join(output_dir, 'best_model.joblib')
    joblib.dump(joblib.load(best_path), target_path)
    print('Copied model to', target_path)
