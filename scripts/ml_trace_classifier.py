"""
Phase 1 of the approved ML extension: a trace/declared segment classifier.

Weakly supervised from the existing rule-based splitter
(allergen_matcher.split_declared_and_trace_text) - no new manual
annotation. Trained ONLY on the 963-product leak-free dev set (the
1,263-product set minus all 300 held-out product codes, which overlap
completely - see ML_EXTENSION_PLAN.md). The 300-product held-out set is
never read by this script.

This script:
1. Builds weak-labeled clause-level training data from the dev set.
2. Trains TF-IDF(word) + TF-IDF(char n-gram) + Logistic Regression via
   stratified 5-fold CV (a sanity check against the classifier's own
   bootstrap source, not the real evaluation).
3. Fits a final model on all dev data.
4. Runs the REAL comparison: rule-only splitting vs. classifier-based
   splitting, both feeding the same unmodified downstream matching code,
   evaluated on the same 963-product set with the same metric methodology
   as scripts/benchmark_matcher.py.
5. Saves every output as a new, versioned file. Nothing existing is
   overwritten. allergen_matcher.py's rule-based splitter is never
   modified - the frozen baseline stays exactly reproducible.

Usage:
    ./venv/bin/python -m scripts.ml_trace_classifier
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from scipy.sparse import hstack
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import precision_recall_fscore_support
from sklearn.model_selection import StratifiedKFold, cross_val_predict

from scripts.allergen_matcher import (
    load_dictionary,
    split_declared_and_trace_text,
    detect_allergen_matches,
    normalize_text,
)


BASE_DIR = Path(__file__).resolve().parent.parent
DATASET_FILE = BASE_DIR / "data" / "cleaned_products.csv"
HELDOUT_FILE = BASE_DIR / "data" / "research" / "ground_truth.csv"

OUTPUT_DIR = BASE_DIR / "data" / "research" / "ml" / "trace_classifier_v1"

MIN_CLAUSE_LEN = 3
RANDOM_STATE = 42


# ============================================================
# WEAK-LABEL DATASET CONSTRUCTION
# ============================================================

def split_into_clauses(text: str) -> list[str]:
    """
    Split on sentence/clause boundaries (period, semicolon) - the
    punctuation real ingredient labels typically use to set a
    precautionary statement apart as its own clause. A text with no
    such punctuation stays as one clause; that's an intentional,
    disclosed limitation (see ML_EXTENSION_PLAN.md), not a bug.
    """
    if not text:
        return []

    parts = re.split(r"[.;]+", text)

    return [p.strip() for p in parts if len(p.strip()) >= MIN_CLAUSE_LEN]


def load_leak_free_dev_set() -> pd.DataFrame:
    df = pd.read_csv(DATASET_FILE, dtype={"code": str})

    heldout = pd.read_csv(HELDOUT_FILE, dtype={"code": str})
    heldout_codes = set(heldout["code"])

    df["ingredients_text"] = df["ingredients_text"].fillna("").astype(str)
    df = df[df["ingredients_text"].str.strip() != ""].copy()

    before = len(df)
    df = df[~df["code"].isin(heldout_codes)].copy()
    after = len(df)

    print(f"Dev set: {before} products with ingredient text, "
          f"{before - after} excluded as held-out overlap, "
          f"{after} remain (leak-free).")

    return df.reset_index(drop=True)


def build_weak_labeled_clauses(dev_df: pd.DataFrame) -> pd.DataFrame:
    rows = []

    for _, row in dev_df.iterrows():
        text = str(row["ingredients_text"])

        declared_text, trace_text = split_declared_and_trace_text(text)

        for clause in split_into_clauses(declared_text):
            rows.append({"code": row["code"], "text": clause, "label": 0})

        for clause in split_into_clauses(trace_text):
            rows.append({"code": row["code"], "text": clause, "label": 1})

    clauses = pd.DataFrame(rows)

    print(f"Weak-labeled clauses: {len(clauses)} total "
          f"({(clauses['label'] == 0).sum()} declared, "
          f"{(clauses['label'] == 1).sum()} trace)")

    return clauses


# ============================================================
# FEATURES
# ============================================================

class ClauseFeaturizer:
    """
    Word TF-IDF (1-2 grams) + character TF-IDF (3-5 grams, word-boundary
    aware) concatenated. Character n-grams matter here specifically
    because the same downstream pipeline also has to work on OCR text,
    which corrupts characters more often than it corrupts whole-word
    choice.
    """

    def __init__(self):
        self.word_vec = TfidfVectorizer(
            ngram_range=(1, 2),
            min_df=2,
            sublinear_tf=True,
        )
        self.char_vec = TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(3, 5),
            min_df=2,
            sublinear_tf=True,
        )

    def fit_transform(self, texts):
        normalized = [normalize_text(t) for t in texts]
        word_features = self.word_vec.fit_transform(normalized)
        char_features = self.char_vec.fit_transform(normalized)
        return hstack([word_features, char_features]).tocsr()

    def transform(self, texts):
        normalized = [normalize_text(t) for t in texts]
        word_features = self.word_vec.transform(normalized)
        char_features = self.char_vec.transform(normalized)
        return hstack([word_features, char_features]).tocsr()


# ============================================================
# ML-BASED SEGMENTATION (mirrors allergen_matcher.analyze_ingredient_text,
# but with classifier-based splitting instead of the rule-based one -
# split_declared_and_trace_text() itself is never touched)
# ============================================================

def ml_split_declared_and_trace_text(text, featurizer, classifier):
    if text is None:
        return "", ""

    original = str(text)
    clauses = split_into_clauses(original)

    if not clauses:
        return original.strip(), ""

    features = featurizer.transform(clauses)
    predictions = classifier.predict(features)

    declared = [c for c, p in zip(clauses, predictions) if p == 0]
    trace = [c for c, p in zip(clauses, predictions) if p == 1]

    return " ".join(declared).strip(), " ".join(trace).strip()


def analyze_ingredient_text_ml(text, dictionary, featurizer, classifier):
    declared_text, trace_text = ml_split_declared_and_trace_text(
        text, featurizer, classifier
    )

    declared_result = detect_allergen_matches(declared_text, dictionary)
    trace_result = detect_allergen_matches(trace_text, dictionary)

    declared = declared_result["detected"]
    trace = trace_result["detected"]

    if declared:
        risk = "AVOID"
    elif trace:
        risk = "CAUTION"
    else:
        risk = "SAFE"

    return {
        "declared_allergens": sorted(declared),
        "trace_allergens": sorted(trace),
        "risk": risk,
    }


# ============================================================
# TAG PARSING (mirrors scripts/benchmark_matcher.py exactly, for a
# directly comparable evaluation)
# ============================================================

TAG_TO_ALLERGEN = {
    "en:milk": "milk",
    "en:eggs": "egg",
    "en:peanuts": "peanut",
    "en:nuts": "tree_nut",
    "en:soybeans": "soy",
    "en:gluten": "wheat_gluten",
    "en:wheat": "wheat_gluten",
    "en:fish": "fish",
    "en:crustaceans": "shellfish",
    "en:molluscs": "shellfish",
    "en:sesame-seeds": "sesame",
}


def parse_tags(value):
    if pd.isna(value):
        return set()

    text = str(value).strip()
    if not text:
        return set()

    text = text.strip("[]")
    parts = re.split(r"[,|;]", text)

    result = set()
    for part in parts:
        tag = part.strip().strip("'\"").lower()
        if tag in TAG_TO_ALLERGEN:
            result.add(TAG_TO_ALLERGEN[tag])

    return result


def multilabel_metrics(records, true_key, pred_key):
    labels = sorted(
        set(a for r in records for a in r[true_key] | r[pred_key])
    )

    if not labels:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0, "support": 0}

    y_true = [[int(l in r[true_key]) for l in labels] for r in records]
    y_pred = [[int(l in r[pred_key]) for l in labels] for r in records]

    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average="micro", zero_division=0,
    )

    support = sum(len(r[true_key]) for r in records)

    return {
        "precision": round(float(precision), 4),
        "recall": round(float(recall), 4),
        "f1": round(float(f1), 4),
        "support": int(support),
    }


def exact_match_rate(records, true_key, pred_key):
    if not records:
        return 0.0
    matches = sum(r[true_key] == r[pred_key] for r in records)
    return round(matches / len(records), 4)


# ============================================================
# DOWNSTREAM COMPARISON: rule-only vs. classifier-based splitting,
# BOTH on the same 963-product leak-free set, same metric methodology
# as scripts/benchmark_matcher.py.
# ============================================================

def run_downstream_comparison(dev_df, dictionary, featurizer, classifier):
    rule_records = []
    ml_records = []

    for _, row in dev_df.iterrows():
        text = row["ingredients_text"]

        true_allergens = parse_tags(row.get("allergens_tags", ""))
        true_traces = parse_tags(row.get("traces_tags", ""))

        # --- rule-only (recomputed fresh on the 963-set, for a fair
        # apples-to-apples comparison; allergen_matcher.py itself is
        # untouched) ---
        rule_declared_text, rule_trace_text = split_declared_and_trace_text(text)
        rule_declared = detect_allergen_matches(rule_declared_text, dictionary)["detected"]
        rule_trace = detect_allergen_matches(rule_trace_text, dictionary)["detected"]

        rule_records.append({
            "reference_allergens": true_allergens,
            "predicted_allergens": rule_declared,
            "reference_traces": true_traces,
            "predicted_traces": rule_trace,
        })

        # --- classifier-based splitting ---
        ml_result = analyze_ingredient_text_ml(text, dictionary, featurizer, classifier)

        ml_records.append({
            "reference_allergens": true_allergens,
            "predicted_allergens": set(ml_result["declared_allergens"]),
            "reference_traces": true_traces,
            "predicted_traces": set(ml_result["trace_allergens"]),
        })

    def summarize(records):
        return {
            "declared": {
                **multilabel_metrics(records, "reference_allergens", "predicted_allergens"),
                "exact_match": exact_match_rate(records, "reference_allergens", "predicted_allergens"),
            },
            "trace": {
                **multilabel_metrics(records, "reference_traces", "predicted_traces"),
                "exact_match": exact_match_rate(records, "reference_traces", "predicted_traces"),
            },
        }

    return summarize(rule_records), summarize(ml_records)


# ============================================================
# MAIN
# ============================================================

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    dictionary = load_dictionary()

    dev_df = load_leak_free_dev_set()

    clauses = build_weak_labeled_clauses(dev_df)

    featurizer = ClauseFeaturizer()
    X = featurizer.fit_transform(clauses["text"].tolist())
    y = clauses["label"].to_numpy()

    # --- Cross-validated sanity check (against the classifier's own
    # bootstrap source - expected to be high, this is NOT the real
    # evaluation, just confirms the model learned something coherent) ---
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    base_clf = LogisticRegression(
        max_iter=2000,
        class_weight="balanced",
        random_state=RANDOM_STATE,
    )

    cv_pred = cross_val_predict(base_clf, X, y, cv=cv)
    cv_precision, cv_recall, cv_f1, _ = precision_recall_fscore_support(
        y, cv_pred, average="binary", zero_division=0,
    )

    print()
    print("=" * 70)
    print("CROSS-VALIDATED SANITY CHECK (vs. own weak-label bootstrap)")
    print("=" * 70)
    print(f"Precision={cv_precision:.4f} Recall={cv_recall:.4f} F1={cv_f1:.4f}")

    # --- Fit final model on all dev clauses ---
    final_clf = LogisticRegression(
        max_iter=2000,
        class_weight="balanced",
        random_state=RANDOM_STATE,
    )
    final_clf.fit(X, y)

    # --- The real evaluation: downstream declared/trace metrics ---
    print()
    print("Running downstream comparison (rule-only vs. classifier-based "
          "splitting) on the 963-product leak-free set...")

    rule_summary, ml_summary = run_downstream_comparison(
        dev_df, dictionary, featurizer, final_clf
    )

    print()
    print("=" * 70)
    print("DOWNSTREAM COMPARISON — 963-product leak-free dev set")
    print("=" * 70)
    print(f"{'':12s} {'Precision':>10s} {'Recall':>8s} {'F1':>8s} {'Exact':>8s}")
    for key in ("declared", "trace"):
        r = rule_summary[key]
        m = ml_summary[key]
        print(f"[rule ] {key:10s} {r['precision']:>10.4f} {r['recall']:>8.4f} {r['f1']:>8.4f} {r['exact_match']:>8.4f}")
        print(f"[ml   ] {key:10s} {m['precision']:>10.4f} {m['recall']:>8.4f} {m['f1']:>8.4f} {m['exact_match']:>8.4f}")

    declared_wins = ml_summary["declared"]["f1"] > rule_summary["declared"]["f1"]
    trace_wins = ml_summary["trace"]["f1"] > rule_summary["trace"]["f1"]
    declared_not_much_worse = ml_summary["declared"]["f1"] >= rule_summary["declared"]["f1"] - 0.01

    go_live = trace_wins and declared_not_much_worse

    print()
    print("=" * 70)
    print(f"VERDICT: {'GO LIVE' if go_live else 'DO NOT GO LIVE'}")
    print("=" * 70)
    print(f"Trace F1 improved: {trace_wins} "
          f"({rule_summary['trace']['f1']:.4f} -> {ml_summary['trace']['f1']:.4f})")
    print(f"Declared F1 not meaningfully worse (>= baseline - 0.01): "
          f"{declared_not_much_worse} "
          f"({rule_summary['declared']['f1']:.4f} -> {ml_summary['declared']['f1']:.4f})")

    # --- Save everything, versioned ---
    joblib.dump(
        {"featurizer": featurizer, "classifier": final_clf},
        OUTPUT_DIR / "model.joblib",
    )

    with (OUTPUT_DIR / "cv_sanity_check.json").open("w", encoding="utf-8") as f:
        json.dump({
            "note": (
                "Cross-validated against the classifier's own weak-label "
                "bootstrap source (the rule-based splitter). High scores "
                "here are expected and do NOT by themselves indicate the "
                "classifier improves on the rules - see "
                "downstream_comparison.json for the real evaluation."
            ),
            "precision": round(float(cv_precision), 4),
            "recall": round(float(cv_recall), 4),
            "f1": round(float(cv_f1), 4),
            "n_clauses": len(clauses),
            "n_declared_clauses": int((clauses["label"] == 0).sum()),
            "n_trace_clauses": int((clauses["label"] == 1).sum()),
        }, f, indent=2)

    with (OUTPUT_DIR / "downstream_comparison.json").open("w", encoding="utf-8") as f:
        json.dump({
            "evaluation_set": (
                "963-product leak-free dev set (1,263-product baseline "
                "minus all 300 held-out product codes, which fully "
                "overlap with it - see ML_EXTENSION_PLAN.md). NOT the "
                "same set as the historical 1,263-product "
                "matcher_summary.json, which includes the 300 held-out "
                "products and is therefore not a valid comparison basis "
                "for this ML work."
            ),
            "held_out_300_touched": False,
            "n_products": len(dev_df),
            "rule_only": rule_summary,
            "ml_classifier": ml_summary,
            "verdict": {
                "go_live": go_live,
                "trace_f1_improved": bool(trace_wins),
                "declared_f1_not_meaningfully_worse": bool(declared_not_much_worse),
            },
        }, f, indent=2)

    print()
    print(f"Model saved to: {OUTPUT_DIR / 'model.joblib'}")
    print(f"Results saved to: {OUTPUT_DIR}")

    return go_live


if __name__ == "__main__":
    main()
