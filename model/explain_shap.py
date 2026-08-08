import joblib
import shap
import numpy as np


def explain(model_path='model_out/best_model.joblib', texts=None):
    model = joblib.load(model_path)
    if texts is None:
        texts = ["Free entry in 2 a wkly comp to win"]
    # If model is a pipeline with vectorizer
    try:
        vectorizer = model.named_steps.get('tfidf')
        clf = model.named_steps.get('clf')
        X = vectorizer.transform(texts)
        explainer = shap.LinearExplainer(clf, vectorizer.transform(["sample text"]))
        shap_vals = explainer.shap_values(X)
        return shap_vals
    except Exception as e:
        print('SHAP explain error', e)
        return None


if __name__ == '__main__':
    print(explain())
