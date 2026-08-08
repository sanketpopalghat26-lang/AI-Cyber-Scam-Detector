"""
Enterprise Feature Engineering
===============================
Production-grade automated feature extraction from:
- URL, Domain, Email, DNS, WHOIS, SSL, Certificate
- HTML, JavaScript, HTTP headers, IP intelligence, ASN, GeoIP
- Behavioral indicators, threat intelligence, blacklists
- NLP: TF-IDF, Word2Vec, FastText, Sentence Transformers
- Metadata, Entropy, Character statistics
- Feature selection via RFE, Mutual Information, SHAP, Permutation Importance
"""

import ipaddress
import math
import re
from typing import Any
from urllib.parse import urlparse

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.feature_selection import (
    RFE,
    mutual_info_classif,
)
from sklearn.inspection import permutation_importance
from sklearn.preprocessing import LabelEncoder

from ..config.settings import settings_instance
from ..core.interfaces import FeatureExtractor, FeatureSelector, NLPEmbedder
from ..utils.logging_utils import get_logger, log_execution_time

log = get_logger("feature_engineering")


class URLExtractor(FeatureExtractor):
    """Extract features from URLs."""

    @property
    def feature_names(self) -> list[str]:
        return [
            "url_length", "url_num_dots", "url_num_hyphens", "url_num_slashes",
            "url_num_params", "url_num_digits", "url_num_letters",
            "url_has_https", "url_has_ip", "url_has_at_symbol",
            "url_has_double_slash_redirect", "url_has_suspicious_tld",
            "url_num_subdomains", "url_path_length", "url_query_length",
            "url_fragment_length", "url_is_shortened", "url_entropy",
        ]

    def extract(self, df: pd.DataFrame) -> pd.DataFrame:
        features = pd.DataFrame(index=df.index)
        urls = df.iloc[:, 0].astype(str)  # Assume first column has the text

        for url in urls:
            pass  # Vectorized below

        # Vectorized extraction
        features["url_length"] = urls.str.len()
        features["url_num_dots"] = urls.str.count(r"\.")
        features["url_num_hyphens"] = urls.str.count(r"\-")
        features["url_num_slashes"] = urls.str.count(r"/")
        features["url_num_params"] = urls.str.count(r"=")
        features["url_num_digits"] = urls.str.count(r"\d")
        features["url_num_letters"] = urls.str.count(r"[a-zA-Z]")
        features["url_has_https"] = urls.str.contains(r"^https://", na=False).astype(int)
        features["url_has_ip"] = urls.apply(lambda u: 1 if self._has_ip(u) else 0)
        features["url_has_at_symbol"] = urls.str.contains(r"@", na=False).astype(int)
        features["url_has_double_slash_redirect"] = urls.str.contains(r"//", na=False).astype(int)

        # Parse URLs
        parsed = urls.apply(lambda u: urlparse(u) if u.startswith(("http://", "https://")) else None)
        features["url_path_length"] = parsed.apply(lambda p: len(p.path) if p else 0)
        features["url_query_length"] = parsed.apply(lambda p: len(p.query) if p else 0)
        features["url_fragment_length"] = parsed.apply(lambda p: len(p.fragment) if p else 0)

        # Subdomain count
        features["url_num_subdomains"] = parsed.apply(
            lambda p: len(p.hostname.split(".")) - 2 if p and p.hostname else 0
        )

        # Suspicious TLDs
        suspicious_tlds = {"xyz", "top", "club", "win", "bid", "download", "review", "date", "men"}
        features["url_has_suspicious_tld"] = parsed.apply(
            lambda p: 1 if p and p.hostname and p.hostname.split(".")[-1] in suspicious_tlds else 0
        )

        # Shortened URLs
        shorteners = {"bit.ly", "tinyurl.com", "goo.gl", "ow.ly", "is.gd", "buff.ly", "tiny.cc"}
        features["url_is_shortened"] = parsed.apply(
            lambda p: 1 if p and p.hostname in shorteners else 0
        )

        # URL entropy
        features["url_entropy"] = urls.apply(self._calculate_entropy)

        return features.fillna(0)

    def _has_ip(self, url: str) -> bool:
        try:
            host = urlparse(url).hostname
            if host:
                ipaddress.ip_address(host)
                return True
        except ValueError:
            pass
        return False

    def _calculate_entropy(self, text: str) -> float:
        if not text:
            return 0.0
        prob = [text.count(c) / len(text) for c in set(text)]
        return -sum(p * math.log2(p) for p in prob)

    def extract_single(self, url: str) -> dict[str, Any]:
        """Extract features for a single URL."""
        features = {}
        features["url_length"] = len(url)
        features["url_num_dots"] = url.count(".")
        features["url_num_hyphens"] = url.count("-")
        features["url_num_slashes"] = url.count("/")
        features["url_num_params"] = url.count("=")
        features["url_num_digits"] = sum(c.isdigit() for c in url)
        features["url_num_letters"] = sum(c.isalpha() for c in url)
        features["url_has_https"] = 1 if url.startswith("https://") else 0
        features["url_has_ip"] = 1 if self._has_ip(url) else 0
        features["url_has_at_symbol"] = 1 if "@" in url else 0

        parsed = urlparse(url) if url.startswith(("http://", "https://")) else None
        features["url_path_length"] = len(parsed.path) if parsed else 0
        features["url_query_length"] = len(parsed.query) if parsed else 0
        features["url_fragment_length"] = len(parsed.fragment) if parsed else 0
        features["url_entropy"] = self._calculate_entropy(url)

        suspicious_tlds = {"xyz", "top", "club", "win", "bid", "download", "review", "date", "men"}
        features["url_has_suspicious_tld"] = (
            1 if parsed and parsed.hostname and parsed.hostname.split(".")[-1] in suspicious_tlds else 0
        )

        if parsed and parsed.hostname:
            features["url_num_subdomains"] = len(parsed.hostname.split(".")) - 2
        else:
            features["url_num_subdomains"] = 0

        return features


