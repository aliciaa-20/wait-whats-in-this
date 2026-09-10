"""
Phase 8 - multi-signal match-confidence model.

Scope, per AI_ML_UPGRADE_PLAN.md: this model NEVER decides which allergens
are present - it only scores how much a user should trust a match the
deterministic matcher already produced. Trained on the combined OCR
benchmark (39 original + 44 newly expanded images = 83 images, 238
allergen match instances - see data/research/ml/ocr_expansion_v1/).

Every row is one (product, allergen, section) match the OCR-text matcher
actually produced (declared or trace); the label is whether that match
was correct against the reference allergens. Features are exactly the
signals available at prediction time - no reference-label leakage.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import brier_score_loss, roc_auc_score

BASE_DIR = Path(__file__).resolve().parent.parent
OLD_FILE = BASE_DIR / "data" / "benchmark" / "final_ocr_results.csv"
NEW_FILE = BASE_DIR / "data" / "research" / "ml" / "ocr_expansion_v1" / "expansion_ocr_results.csv"
OUTPUT_DIR = BASE_DIR / "data" / "research" / "ml" / "confidence_model_v1"


def sset(v):
    if pd.isna(v) or not str(v).strip():
        return set()
    return set(str(v).split("|"))


def build_instances(df, source):
    rows = []
    for _, r in df.iterrows():
        ocr_conf = r.get("ocr_confidence", 0.0)
        if pd.isna(ocr_conf):
            ocr_conf = 0.0
        extraction_found = bool(r.get("extraction_found", False))
        language = str(r.get("target_language", "fr") or "fr").lower()
        ocr_text = str(r.get("ocr_text", r.get("manual_transcription", "")) or "")
        text_len = len(ocr_text)

        for section, pred_col, ref_col in [
            ("declared", "ocr_declared_allergens", "reference_declared_allergens"),
            ("trace", "ocr_trace_allergens", "reference_trace_allergens"),
        ]:
            predicted = sset(r.get(pred_col))
            reference = sset(r.get(ref_col))
            for allergen in predicted:
                correct = int(allergen in reference)
                rows.append({
                    "source": source,
                    "code": r["code"],
                    "allergen": allergen,
                    "section": section,
                    "is_trace": int(section == "trace"),
                    "ocr_confidence": float(ocr_conf),
                    "extraction_found": int(extraction_found),
                    "language": language,
                    "text_length": text_len,
                    "correct": correct,
                })
    return rows


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    old = pd.read_csv(OLD_FILE, dtype={"code": str})
    new = pd.read_csv(NEW_FILE, dtype={"code": str})

    instances = build_instances(old, "original_39") + build_instances(new, "expansion_44")
    df = pd.DataFrame(instances)

    print(f"Total match instances: {len(df)}")
    print(f"Correct: {df['correct'].sum()}, Incorrect: {(1 - df['correct']).sum()}")
    print(df.groupby("source")["correct"].agg(["count", "mean"]))

    if len(df) < 40 or df["correct"].nunique() < 2:
        print("Not enough instances / class diversity to train - stopping honestly.")
        return

    # One-hot language, keep it simple.
    lang_dummies = pd.get_dummies(df["language"], prefix="lang")
    X = pd.concat([
        df[["is_trace", "ocr_confidence", "extraction_found", "text_length"]],
        lang_dummies,
    ], axis=1)
    y = df["correct"]

    X_train, X_test, y_train, y_test, df_train, df_test = train_test_split(
        X, y, df, test_size=0.3, random_state=42, stratify=y
    )

    model = LogisticRegression(max_iter=1000, class_weight="balanced")
    model.fit(X_train, y_train)

    probs_test = model.predict_proba(X_test)[:, 1]

    brier = brier_score_loss(y_test, probs_test)
    try:
        auc = roc_auc_score(y_test, probs_test)
    except ValueError:
        auc = None

    # Calibration check: bucket predicted probability, compare to actual
    # accuracy in that bucket. With ~70 test instances this is coarse (3
    # buckets, not 10) - reported honestly as such, not oversold.
    bucket_edges = [0.0, 0.4, 0.7, 1.01]
    bucket_labels = ["low (0-0.4)", "medium (0.4-0.7)", "high (0.7-1.0)"]
    df_test = df_test.copy()
    df_test["predicted_prob"] = probs_test
    df_test["bucket"] = pd.cut(
        df_test["predicted_prob"], bins=bucket_edges, labels=bucket_labels, right=False
    )

    calibration = []
    for bucket in bucket_labels:
        sub = df_test[df_test["bucket"] == bucket]
        if len(sub) == 0:
            continue
        calibration.append({
            "bucket": bucket,
            "n": int(len(sub)),
            "mean_predicted_prob": round(float(sub["predicted_prob"].mean()), 3),
            "actual_accuracy": round(float(sub["correct"].mean()), 3),
        })

    coef_report = dict(zip(X.columns.tolist(), [round(float(c), 4) for c in model.coef_[0]]))

    result = {
        "model_type": "logistic_regression_confidence_scorer",
        "not_an_allergen_detector": True,
        "scope": "scores trust in matches the deterministic matcher already made; never adds/removes a detection",
        "training_data": {
            "total_instances": len(df),
            "original_39_image_instances": int((df["source"] == "original_39").sum()),
            "expansion_44_image_instances": int((df["source"] == "expansion_44").sum()),
            "train_n": len(X_train),
            "test_n": len(X_test),
        },
        "caveat": (
            "238 instances total, ~70 in the held-out test split, is still a "
            "modest sample for calibration - the 3-bucket calibration table "
            "below is coarse evidence, not a fine-grained reliability curve. "
            "Treat this as a first honest attempt, not a final calibrated "
            "probability model."
        ),
        "test_metrics": {
            "brier_score": round(float(brier), 4),
            "roc_auc": round(float(auc), 4) if auc is not None else None,
            "baseline_accuracy": round(float(y_test.mean()), 4),
        },
        "calibration_by_bucket": calibration,
        "feature_coefficients": coef_report,
    }

    with (OUTPUT_DIR / "confidence_model_result.json").open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    df.to_csv(OUTPUT_DIR / "confidence_training_instances.csv", index=False)

    import joblib
    joblib.dump(model, OUTPUT_DIR / "model.joblib")

    print("\n=== TEST METRICS ===")
    print(json.dumps(result["test_metrics"], indent=2))
    print("\n=== CALIBRATION (coarse, 3-bucket) ===")
    for row in calibration:
        print(f"  {row['bucket']:20s} n={row['n']:3d}  "
              f"predicted={row['mean_predicted_prob']:.3f}  actual={row['actual_accuracy']:.3f}")
    print(f"\nSaved: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
