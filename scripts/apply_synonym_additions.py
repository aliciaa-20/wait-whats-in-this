"""
Applies the 9 explicitly user-approved synonym additions from Phase 3
(scripts/ml_synonym_discovery.py review) to data/allergen_dictionary.json,
then verifies no regression on the 963-product leak-free dev set.

Scope, per explicit instruction:
- Adds ONLY the 9 approved terms below. Nothing else.
- Does not remove, rename, or modify any existing entry.
- Does not touch the flagged existing entries (mantelrouge, sei, crabe) -
  those are a separate audit, untouched here.
- Does not act on the Arabic-comma splitting bug or barley-milk spelling
  follow-ups.
- Backs up the pre-change dictionary first (reversible).
- Re-runs the rule-only benchmark on the same 963-product leak-free set
  used throughout this ML extension, before and after, and compares.
- Does not change allergen_matcher.py or any matching logic - only the
  data file.

Usage:
    ./venv/bin/python -m scripts.apply_synonym_additions
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd

from scripts.allergen_matcher import (
    load_dictionary,
    split_declared_and_trace_text,
    detect_allergen_matches,
)


BASE_DIR = Path(__file__).resolve().parent.parent
DICTIONARY_FILE = BASE_DIR / "data" / "allergen_dictionary.json"
DATASET_FILE = BASE_DIR / "data" / "cleaned_products.csv"
HELDOUT_FILE = BASE_DIR / "data" / "research" / "ground_truth.csv"

OUTPUT_DIR = BASE_DIR / "data" / "research" / "ml" / "synonym_proposals_v1"
BACKUP_DIR = OUTPUT_DIR / "backup"
BACKUP_FILE = BACKUP_DIR / "allergen_dictionary.pre_synonym_v1.json"

# Exactly the 9 terms explicitly approved by the user, 2026-09-09.
APPROVED_ADDITIONS = {
    "milk": [
        "بروتينات الحليب",
        "lactossoro em pó",
        "مركزات بروتينات الحليب",
        "حليب كامل الدسم",
    ],
    "tree_nut": [
        "fruit à coques",
        "frutos de cáscara",
        "fruits coque",  # cleaned of the "_..._" markup wrapper present in the raw candidate
    ],
    "wheat_gluten": [
        "пшенично брашно",
        "farine de froment",  # lowercased for consistency with existing entries
    ],
}


TAG_TO_ALLERGEN = {
    "en:milk": "milk", "en:eggs": "egg", "en:peanuts": "peanut",
    "en:nuts": "tree_nut", "en:soybeans": "soy", "en:gluten": "wheat_gluten",
    "en:wheat": "wheat_gluten", "en:fish": "fish",
    "en:crustaceans": "shellfish", "en:molluscs": "shellfish",
    "en:sesame-seeds": "sesame",
}


def parse_tags(value):
    import re
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


def multilabel_metrics(records, true_key, pred_key):
    from sklearn.metrics import precision_recall_fscore_support
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


def run_rule_only_benchmark(dev_df, dictionary):
    declared_records = []
    trace_records = []
    for _, row in dev_df.iterrows():
        text = row["ingredients_text"]
        true_declared = parse_tags(row.get("allergens_tags", ""))
        true_trace = parse_tags(row.get("traces_tags", ""))
        declared_text, trace_text = split_declared_and_trace_text(text)
        declared_records.append({
            "reference_allergens": true_declared,
            "predicted_allergens": detect_allergen_matches(declared_text, dictionary)["detected"],
        })
        trace_records.append({
            "reference_allergens": true_trace,
            "predicted_allergens": detect_allergen_matches(trace_text, dictionary)["detected"],
        })
    return {
        "declared": {
            **multilabel_metrics(declared_records, "reference_allergens", "predicted_allergens"),
            "exact_match": exact_match_rate(declared_records, "reference_allergens", "predicted_allergens"),
        },
        "trace": {
            **multilabel_metrics(trace_records, "reference_allergens", "predicted_allergens"),
            "exact_match": exact_match_rate(trace_records, "reference_allergens", "predicted_allergens"),
        },
    }


def main():
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    # --- 1. Backup (idempotent - don't overwrite an existing backup) ---
    if not BACKUP_FILE.exists():
        shutil.copy2(DICTIONARY_FILE, BACKUP_FILE)
        print(f"Backup created: {BACKUP_FILE}")
    else:
        print(f"Backup already exists (not overwritten): {BACKUP_FILE}")

    # --- 2. Baseline benchmark (BEFORE any change) ---
    dev_df = load_leak_free_dev_set()
    print(f"Dev set (leak-free): {len(dev_df)} products")

    dictionary_before = load_dictionary()
    print("\nRunning rule-only benchmark BEFORE dictionary change...")
    before_metrics = run_rule_only_benchmark(dev_df, dictionary_before)
    print(json.dumps(before_metrics, indent=2))

    # --- 3. Apply additions ---
    with DICTIONARY_FILE.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    diff = {}
    for allergen, terms in APPROVED_ADDITIONS.items():
        if allergen not in raw:
            raise ValueError(f"Unexpected allergen key not in dictionary: {allergen}")
        added = []
        for term in terms:
            if term in raw[allergen]:
                print(f"WARNING: '{term}' already present in {allergen} - skipping duplicate insert")
                continue
            raw[allergen].append(term)
            added.append(term)
        diff[allergen] = added

    with DICTIONARY_FILE.open("w", encoding="utf-8") as f:
        json.dump(raw, f, indent=4, ensure_ascii=False)
        f.write("\n")

    total_added = sum(len(v) for v in diff.values())
    print(f"\nApplied {total_added} additions to {DICTIONARY_FILE}:")
    for allergen, terms in diff.items():
        for term in terms:
            print(f"  + [{allergen}] {term}")

    # --- 4. Re-run benchmark AFTER the change ---
    dictionary_after = load_dictionary()  # re-read from disk, picks up the edit
    print("\nRunning rule-only benchmark AFTER dictionary change...")
    after_metrics = run_rule_only_benchmark(dev_df, dictionary_after)
    print(json.dumps(after_metrics, indent=2))

    # --- 5. Compare, check for regression ---
    declared_delta = round(after_metrics["declared"]["f1"] - before_metrics["declared"]["f1"], 4)
    trace_delta = round(after_metrics["trace"]["f1"] - before_metrics["trace"]["f1"], 4)
    declared_precision_delta = round(after_metrics["declared"]["precision"] - before_metrics["declared"]["precision"], 4)
    trace_precision_delta = round(after_metrics["trace"]["precision"] - before_metrics["trace"]["precision"], 4)

    regression = declared_delta < 0 or trace_delta < 0 or declared_precision_delta < 0 or trace_precision_delta < 0

    print()
    print("=" * 70)
    print(f"REGRESSION CHECK: {'REGRESSION DETECTED' if regression else 'NO REGRESSION'}")
    print("=" * 70)
    print(f"Declared F1: {before_metrics['declared']['f1']:.4f} -> {after_metrics['declared']['f1']:.4f} (Δ{declared_delta:+.4f})")
    print(f"Declared P:  {before_metrics['declared']['precision']:.4f} -> {after_metrics['declared']['precision']:.4f} (Δ{declared_precision_delta:+.4f})")
    print(f"Trace F1:    {before_metrics['trace']['f1']:.4f} -> {after_metrics['trace']['f1']:.4f} (Δ{trace_delta:+.4f})")
    print(f"Trace P:     {before_metrics['trace']['precision']:.4f} -> {after_metrics['trace']['precision']:.4f} (Δ{trace_precision_delta:+.4f})")

    # --- 6. Save everything ---
    result = {
        "applied_at": "2026-09-09",
        "evaluation_set": "963-product leak-free dev set (same as ml_trace_classifier.py / ml_embedding_candidates.py)",
        "held_out_300_touched": False,
        "backup_file": str(BACKUP_FILE.relative_to(BASE_DIR)),
        "dictionary_diff": diff,
        "total_terms_added": total_added,
        "unchanged_flagged_entries": ["mantelrouge (tree_nut)", "sei (fish)", "crabe (shellfish)"],
        "before": before_metrics,
        "after": after_metrics,
        "deltas": {
            "declared_f1": declared_delta,
            "declared_precision": declared_precision_delta,
            "trace_f1": trace_delta,
            "trace_precision": trace_precision_delta,
        },
        "regression_detected": regression,
    }

    with (OUTPUT_DIR / "dictionary_application_result.json").open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"\nFull result saved to: {OUTPUT_DIR / 'dictionary_application_result.json'}")

    return not regression


if __name__ == "__main__":
    main()