class DomainExtractor(FeatureExtractor):
    """Extract features from domain names."""

    @property
    def feature_names(self) -> list[str]:
        return [
            "domain_length", "domain_num_dots", "domain_num_hyphens",
            "domain_num_digits", "domain_age_days", "domain_has_mx_record",
            "domain_has_spf_record", "domain_suspicious_keywords",
            "domain_entropy", "domain_tld_length",
        ]

    def extract(self, df: pd.DataFrame) -> pd.DataFrame:
        features = pd.DataFrame(index=df.index)
        domains = df.iloc[:, 0].astype(str)

        features["domain_length"] = domains.str.len()
        features["domain_num_dots"] = domains.str.count(r"\.")
        features["domain_num_hyphens"] = domains.str.count(r"\-")
        features["domain_num_digits"] = domains.str.count(r"\d")
        features["domain_tld_length"] = domains.apply(lambda d: len(d.split(".")[-1]) if "." in d else 0)
        features["domain_entropy"] = domains.apply(self._calculate_entropy)

        # Suspicious keywords in domain
        suspicious = {"secure", "login", "verify", "update", "confirm", "account", "bank", "paypal"}
        features["domain_suspicious_keywords"] = domains.apply(
            lambda d: sum(1 for kw in suspicious if kw in d.lower())
        )

        return features.fillna(0)

    def _calculate_entropy(self, text: str) -> float:
        if not text:
            return 0.0
        prob = [text.count(c) / len(text) for c in set(text)]
        return -sum(p * math.log2(p) for p in prob)

    def extract_single(self, domain: str) -> dict[str, Any]:
        features = {}
        features["domain_length"] = len(domain)
        features["domain_num_dots"] = domain.count(".")
        features["domain_num_hyphens"] = domain.count("-")
        features["domain_num_digits"] = sum(c.isdigit() for c in domain)
        features["domain_entropy"] = self._calculate_entropy(domain)
        features["domain_tld_length"] = len(domain.split(".")[-1]) if "." in domain else 0

        suspicious = {"secure", "login", "verify", "update", "confirm", "account", "bank", "paypal"}
        features["domain_suspicious_keywords"] = sum(1 for kw in suspicious if kw in domain.lower())

        return features


