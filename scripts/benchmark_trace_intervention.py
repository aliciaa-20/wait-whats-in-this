"""
Phase B trace-recall targeted intervention - before/after benchmark.

Same leak-free 963-product dev set and same metric methodology used for
the Phase 3 synonym audit and the mantelrouge dictionary cleanup
(scripts/remove_dictionary_anomaly.py). Read-only against the held-out
300-product set and research-v1.0-experimental - neither is touched or
tuned against here.

The "before" dictionary/matcher snapshot is the pre_intervention backup
under data/research/ml/trace_intervention_v1/; "after" is the live,
already-edited data/allergen_dictionary.json and scripts/allergen_matcher.py.
"""

from __future__ import annotations

import importlib.util
import json
from datetime import date
from pathlib import Path

import pandas as pd
from sklearn.metrics import precision_recall_fscore_support

BASE_DIR = Path(__file__).resolve().parent.parent
DATASET_FILE = BASE_DIR / "data" / "cleaned_products.csv"
HELDOUT_FILE = BASE_DIR / "data" / "research" / "ground_truth.csv"

INTERVENTION_DIR = BASE_DIR / "data" / "research" / "ml" / "trace_intervention_v1"
PRE_DICT = INTERVENTION_DIR / "allergen_dictionary.pre_intervention.json"
PRE_MATCHER = INTERVENTION_DIR / "allergen_matcher.pre_intervention.py"

LIVE_DICT = BASE_DIR / "data" / "allergen_dictionary.json"

DIAGNOSTIC_RAW = (
    BASE_DIR / "data" / "research" / "ml" / "trace_fn_diagnostic_v1" / "trace_fn_raw_records.csv"
)

TAG_TO_ALLERGEN = {
    "en:milk": "milk", "en:eggs": "egg", "en:peanuts": "peanut",
    "en:nuts": "tree_nut", "en:soybeans": "soy", "en:gluten": "wheat_gluten",
    "en:wheat": "wheat_gluten", "en:fish": "fish",
    "en:crustaceans": "shellfish", "en:molluscs": "shellfish",
    "en:sesame-seeds": "sesame",
}


