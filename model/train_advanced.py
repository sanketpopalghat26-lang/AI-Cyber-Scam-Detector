"""
Advanced training: use sentence-transformers to generate embeddings and train a classifier.
Also provides a simple merge of public datasets into unified labels.
"""
import os
import joblib
import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report


def load_sms():
    url = "https://raw.githubusercontent.com/justmarkham/pycon-2016-tutorial/master/data/sms.tsv"
    df = pd.read_table(url, header=None, names=["label", "text"] )
    df['label'] = df['label'].map({'ham':'safe','spam':'scam'})
    return df


def load_fake_jobs():
    # Placeholder: if dataset available, load and label as 'scam' for suspicious postings
    return pd.DataFrame(columns=['label','text'])


def merge_datasets():
    parts = []
    parts.append(load_sms())
    parts.append(load_fake_jobs())
    df = pd.concat(parts, ignore_index=True)
    df = df.dropna().reset_index(drop=True)
    return df


def train():
    df = merge_datasets()
    X = df['text'].astype(str)
    y = df['label']
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model_name = 'all-MiniLM-L6-v2'
    embedder = SentenceTransformer(model_name)
    emb_train = embedder.encode(X_train.tolist(), show_progress_bar=True)
    emb_test = embedder.encode(X_test.tolist(), show_progress_bar=True)

    clf = LogisticRegression(max_iter=1000)
    clf.fit(emb_train, y_train)
    preds = clf.predict(emb_test)
    acc = accuracy_score(y_test, preds)
    print('Embedding+LR acc', acc)
    joblib.dump((embedder, clf), 'model_out/embed_clf.joblib')


if __name__ == '__main__':
    train()
