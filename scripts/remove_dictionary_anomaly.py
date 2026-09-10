"""
Post-freeze dictionary integrity cleanup: removes the single confirmed
anomalous term 'mantelrouge' (tree_nut) found during the full-dictionary
audit in Phase B.

This is NOT a new ML method or a synonym-expansion decision - it is the
removal of a term that does not correspond to any recognizable word in
any of the project's 9 supported languages, has zero occurrences
anywhere in the 1,612-product dataset, and was the sole cause of a
false-positive embedding-attractor pattern discovered during the Phase 3
synonym review. Confirmed as the only such anomaly via a complete sweep
of all 268 dictionary terms (not just short ones), cross-checked against
zero-occurrence + manual language verification.

Scope, per explicit instruction:
- Backs up data/allergen_dictionary.json first (reversible).
- Removes ONLY 'mantelrouge' from tree_nut. Nothing else changed.
- Re-runs the same 963-product leak-free benchmark used for the Phase 3
  synonym audit, before and after.
- Investigates which specific predictions changed, and whether any of
  them are resolved false positives.
- Does not touch the research-v1.0-experimental frozen results - this
  is a separate, post-freeze, dated change.

Usage:
    ./venv/bin/python -m scripts.remove_dictionary_anomaly
"""

from __future__ import annotations

import json
import re
import shutil
from datetime import date
from pathlib import Path

import pandas as pd
from sklearn.metrics import precision_recall_fscore_support

from scripts.allergen_matcher import (
    ALLERGENS,
    load_dictionary,
    normalize_text,
    split_declared_and_trace_text,
    detect_allergen_matches,
)


BASE_DIR = Path(__file__).resolve().parent.parent
DICTIONARY_FILE = BASE_DIR / "data" / "allergen_dictionary.json"
DATASET_FILE = BASE_DIR / "data" / "cleaned_products.csv"
HELDOUT_FILE = BASE_DIR / "data" / "research" / "ground_truth.csv"

OUTPUT_DIR = BASE_DIR / "data" / "research" / "ml" / "dictionary_cleanup_v1"
BACKUP_FILE = OUTPUT_DIR / "allergen_dictionary.pre_mantelrouge_removal.json"

TERM_TO_REMOVE = "mantelrouge"
ALLERGEN_OF_TERM = "tree_nut"


TAG_TO_ALLERGEN = {
    "en:milk": "milk", "en:eggs": "egg", "en:peanuts": "peanut",
    "en:nuts": "tree_nut", "en:soybeans": "soy", "en:gluten": "wheat_gluten",
    "en:wheat": "wheat_gluten", "en:fish": "fish",
    "en:crustaceans": "shellfish", "en:molluscs": "shellfish",
    "en:sesame-seeds": "sesame",
}


def parse_tags(value):
    if pd.isna(value):
        return set()
    text = str(value).strip().strip("[]")
    if not text:
        return set()
    result = set()
    for part in re.split(r"[,|;]", text):
        tag = part.strip().strip("'\"").lower()
        if tag in TAG_TO_ALLERGEN:
            result.add(TAG_TO_ALLERGEN[tag])
    return result


def load_leak_free_dev_set() -> pd.DataFrame:
    df = pd.read_csv(DATASET_FILE, dtype={"code": str})
    heldout = pd.read_csv(HELDOUT_FILE, dtype={"code": str})
    heldout_codes = set(heldout["code"])
    df["ingredients_text"] = df["ingredients_text"].fillna("").astype(str)
    df = df[df["ingredients_text"].str.strip() != ""].copy()
    df = df[~df["code"].isin(heldout_codes)].copy()
    return df.reset_index(drop=True)


def make_dict(raw):
    result = {a: set() for a in ALLERGENS}
    for a, vals in raw.items():
        for v in vals:
            n = normalize_text(v)
            if n:
                result[a].add(n)
    return result


def multilabel_metrics(records, true_key, pred_key):
    labels = sorted(set(a for r in records for a in r[true_key] | r[pred_key]))
    if not labels:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    y_true = [[int(l in r[true_key]) for l in labels] for r in records]
    y_pred = [[int(l in r[pred_key]) for l in labels] for r in records]
    p, r, f1, _ = precision_recall_fscore_support(y_true, y_pred, average="micro", zero_division=0)
    return {"precision": round(float(p), 4), "recall": round(float(r), 4), "f1": round(float(f1), 4)}