def load_module(name, path, dictionary_path):
    """Import allergen_matcher.py from an arbitrary path, pointed at an
    arbitrary dictionary file, as an isolated module (so the 'before' and
    'after' matcher code+vocabulary don't collide in sys.modules)."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.DICTIONARY_FILE = dictionary_path
    return module


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


def run_benchmark(dev_df, matcher_module):
    dictionary = matcher_module.load_dictionary()
    declared_records = []
    trace_records = []
    per_product = {}
    for _, row in dev_df.iterrows():
        text = row["ingredients_text"]
        true_declared = parse_tags(row.get("allergens_tags", ""))
        true_trace = parse_tags(row.get("traces_tags", ""))
        declared_text, trace_text = matcher_module.split_declared_and_trace_text(text)
        pred_declared = matcher_module.detect_allergen_matches(declared_text, dictionary)["detected"]
        pred_trace = matcher_module.detect_allergen_matches(trace_text, dictionary)["detected"]
        declared_records.append({"reference_allergens": true_declared, "predicted_allergens": pred_declared})
        trace_records.append({"reference_allergens": true_trace, "predicted_allergens": pred_trace})
        per_product[row["code"]] = {
            "declared_pred": pred_declared, "trace_pred": pred_trace,
            "declared_true": true_declared, "trace_true": true_trace,
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
    dev_df = load_leak_free_dev_set()
    print(f"Dev set (leak-free): {len(dev_df)} products")

    before_mod = load_module("matcher_before", PRE_MATCHER, PRE_DICT)
    after_mod = load_module("matcher_after", BASE_DIR / "scripts" / "allergen_matcher.py", LIVE_DICT)

    print("\nRunning BEFORE benchmark (pre-intervention snapshot)...")
    metrics_before, per_product_before = run_benchmark(dev_df, before_mod)
    print(json.dumps(metrics_before, indent=2))

    print("\nRunning AFTER benchmark (live, post-intervention)...")
    metrics_after, per_product_after = run_benchmark(dev_df, after_mod)
    print(json.dumps(metrics_after, indent=2))

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

    changed = []
    for code in per_product_before:
        b = per_product_before[code]
        a = per_product_after[code]
        if b["declared_pred"] != a["declared_pred"] or b["trace_pred"] != a["trace_pred"]:
            changed.append({
                "code": code,
                "declared_before": sorted(b["declared_pred"]), "declared_after": sorted(a["declared_pred"]),
                "trace_before": sorted(b["trace_pred"]), "trace_after": sorted(a["trace_pred"]),
                "declared_true": sorted(b["declared_true"]), "trace_true": sorted(b["trace_true"]),
            })

    new_declared_fp = 0
    new_trace_fp = 0
    for c in changed:
        added_declared = set(c["declared_after"]) - set(c["declared_before"])
        added_trace = set(c["trace_after"]) - set(c["trace_before"])
        new_declared_fp += len(added_declared - set(c["declared_true"]))
        new_trace_fp += len(added_trace - set(c["trace_true"]))

    # --- Recovery check against the specific diagnosed FN codes/allergens ---
    diagnosed = []
    if DIAGNOSTIC_RAW.exists():
        diag_df = pd.read_csv(DIAGNOSTIC_RAW, dtype={"code": str})
        target_cats = {"trace_marker_detection_gap", "ontology_dictionary_gap"}
        diag_df = diag_df[diag_df["category"].isin(target_cats)]
        # Only codes that are in this leak-free dev set (1263-eval sourced
        # codes may include held-out codes, which this benchmark excludes).
        dev_codes = set(dev_df["code"])
        for _, r in diag_df.iterrows():
            code = r["code"]
            allergen = r["allergen"]
            if code not in dev_codes or code not in per_product_after:
                continue
            was_fn_before = allergen in per_product_before[code]["trace_true"] and \
                allergen not in per_product_before[code]["trace_pred"]
            resolved_after = allergen in per_product_after[code]["trace_pred"]
            diagnosed.append({
                "code": code, "allergen": allergen, "category": r["category"],
                "was_fn_before": bool(was_fn_before), "resolved_after": bool(resolved_after),
            })

    n_diagnosed = len(diagnosed)
    n_resolved = sum(1 for d in diagnosed if d["resolved_after"])

    result = {
        "change_type": "targeted_rule_ontology_correction",
        "not_a_new_ml_method": True,
        "date": str(date.today()),
        "evaluation_set": "963-product leak-free dev set (same as Phase 3 synonym audit and mantelrouge cleanup)",
        "held_out_300_touched_for_tuning": False,
        "research_v1.0_experimental_untouched": True,
        "changes": {
            "regex_added": r"\bkann\b[^.]{0,80}\benthalten\b (German 'kann ... enthalten' bounded-clause trace marker)",
            "dictionary_terms_added": {
                "egg": ["huevo", "huevos"],
                "peanut": ["erdnüssen"],
                "tree_nut": ["schalenfrüchten", "frutos secos"],
                "shellfish": ["crustacé", "crustáceo", "crustáceos"],
                "sesame": ["sésamo"],
            },
            "excluded_ambiguous_or_out_of_scope": {
                "noix (fr, tree_nut)": "ambiguous - collides with 'noix de coco' (coconut, not an EU-regulated tree-nut allergen)",
                "underscore-wrapped OFF terms (e.g. '_soja_', '_lait_', '_sesamo...huevo._')":
                    "term already correct in dictionary; failure is a normalize_text/phrase_in_text "
                    "word-boundary bug where '_' counts as \\w - out of scope for a dictionary/regex-only change",
            },
        },
        "before": metrics_before,
        "after": metrics_after,
        "deltas": deltas,
        "products_with_changed_prediction": len(changed),
        "new_declared_false_positives_introduced": new_declared_fp,
        "new_trace_false_positives_introduced": new_trace_fp,
        "diagnosed_false_negative_recovery": {
            "targeted_categories": ["trace_marker_detection_gap", "ontology_dictionary_gap"],
            "diagnosed_instances_in_this_dev_set": n_diagnosed,
            "resolved_after_intervention": n_resolved,
            "detail": diagnosed,
        },
    }

    out_dir = INTERVENTION_DIR
    with (out_dir / "trace_intervention_result.json").open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 70)
    print("DELTAS")
    print("=" * 70)
    for k, v in deltas.items():
        print(f"  {k}: {v:+.4f}")
    print(f"\nProducts with any changed prediction: {len(changed)}")
    print(f"New declared false positives introduced: {new_declared_fp}")
    print(f"New trace false positives introduced: {new_trace_fp}")
    print(f"\nDiagnosed FN recovery: {n_resolved}/{n_diagnosed} resolved")
    for d in diagnosed:
        print(f"  {d['code']} {d['allergen']:12s} [{d['category']}] resolved={d['resolved_after']}")

    print(f"\nFull result: {out_dir / 'trace_intervention_result.json'}")


if __name__ == "__main__":
    main()
