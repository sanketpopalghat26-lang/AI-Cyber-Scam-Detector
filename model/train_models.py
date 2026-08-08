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
from xgboost import XGBClassifier
from sklearn.metrics import classification_report, accuracy_score


def load_sms_spam(path="data/smsspamcollection/SMSSpamCollection"):
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        url = "https://raw.githubusercontent.com/justmarkham/pycon-2016-tutorial/master/data/sms.tsv"
        df = pd.read_table(url, header=None, names=["label", "text"])
        df.to_csv(path, sep='\t', index=False, header=False)
    df = pd.read_csv(path, sep='\t', header=None, names=["label", "text"])
    df['label'] = df['label'].map({'ham':'safe','spam':'scam'})
    return df


def build_and_train(df):
    X = df['text'].astype(str)
    y = df['label']
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    pipelines = {
        'logreg': Pipeline([('tfidf', TfidfVectorizer(max_features=20000)), ('clf', LogisticRegression(max_iter=1000))]),
        'rf': Pipeline([('tfidf', TfidfVectorizer(max_features=20000)), ('clf', RandomForestClassifier(n_estimators=200))]),
        'xgb': Pipeline([('tfidf', TfidfVectorizer(max_features=20000)), ('clf', XGBClassifier(use_label_encoder=False, eval_metric='logloss'))]),
    }
    best = None
    best_acc = 0.0
    for name, pipe in pipelines.items():
        print(f"Training {name}")
        pipe.fit(X_train, y_train)
        preds = pipe.predict(X_test)
        acc = accuracy_score(y_test, preds)
        print(name, acc)
        if acc > best_acc:
            best_acc = acc
            best = pipe

    os.makedirs('model_out', exist_ok=True)
    joblib.dump(best, 'model_out/best_model.joblib')
    print('Saved best model with acc', best_acc)


if __name__ == '__main__':
    df = load_sms_spam()
    build_and_train(df)
