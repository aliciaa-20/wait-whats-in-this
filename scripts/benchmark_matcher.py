import json
import re
from pathlib import Path

import pandas as pd
from sklearn.metrics import precision_recall_fscore_support

from scripts.allergen_matcher import (
    load_dictionary,
    analyze_product,
)


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = BASE_DIR / "data" / "cleaned_products.csv"
OUTPUT_DIR = BASE_DIR / "data" / "benchmark"

RESULTS_FILE = OUTPUT_DIR / "matcher_results.csv"
SUMMARY_FILE = OUTPUT_DIR / "matcher_summary.json"


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
    """Convert Open Food Facts tag field into a set of canonical allergens."""

    if pd.isna(value):
        return set()

    text = str(value).strip()

    if not text:
        return set()

    # Handle common list representations.
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
        set(
            allergen
            for row in records
            for allergen in row[true_key] | row[pred_key]
        )
    )

    if not labels:
        return {
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "support": 0,
        }

    y_true = []
    y_pred = []

    for row in records:
        y_true.append(
            [int(label in row[true_key]) for label in labels]
        )

        y_pred.append(
            [int(label in row[pred_key]) for label in labels]
        )

    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true,
        y_pred,
        average="micro",
        zero_division=0,
    )

    support = sum(
        len(row[true_key])
        for row in records
    )

    return {
        "precision": round(float(precision), 4),
        "recall": round(float(recall), 4),
        "f1": round(float(f1), 4),
        "support": int(support),
    }


def main():

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not DATA_FILE.exists():
        raise FileNotFoundError(
            f"Dataset not found: {DATA_FILE}"
        )

    df = pd.read_csv(DATA_FILE)

    dictionary = load_dictionary()

    records = []

    for _, row in df.iterrows():

        ingredients = row.get(
            "ingredients_text",
            ""
        )

        if pd.isna(ingredients):
            ingredients = ""

        ingredients = str(ingredients).strip()

        if not ingredients:
            continue

        true_allergens = parse_tags(
            row.get("allergens_tags", "")
        )

        true_traces = parse_tags(
            row.get("traces_tags", "")
        )

        try:
            analysis = analyze_product(
                row,
                dictionary
            )
        except Exception as e:
            print(
                f"Skipping {row.get('code', 'unknown')}: {e}"
            )
            continue

        predicted_allergens = set(
            analysis.get("declared_detected", set())
        )

        predicted_traces = set(
            analysis.get("trace_detected", set())
        )

        records.append(
            {
                "code": row.get("code", ""),
                "product_name": row.get(
                    "product_name",
                    ""
                ),
                "ingredients_text": ingredients,
                "reference_allergens": true_allergens,
                "predicted_allergens": predicted_allergens,
                "reference_traces": true_traces,
                "predicted_traces": predicted_traces,
            }
        )

    print()
    print("=" * 60)
    print("TEXT-ONLY ALLERGEN MATCHER BENCHMARK")
    print("=" * 60)
    print(f"Products evaluated: {len(records)}")

    allergen_metrics = multilabel_metrics(
        records,
        "reference_allergens",
        "predicted_allergens",
    )

    trace_metrics = multilabel_metrics(
        records,
        "reference_traces",
        "predicted_traces",
    )

    exact_allergen_matches = sum(
        row["reference_allergens"]
        == row["predicted_allergens"]
        for row in records
    )

    exact_trace_matches = sum(
        row["reference_traces"]
        == row["predicted_traces"]
        for row in records
    )

    exact_allergen_rate = (
        exact_allergen_matches / len(records)
        if records else 0
    )

    exact_trace_rate = (
        exact_trace_matches / len(records)
        if records else 0
    )

    # Per-allergen statistics.
    all_labels = sorted(
        set(
            allergen
            for row in records
            for allergen in (
                row["reference_allergens"]
                | row["predicted_allergens"]
            )
        )
    )

    per_allergen = {}

    for label in all_labels:

        tp = sum(
            label in row["reference_allergens"]
            and label in row["predicted_allergens"]
            for row in records
        )

        fp = sum(
            label not in row["reference_allergens"]
            and label in row["predicted_allergens"]
            for row in records
        )

        fn = sum(
            label in row["reference_allergens"]
            and label not in row["predicted_allergens"]
            for row in records
        )

        precision = (
            tp / (tp + fp)
            if tp + fp
            else 0
        )

        recall = (
            tp / (tp + fn)
            if tp + fn
            else 0
        )

        f1 = (
            2 * precision * recall
            / (precision + recall)
            if precision + recall
            else 0
        )

        per_allergen[label] = {
            "support": int(tp + fn),
            "true_positive": int(tp),
            "false_positive": int(fp),
            "false_negative": int(fn),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
        }

    # Save detailed results.
    output_rows = []

    for row in records:

        output_rows.append(
            {
                "code": row["code"],
                "product_name": row["product_name"],
                "reference_allergens": "|".join(
                    sorted(row["reference_allergens"])
                ),
                "predicted_allergens": "|".join(
                    sorted(row["predicted_allergens"])
                ),
                "reference_traces": "|".join(
                    sorted(row["reference_traces"])
                ),
                "predicted_traces": "|".join(
                    sorted(row["predicted_traces"])
                ),
                "exact_allergen_match": (
                    row["reference_allergens"]
                    == row["predicted_allergens"]
                ),
                "exact_trace_match": (
                    row["reference_traces"]
                    == row["predicted_traces"]
                ),
            }
        )

    pd.DataFrame(output_rows).to_csv(
        RESULTS_FILE,
        index=False,
    )

    summary = {
        "benchmark": "Text-only allergen matcher",
        "dataset": str(DATA_FILE),
        "products_evaluated": len(records),

        "allergen": {
            **allergen_metrics,
            "exact_set_agreement": round(
                exact_allergen_rate,
                4
            ),
        },

        "trace": {
            **trace_metrics,
            "exact_set_agreement": round(
                exact_trace_rate,
                4
            ),
        },

        "per_allergen": per_allergen,

        "note": (
            "Open Food Facts allergen and trace tags are used "
            "as reference metadata and should not be treated "
            "as absolute ground truth. A manually verified "
            "held-out test set is required for final paper claims."
        ),
    }

    with open(
        SUMMARY_FILE,
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            summary,
            f,
            indent=2,
            ensure_ascii=False,
        )

    print()
    print("ALLERGEN DETECTION")
    print(
        f"Precision : {allergen_metrics['precision']:.4f}"
    )
    print(
        f"Recall    : {allergen_metrics['recall']:.4f}"
    )
    print(
        f"F1        : {allergen_metrics['f1']:.4f}"
    )
    print(
        f"Exact     : {exact_allergen_rate:.4f}"
    )

    print()
    print("TRACE DETECTION")
    print(
        f"Precision : {trace_metrics['precision']:.4f}"
    )
    print(
        f"Recall    : {trace_metrics['recall']:.4f}"
    )
    print(
        f"F1        : {trace_metrics['f1']:.4f}"
    )
    print(
        f"Exact     : {exact_trace_rate:.4f}"
    )

    print()
    print("PER-ALLERGEN RESULTS")
    print("-" * 60)

    for label, metrics in per_allergen.items():

        print(
            f"{label:15s} "
            f"P={metrics['precision']:.3f} "
            f"R={metrics['recall']:.3f} "
            f"F1={metrics['f1']:.3f} "
            f"Support={metrics['support']}"
        )

    print()
    print(f"Results saved to: {RESULTS_FILE}")
    print(f"Summary saved to: {SUMMARY_FILE}")


if __name__ == "__main__":
    main()