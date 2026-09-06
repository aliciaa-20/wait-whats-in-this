"""
Baseline comparison for allergen detection.

Compares:
1. Exact keyword matching
2. Normalized keyword matching
3. Proposed ontology/context-aware matcher

Reference:
Open Food Facts allergen metadata.

Important:
Open Food Facts metadata is treated as reference metadata,
not absolute ground truth.
"""

import json
import re
from pathlib import Path

import pandas as pd
from sklearn.metrics import precision_recall_fscore_support

from scripts.allergen_matcher import (
    load_dictionary,
    normalize_text,
    analyze_product,
)


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = BASE_DIR / "data" / "cleaned_products.csv"
OUTPUT_DIR = BASE_DIR / "data" / "benchmark"

RESULTS_FILE = OUTPUT_DIR / "baseline_comparison.csv"
SUMMARY_FILE = OUTPUT_DIR / "baseline_summary.json"


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


def phrase_in_text(phrase, text):
    """
    Boundary-aware phrase matching.
    """
    escaped = re.escape(phrase)

    pattern = rf"(?<!\w){escaped}(?!\w)"

    return re.search(
        pattern,
        text,
        flags=re.IGNORECASE,
    ) is not None


def exact_keyword_match(text, dictionary):
    """
    Baseline 1:
    Match dictionary terms directly against the raw ingredient text.

    No normalization.
    No contextual exclusions.
    No negation.
    No trace separation.
    """

    if not text:
        return set()

    detected = set()

    for allergen, terms in dictionary.items():

        for term in terms:

            if phrase_in_text(
                str(term),
                str(text),
            ):
                detected.add(allergen)
                break

    return detected


def normalized_keyword_match(text, dictionary):
    """
    Baseline 2:
    Normalize both the input text and dictionary terms,
    then perform keyword matching.

    No contextual exclusions.
    No negation.
    No trace separation.
    """

    if not text:
        return set()

    normalized = normalize_text(text)

    detected = set()

    for allergen, terms in dictionary.items():

        for term in terms:

            normalized_term = normalize_text(term)

            if not normalized_term:
                continue

            if phrase_in_text(
                normalized_term,
                normalized,
            ):
                detected.add(allergen)
                break

    return detected


def calculate_metrics(records, prediction_key):

    labels = sorted(
        set(
            allergen
            for row in records
            for allergen in (
                row["reference"]
                | row[prediction_key]
            )
        )
    )

    if not labels:
        return {
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
        }

    y_true = []
    y_pred = []

    for row in records:

        y_true.append(
            [
                int(label in row["reference"])
                for label in labels
            ]
        )

        y_pred.append(
            [
                int(label in row[prediction_key])
                for label in labels
            ]
        )

    precision, recall, f1, _ = (
        precision_recall_fscore_support(
            y_true,
            y_pred,
            average="micro",
            zero_division=0,
        )
    )

    return {
        "precision": round(float(precision), 4),
        "recall": round(float(recall), 4),
        "f1": round(float(f1), 4),
    }


def exact_agreement(records, prediction_key):

    if not records:
        return 0.0

    matches = sum(
        row["reference"]
        == row[prediction_key]
        for row in records
    )

    return round(
        matches / len(records),
        4,
    )


def per_allergen(records, prediction_key):

    labels = sorted(
        set(
            allergen
            for row in records
            for allergen in (
                row["reference"]
                | row[prediction_key]
            )
        )
    )

    output = {}

    for label in labels:

        tp = sum(
            label in row["reference"]
            and label in row[prediction_key]
            for row in records
        )

        fp = sum(
            label not in row["reference"]
            and label in row[prediction_key]
            for row in records
        )

        fn = sum(
            label in row["reference"]
            and label not in row[prediction_key]
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

        output[label] = {
            "support": int(tp + fn),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
        }

    return output


def main():

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

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
            "",
        )

        if pd.isna(ingredients):
            ingredients = ""

        ingredients = str(
            ingredients
        ).strip()

        if not ingredients:
            continue

        reference = parse_tags(
            row.get(
                "allergens_tags",
                "",
            )
        )

        exact_prediction = (
            exact_keyword_match(
                ingredients,
                dictionary,
            )
        )

        normalized_prediction = (
            normalized_keyword_match(
                ingredients,
                dictionary,
            )
        )

        try:
            proposed = analyze_product(
                row,
                dictionary,
            )

            proposed_prediction = set(
                proposed.get(
                    "declared_detected",
                    set(),
                )
            )

        except Exception as e:

            print(
                f"Skipping "
                f"{row.get('code', 'unknown')}: "
                f"{e}"
            )

            continue

        records.append(
            {
                "code": row.get(
                    "code",
                    "",
                ),
                "product_name": row.get(
                    "product_name",
                    "",
                ),
                "reference": reference,
                "exact_keyword": exact_prediction,
                "normalized_keyword": normalized_prediction,
                "proposed": proposed_prediction,
            }
        )

    print()
    print("=" * 70)
    print("ALLERGEN MATCHING BASELINE COMPARISON")
    print("=" * 70)

    print(
        f"Products evaluated: {len(records)}"
    )

    methods = {
        "Exact keyword": "exact_keyword",
        "Normalized keyword": "normalized_keyword",
        "Proposed matcher": "proposed",
    }

    comparison = []
    detailed = {}

    for method_name, prediction_key in methods.items():

        metrics = calculate_metrics(
            records,
            prediction_key,
        )

        exact = exact_agreement(
            records,
            prediction_key,
        )

        per_class = per_allergen(
            records,
            prediction_key,
        )

        comparison.append(
            {
                "method": method_name,
                "precision": metrics["precision"],
                "recall": metrics["recall"],
                "f1": metrics["f1"],
                "exact_set_agreement": exact,
            }
        )

        detailed[method_name] = {
            **metrics,
            "exact_set_agreement": exact,
            "per_allergen": per_class,
        }

    comparison_df = pd.DataFrame(
        comparison
    )

    comparison_df.to_csv(
        RESULTS_FILE,
        index=False,
    )

    summary = {
        "benchmark": (
            "Allergen matching baseline comparison"
        ),
        "dataset": str(DATA_FILE),
        "products_evaluated": len(records),
        "methods": detailed,
        "note": (
            "Open Food Facts allergen tags are used "
            "as reference metadata and should not be "
            "treated as absolute ground truth. "
            "Final paper evaluation should use a "
            "manually verified held-out test set."
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
    print(
        f"{'METHOD':<25}"
        f"{'PRECISION':>12}"
        f"{'RECALL':>12}"
        f"{'F1':>12}"
        f"{'EXACT':>12}"
    )

    print("-" * 70)

    for row in comparison:

        print(
            f"{row['method']:<25}"
            f"{row['precision']:>12.4f}"
            f"{row['recall']:>12.4f}"
            f"{row['f1']:>12.4f}"
            f"{row['exact_set_agreement']:>12.4f}"
        )

    print()
    print(
        f"Results saved to: {RESULTS_FILE}"
    )

    print(
        f"Summary saved to: {SUMMARY_FILE}"
    )


if __name__ == "__main__":
    main()