def exact_match_rate(records, true_key, pred_key):
    if not records:
        return 0.0
    return round(sum(r[true_key] == r[pred_key] for r in records) / len(records), 4)


def run_benchmark(dev_df, dictionary):
    declared_records = []
    trace_records = []
    per_product = {}
    for _, row in dev_df.iterrows():
        text = row["ingredients_text"]
        true_declared = parse_tags(row.get("allergens_tags", ""))
        true_trace = parse_tags(row.get("traces_tags", ""))
        declared_text, trace_text = split_declared_and_trace_text(text)
        pred_declared = detect_allergen_matches(declared_text, dictionary)["detected"]
        pred_trace = detect_allergen_matches(trace_text, dictionary)["detected"]
        declared_records.append({"reference_allergens": true_declared, "predicted_allergens": pred_declared})
        trace_records.append({"reference_allergens": true_trace, "predicted_allergens": pred_trace})
        per_product[row["code"]] = {
            "declared_pred": pred_declared,
            "trace_pred": pred_trace,
            "declared_true": true_declared,
            "trace_true": true_trace,
        }
    metrics = {
        "declared": {
            **multilabel_metrics(declared_records, "reference_allergens", "predicted_allergens"),
            "exact_match": exact_match_rate(declared_records, "reference_allergens", "predicted_allergens"),
        },
        "trace": {
            **multilabel_metrics(trace_records, "reference_allergens", "predicted_allergens"),
            "exact_match": exact_match_rate(trace_records, "reference_allergens", "predicted_allergens"),
        },
    }
    return metrics, per_product


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # --- 1. Backup ---
    if not BACKUP_FILE.exists():
        shutil.copy2(DICTIONARY_FILE, BACKUP_FILE)
        print(f"Backup created: {BACKUP_FILE}")
    else:
        print(f"Backup already exists (not overwritten): {BACKUP_FILE}")

    dev_df = load_leak_free_dev_set()
    print(f"Dev set (leak-free): {len(dev_df)} products")

    # --- Before ---
    with DICTIONARY_FILE.open("r", encoding="utf-8") as f:
        raw_before = json.load(f)

    assert TERM_TO_REMOVE in raw_before[ALLERGEN_OF_TERM], (
        f"'{TERM_TO_REMOVE}' not found in {ALLERGEN_OF_TERM} - nothing to remove, aborting."
    )

    dict_before = make_dict(raw_before)
    print("\nRunning benchmark BEFORE removal...")
    metrics_before, per_product_before = run_benchmark(dev_df, dict_before)
    print(json.dumps(metrics_before, indent=2))

    # --- 2/3. Remove ONLY the one term, preserving order/formatting of everything else ---
    order = ["milk", "egg", "peanut", "tree_nut", "soy", "wheat_gluten", "fish", "shellfish", "sesame"]
    raw_after = {k: list(v) for k, v in raw_before.items()}
    raw_after[ALLERGEN_OF_TERM] = [t for t in raw_after[ALLERGEN_OF_TERM] if t != TERM_TO_REMOVE]

    lines = ["{"]
    for i, key in enumerate(order):
        lines.append(f'    "{key}": [')
        terms = raw_after[key]
        for j, term in enumerate(terms):
            comma = "," if j < len(terms) - 1 else ""
            lines.append(f'        {json.dumps(term, ensure_ascii=False)}{comma}')
        closing = "]," if i < len(order) - 1 else "]"
        lines.append(f"    {closing}")
        if i < len(order) - 1:
            lines.append("")
    lines.append("}")

    with DICTIONARY_FILE.open("w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"\nRemoved '{TERM_TO_REMOVE}' from {ALLERGEN_OF_TERM}.")

    # --- 4. After ---
    dict_after = load_dictionary()
    print("\nRunning benchmark AFTER removal...")
    metrics_after, per_product_after = run_benchmark(dev_df, dict_after)
    print(json.dumps(metrics_after, indent=2))

    # --- 5. Compare ---
    def delta(key, sub):
        return round(metrics_after[key][sub] - metrics_before[key][sub], 4)

    deltas = {
        "declared_precision": delta("declared", "precision"),
        "declared_recall": delta("declared", "recall"),
        "declared_f1": delta("declared", "f1"),
        "declared_exact_match": delta("declared", "exact_match"),
        "trace_precision": delta("trace", "precision"),
        "trace_recall": delta("trace", "recall"),
        "trace_f1": delta("trace", "f1"),
        "trace_exact_match": delta("trace", "exact_match"),
    }

    # --- Changed predictions + false-positive resolution check ---
    changed = []
    resolved_false_positives = []
    for code in per_product_before:
        b = per_product_before[code]
        a = per_product_after[code]
        if b["declared_pred"] != a["declared_pred"] or b["trace_pred"] != a["trace_pred"]:
            changed.append(code)
            # A resolved false positive: tree_nut was predicted before
            # (declared or trace) but NOT actually true, and is gone after.
            for field_pred, field_true in [("declared_pred", "declared_true"), ("trace_pred", "trace_true")]:
                had_fp_before = "tree_nut" in b[field_pred] and "tree_nut" not in b[field_true]
                has_fp_after = "tree_nut" in a[field_pred] and "tree_nut" not in a[field_true]
                if had_fp_before and not has_fp_after:
                    resolved_false_positives.append({"code": code, "field": field_pred})

    print(f"\nProducts with any changed prediction: {len(changed)}")
    print(f"Resolved tree_nut false positives: {len(resolved_false_positives)}")
    for r in resolved_false_positives:
        print(f"  {r['code']} ({r['field']})")

    if changed and not resolved_false_positives:
        print("\nChanged products with no resolved false positive (investigate):")
        for code in changed:
            print(f"  {code}: before_declared={per_product_before[code]['declared_pred']} "
                  f"after_declared={per_product_after[code]['declared_pred']} "
                  f"before_trace={per_product_before[code]['trace_pred']} "
                  f"after_trace={per_product_after[code]['trace_pred']}")

    verdict = (
        "IMPROVED" if any(v > 0 for v in deltas.values()) and all(v >= 0 for v in deltas.values())
        else "WORSENED" if any(v < 0 for v in deltas.values())
        else "NO MEASURABLE EFFECT"
    )

    # --- 7. Record as documentation ---
    result = {
        "change_type": "dictionary_integrity_cleanup",
        "not_a_new_ml_method": True,
        "date": str(date.today()),
        "term_removed": TERM_TO_REMOVE,
        "allergen": ALLERGEN_OF_TERM,
        "reason": (
            "Confirmed as the sole anomaly in a complete audit of all 268 dictionary "
            "terms: does not correspond to any recognizable word in any of the "
            "project's 9 supported languages, has zero occurrences anywhere in the "
            "1,612-product dataset, and was the sole cause of a false-positive "
            "embedding-attractor pattern discovered during the Phase 3 synonym review "
            "(9+ unrelated candidates across multiple products falsely clustered onto "
            "it during embedding-based candidate generation)."
        ),
        "evaluation_set": "963-product leak-free dev set (same as the Phase 3 synonym audit)",
        "held_out_300_touched": False,
        "research_v1.0_experimental_untouched": True,
        "backup_file": str(BACKUP_FILE.relative_to(BASE_DIR)),
        "before": metrics_before,
        "after": metrics_after,
        "deltas": deltas,
        "products_with_changed_prediction": len(changed),
        "resolved_tree_nut_false_positives": len(resolved_false_positives),
        "resolved_false_positive_details": resolved_false_positives,
        "verdict": verdict,
    }

    with (OUTPUT_DIR / "mantelrouge_removal_result.json").open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print()
    print("=" * 70)
    print(f"VERDICT: {verdict}")
    print("=" * 70)
    for k, v in deltas.items():
        print(f"  {k}: {v:+.4f}")

    print(f"\nFull result saved to: {OUTPUT_DIR / 'mantelrouge_removal_result.json'}")


if __name__ == "__main__":
    main()