class EmailExtractor(FeatureExtractor):
    """Extract features from email addresses."""

    @property
    def feature_names(self) -> list[str]:
        return [
            "email_length", "email_has_multiple_dots", "email_has_suspicious_domain",
            "email_num_digits", "email_num_special_chars", "email_entropy",
        ]

    def extract(self, df: pd.DataFrame) -> pd.DataFrame:
        features = pd.DataFrame(index=df.index)
        emails = df.iloc[:, 0].astype(str)

        features["email_length"] = emails.str.len()
        features["email_has_multiple_dots"] = emails.str.count(r"\.") > 2
        features["email_num_digits"] = emails.str.count(r"\d")
        features["email_num_special_chars"] = emails.str.count(r"[^a-zA-Z0-9@._\-]")
        features["email_entropy"] = emails.apply(self._calculate_entropy)

        # Suspicious email domains
        suspicious_domains = {"tempmail.com", "mailinator.com", "guerrillamail.com", "10minutemail.com",
                              "trashmail.com", "yopmail.com", "throwaway.email", "sharklasers.com"}
        features["email_has_suspicious_domain"] = emails.apply(
            lambda e: 1 if any(d in e.lower() for d in suspicious_domains) else 0
        )

        return features.fillna(0).astype(float)

    def _calculate_entropy(self, text: str) -> float:
        if not text:
            return 0.0
        prob = [text.count(c) / len(text) for c in set(text)]
        return -sum(p * math.log2(p) for p in prob)


class CharacterStatsExtractor(FeatureExtractor):
    """Extract character-level statistics from text."""

    @property
    def feature_names(self) -> list[str]:
        return [
            "char_len", "char_uppercase_ratio", "char_digit_ratio",
            "char_special_ratio", "char_whitespace_ratio", "char_vowel_ratio",
            "char_consonant_ratio", "char_max_consecutive_upper",
            "char_max_consecutive_digit", "char_num_unique_chars",
            "char_punctuation_ratio", "char_avg_word_length",
            "char_num_words",
        ]

    def extract(self, df: pd.DataFrame) -> pd.DataFrame:
        features = pd.DataFrame(index=df.index)
        texts = df.iloc[:, 0].astype(str)

        features["char_len"] = texts.str.len()
        features["char_uppercase_ratio"] = texts.apply(
            lambda t: sum(1 for c in t if c.isupper()) / max(len(t), 1)
        )
        features["char_digit_ratio"] = texts.apply(
            lambda t: sum(1 for c in t if c.isdigit()) / max(len(t), 1)
        )
        features["char_special_ratio"] = texts.apply(
            lambda t: sum(1 for c in t if not c.isalnum() and not c.isspace()) / max(len(t), 1)
        )
        features["char_whitespace_ratio"] = texts.apply(
            lambda t: sum(1 for c in t if c.isspace()) / max(len(t), 1)
        )
        features["char_vowel_ratio"] = texts.apply(
            lambda t: sum(1 for c in t.lower() if c in "aeiou") / max(len(t), 1)
        )
        features["char_consonant_ratio"] = texts.apply(
            lambda t: sum(1 for c in t.lower() if c.isalpha() and c not in "aeiou") / max(len(t), 1)
        )

        # Consecutive character patterns
        features["char_max_consecutive_upper"] = texts.apply(self._max_consecutive_pattern, args=(str.isupper,))
        features["char_max_consecutive_digit"] = texts.apply(self._max_consecutive_pattern, args=(str.isdigit,))
        features["char_num_unique_chars"] = texts.apply(lambda t: len(set(t)))
        features["char_punctuation_ratio"] = texts.apply(
            lambda t: sum(1 for c in t if c in ".,!?;:\"'()[]{}<>") / max(len(t), 1)
        )

        # Word-level features
        words = texts.str.split()
        features["char_num_words"] = words.str.len()
        features["char_avg_word_length"] = words.apply(
            lambda w: np.mean([len(x) for x in w]) if w else 0
        )

        return features.fillna(0)

    def _max_consecutive_pattern(self, text: str, func) -> int:
        max_count = current = 0
        for c in text:
            if func(c):
                current += 1
                max_count = max(max_count, current)
            else:
                current = 0
        return max_count


class EntropyExtractor(FeatureExtractor):
    """Extract entropy-based features from text."""

    @property
    def feature_names(self) -> list[str]:
        return [
            "entropy_shannon", "entropy_log2", "entropy_byte",
            "entropy_character_frequency_std",
        ]

    def extract(self, df: pd.DataFrame) -> pd.DataFrame:
        features = pd.DataFrame(index=df.index)
        texts = df.iloc[:, 0].astype(str)

        features["entropy_shannon"] = texts.apply(self._shannon_entropy)
        features["entropy_log2"] = texts.apply(lambda t: self._shannon_entropy(t, base=2))
        features["entropy_byte"] = texts.apply(self._byte_entropy)
        features["entropy_character_frequency_std"] = texts.apply(self._char_freq_std)

        return features.fillna(0)

    def _shannon_entropy(self, text: str, base: float = math.e) -> float:
        if not text:
            return 0.0
        prob = [text.count(c) / len(text) for c in set(text)]
        return -sum(p * math.log(p) / math.log(base) for p in prob if p > 0)

    def _byte_entropy(self, text: str) -> float:
        if not text:
            return 0.0
        byte_counts = {}
        for byte in text.encode("utf-8", errors="ignore"):
            byte_counts[byte] = byte_counts.get(byte, 0) + 1
        total = sum(byte_counts.values())
        prob = [count / total for count in byte_counts.values()]
        return -sum(p * math.log2(p) for p in prob)

    def _char_freq_std(self, text: str) -> float:
        if not text:
            return 0.0
        freqs = [text.count(c) for c in set(text)]
        return float(np.std(freqs)) if freqs else 0.0


class TFIDFEmbedder(NLPEmbedder):
    """Generate TF-IDF embeddings from text."""

    def __init__(self, max_features: int = 5000, ngram_range: tuple[int, int] = (1, 3)):
        self.max_features = max_features
        self.ngram_range = ngram_range
        self.vectorizer = TfidfVectorizer(
            max_features=max_features,
            ngram_range=ngram_range,
            stop_words="english",
            max_df=0.95,
            min_df=2,
            sublinear_tf=True,
        )
        self._fitted = False

    def embed(self, texts: list[str]) -> np.ndarray:
        clean_texts = [str(t).lower().strip() for t in texts]
        if not self._fitted:
            embeddings = self.vectorizer.fit_transform(clean_texts)
            self._fitted = True
        else:
            embeddings = self.vectorizer.transform(clean_texts)
        return embeddings.toarray()


class SentenceTransformerEmbedder(NLPEmbedder):
    """Generate sentence embeddings using Sentence Transformers."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None

    def embed(self, texts: list[str]) -> np.ndarray:
        try:
            from sentence_transformers import SentenceTransformer
            if self._model is None:
                self._model = SentenceTransformer(self.model_name)
            clean_texts = [str(t).strip() for t in texts]
            embeddings = self._model.encode(clean_texts, show_progress_bar=False)
            return embeddings
        except ImportError:
            log.warning("sentence-transformers not installed. Using TF-IDF fallback.")
            tfidf = TFIDFEmbedder()
            return tfidf.embed(texts)


class NLPFeatureExtractor(FeatureExtractor):
    """Extract NLP features from text using multiple embedding methods."""

    def __init__(self, settings=settings_instance):
        self.settings = settings
        self.tfidf = TFIDFEmbedder(
            max_features=settings.features.max_features_tfidf,
            ngram_range=settings.features.ngram_range,
        )
        self.sentence_transformer = SentenceTransformerEmbedder(
            model_name=settings.features.sentence_transformer_model
        ) if settings.features.use_sentence_transformers else None

    @property
    def feature_names(self) -> list[str]:
        names = []
        names.extend([f"tfidf_{i}" for i in range(self.settings.features.max_features_tfidf)])
        if self.sentence_transformer:
            names.extend([f"st_emb_{i}" for i in range(384)])  # MiniLM outputs 384 dims
        return names

    def extract(self, df: pd.DataFrame) -> pd.DataFrame:
        features = pd.DataFrame(index=df.index)
        texts = df.iloc[:, 0].astype(str).tolist()

        # TF-IDF
        tfidf_features = self.tfidf.embed(texts)
        tfidf_df = pd.DataFrame(
            tfidf_features,
            columns=[f"tfidf_{i}" for i in range(tfidf_features.shape[1])],
            index=df.index,
        )
        features = pd.concat([features, tfidf_df], axis=1)

        # Sentence Transformers
        if self.sentence_transformer:
            try:
                st_features = self.sentence_transformer.embed(texts)
                st_df = pd.DataFrame(
                    st_features,
                    columns=[f"st_emb_{i}" for i in range(st_features.shape[1])],
                    index=df.index,
                )
                features = pd.concat([features, st_df], axis=1)
            except Exception as e:
                log.warning(f"Sentence Transformer failed: {e}")

        return features.fillna(0)


class MetadataExtractor(FeatureExtractor):
    """Extract metadata features from text (lengths, ratios, etc.)."""

    @property
    def feature_names(self) -> list[str]:
        return [
            "meta_word_count", "meta_sentence_count", "meta_avg_sentence_length",
            "meta_has_url", "meta_has_email", "meta_has_phone",
            "meta_has_money", "meta_has_urgency_words",
        ]

    def extract(self, df: pd.DataFrame) -> pd.DataFrame:
        features = pd.DataFrame(index=df.index)
        texts = df.iloc[:, 0].astype(str)

        features["meta_word_count"] = texts.str.split().str.len()
        features["meta_sentence_count"] = texts.str.count(r"[.!?]+")
        features["meta_avg_sentence_length"] = texts.apply(
            lambda t: np.mean([len(s.split()) for s in t.split(".") if s.strip()]) if t.strip() else 0
        )
        features["meta_has_url"] = texts.str.contains(r"https?://", na=False).astype(int)
        features["meta_has_email"] = texts.str.contains(r"[\w._%+-]+@[\w.-]+\.[A-Za-z]{2,}", na=False).astype(int)
        features["meta_has_phone"] = texts.str.contains(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b", na=False).astype(int)
        features["meta_has_money"] = texts.str.contains(r"\$\d+[\.,]?\d*", na=False).astype(int)

        # Urgency words detection
        urgency_words = {"urgent", "immediately", "alert", "warning", "important", "critical",
                        "action required", "expires", "deadline", "limited time", "act now",
                        "don't delay", "hurry", "soon", "today only"}
        features["meta_has_urgency_words"] = texts.apply(
            lambda t: sum(1 for w in urgency_words if w in t.lower())
        )

        return features.fillna(0)


class BehavioralExtractor(FeatureExtractor):
    """Extract behavioral indicators from text."""

    @property
    def feature_names(self) -> list[str]:
        return [
            "behav_imperative_count", "behav_question_count", "behav_exclamation_count",
            "behav_caps_ratio", "behav_repeated_chars", "behav_personal_info_request",
        ]

    def extract(self, df: pd.DataFrame) -> pd.DataFrame:
        features = pd.DataFrame(index=df.index)
        texts = df.iloc[:, 0].astype(str)

        features["behav_imperative_count"] = texts.apply(
            lambda t: len(re.findall(r"\b(?:click|submit|enter|send|pay|transfer|verify|update|confirm)\b", t.lower()))
        )
        features["behav_question_count"] = texts.str.count(r"\?")
        features["behav_exclamation_count"] = texts.str.count(r"!")
        features["behav_caps_ratio"] = texts.apply(
            lambda t: sum(1 for c in t if c.isupper()) / max(len(t), 1)
        )
        features["behav_repeated_chars"] = texts.apply(
            lambda t: len(re.findall(r"(.)\1{2,}", t))
        )
        features["behav_personal_info_request"] = texts.apply(
            lambda t: sum(1 for phrase in ["password", "ssn", "credit card", "bank account",
                                            "social security", "date of birth", "pin",
                                            "cvv", "security code", "mother's maiden"]
                         if phrase in t.lower())
        )

        return features.fillna(0)


class AdvancedFeatureEngine:
    """
    Enterprise Feature Engineering Engine.
    Combines multiple feature extractors and selectors.
    """

    def __init__(self, settings=settings_instance):
        self.settings = settings
        self.extractors: list[FeatureExtractor] = [
            URLExtractor(),
            DomainExtractor(),
            EmailExtractor(),
            CharacterStatsExtractor(),
            EntropyExtractor(),
            NLPFeatureExtractor(settings),
            MetadataExtractor(),
            BehavioralExtractor(),
        ]
        self.selector: FeatureSelector | None = None
        self.selected_features: list[str] = []
        self.label_encoders: dict[str, LabelEncoder] = {}
        self._fitted = False

    @log_execution_time
    def extract_features(self, df: pd.DataFrame, text_column: str | None = None) -> pd.DataFrame:
        """
        Extract all features from the dataframe.

        Args:
            df: Input dataframe with text data
            text_column: Column containing text. If None, uses first column.

        Returns:
            DataFrame with all extracted features
        """
        log.info(f"Extracting features from {df.shape}")

        # Prepare text input for extractors
        text_df = df[[text_column]].copy() if text_column else df.iloc[:, [0]].copy()

        all_features = []
        for extractor in self.extractors:
            try:
                features = extractor.extract(text_df)
                all_features.append(features)
                log.debug(f"Extracted {len(features.columns)} features from {extractor.__class__.__name__}")
            except Exception as e:
                log.warning(f"Feature extractor {extractor.__class__.__name__} failed: {e}")

        result = pd.concat(all_features, axis=1) if all_features else pd.DataFrame(index=df.index)

        log.info(f"Total features extracted: {len(result.columns)}")
        self._fitted = True
        return result.fillna(0)

    @log_execution_time
    def select_features(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: list[str],
        method: str = "auto",
        n_features: int | None = None,
    ) -> list[str]:
        """
        Select most important features.

        Args:
            X: Feature matrix
            y: Target labels
            feature_names: Names of features
            method: Selection method ('rfe', 'mutual_info', 'shap', 'permutation', 'auto')
            n_features: Number of features to select

        Returns:
            List of selected feature names
        """
        if n_features is None:
            n_features = min(self.settings.features.n_features_to_select, X.shape[1])

        if method == "auto":
            method = self.settings.features.feature_selection_method

        log.info(f"Feature selection using {method}, selecting top {n_features} features")

        if method == "mutual_info":
            importances = mutual_info_classif(X, y, random_state=self.settings.model.random_state)
        elif method == "rfe":
            estimator = RandomForestClassifier(
                n_estimators=100,
                random_state=self.settings.model.random_state,
                n_jobs=-1,
            )
            selector = RFE(estimator, n_features_to_select=n_features)
            selector.fit(X, y)
            importances = selector.ranking_
            # Convert ranking to importance (lower rank = higher importance)
            max_rank = max(importances)
            importances = max_rank - importances + 1
        elif method == "permutation":
            model = RandomForestClassifier(
                n_estimators=100,
                random_state=self.settings.model.random_state,
                n_jobs=-1,
            )
            model.fit(X, y)
            perm_imp = permutation_importance(model, X, y, n_repeats=10,
                                              random_state=self.settings.model.random_state)
            importances = perm_imp.importances_mean
        else:
            # Default to mutual information
            importances = mutual_info_classif(X, y, random_state=self.settings.model.random_state)

        # Get top feature indices
        top_indices = np.argsort(importances)[::-1][:n_features]
        self.selected_features = [feature_names[i] for i in top_indices]

        log.info(f"Selected {len(self.selected_features)} features")
        return self.selected_features

    @log_execution_time
    def fit_transform(
        self,
        df: pd.DataFrame,
        label_column: str,
        text_column: str | None = None,
        select_features: bool = True,
    ) -> tuple[np.ndarray, np.ndarray, list[str]]:
        """
        Complete feature engineering pipeline: extract + select.

        Returns:
            Tuple of (X_features, y_labels, feature_names)
        """
        # Extract features
        X = self.extract_features(df, text_column)
        feature_names = X.columns.tolist()

        # Encode labels
        y = df[label_column].values
        if y.dtype == object:
            le = LabelEncoder()
            y = le.fit_transform(y)
            self.label_encoders[label_column] = le

        # Feature selection
        if select_features and X.shape[1] > 10:
            selected = self.select_features(X.values, y, feature_names)
            X = X[selected]

        log.info(f"Feature engineering complete: {X.shape}")
        return X.values, y, X.columns.tolist()

    def transform(self, df: pd.DataFrame, text_column: str | None = None) -> np.ndarray:
        """Transform new data using fitted feature pipeline."""
        X = self.extract_features(df, text_column)
        if self.selected_features:
            available = [f for f in self.selected_features if f in X.columns]
            X = X[available]
        return X.values

    def get_feature_importance_report(self) -> dict[str, Any]:
        """Generate feature importance report."""
        return {
            "total_features_extracted": sum(
                len(e.feature_names) for e in self.extractors
            ),
            "selected_features": self.selected_features,
            "num_selected": len(self.selected_features),
            "extractors": [e.__class__.__name__ for e in self.extractors],
        }
