"""
Ablation study for the allergen matching engine.

Configurations:
1. Exact keyword
2. Normalized keyword
3. Normalized keyword + negation
4. Normalized keyword + contextual validation
5. Full proposed matcher

Reference:
Open Food Facts allergen metadata.

Important:
Open Food Facts metadata is reference metadata, not absolute
ground truth. Final paper evaluation should use a manually
verified held-out test set.
"""

import json
import re
from pathlib import Path

import pandas as pd
from sklearn.metrics import precision_recall_fscore_support

from scripts.allergen_matcher import (
    ALLERGENS,
    load_dictionary,
    normalize_text,
    phrase_in_text,
    is_negated,
    analyze_product,
    _is_valid_match,
)


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = BASE_DIR / "data" / "cleaned_products.csv"
OUTPUT_DIR = BASE_DIR / "data" / "benchmark"

RESULTS_FILE = OUTPUT_DIR / "ablation_comparison.csv"
SUMMARY_FILE = OUTPUT_DIR / "ablation_summary.json"


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
    """Convert Open Food Facts allergen tags to canonical labels."""

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


def exact_keyword_match(text, dictionary):
    """
    Baseline 1: genuinely raw keyword matching.

    No normalization is applied to either the dictionary
    terms or the ingredient text.
    """

    if not text:
        return set()

    detected = set()

    for allergen in ALLERGENS:

        for synonym in dictionary.get(
            allergen,
            set(),
        ):

            synonym = str(synonym).strip()

            if not synonym:
                continue

            # Raw boundary-aware regex.
            pattern = (
                r"(?<!\w)"
                + re.escape(synonym)
                + r"(?!\w)"
            )

            if re.search(
                pattern,
                str(text),
                flags=re.IGNORECASE | re.UNICODE,
            ):
                detected.add(allergen)
                break

    return detected


def raw_dictionary(path=None):
    """
    Load dictionary without normalization.

    Used only for the exact keyword baseline.
    """

    dictionary_path = (
        Path(path)
        if path
        else BASE_DIR
        / "data"
        / "allergen_dictionary.json"
    )

    with open(
        dictionary_path,
        "r",
        encoding="utf-8",
    ) as file:

        data = json.load(file)

    result = {
        allergen: set()
        for allergen in ALLERGENS
    }

    for allergen, values in data.items():

        if (
            allergen not in result
            or not isinstance(values, list)
        ):
            continue

        for value in values:

            value = str(value).strip()

            if value:
                result[allergen].add(value)

    return result


def normalized_keyword_match(text, dictionary):
    """Baseline 2: normalized keyword matching."""

    if not text:
        return set()

    normalized = normalize_text(text)

    detected = set()

    for allergen in ALLERGENS:

        for synonym in dictionary.get(
            allergen,
            set(),
        ):

            if phrase_in_text(
                synonym,
                normalized,
            ):
                detected.add(allergen)
                break

    return detected


def normalized_with_negation(text, dictionary):
    """
    Ablation 3:
    Normalization + negation handling.
    """

    if not text:
        return set()

    normalized = normalize_text(text)

    detected = set()

    for allergen in ALLERGENS:

        if is_negated(
            allergen,
            normalized,
        ):
            continue

        for synonym in dictionary.get(
            allergen,
            set(),
        ):

            if phrase_in_text(
                synonym,
                normalized,
            ):
                detected.add(allergen)
                break

    return detected


def normalized_with_context(text, dictionary):
    """
    Ablation 4:
    Normalization + contextual validation.

    Negation is intentionally NOT enabled here so that
    contextual validation can be measured separately.
    """

    if not text:
        return set()

    normalized = normalize_text(text)

    detected = set()

    for allergen in ALLERGENS:

        for synonym in dictionary.get(
            allergen,
            set(),
        ):

            if not phrase_in_text(
                synonym,
                normalized,
            ):
                continue

            if not _is_valid_match(
                allergen,
                synonym,
                normalized,
            ):
                continue

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
                int(
                    label
                    in row["reference"]
                )
                for label in labels
            ]
        )

        y_pred.append(
            [
                int(
                    label
                    in row[prediction_key]
                )
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
        "precision": round(
            float(precision),
            4,
        ),
        "recall": round(
            float(recall),
            4,
        ),
        "f1": round(
            float(f1),
            4,
        ),
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
            "precision": round(
                precision,
                4,
            ),
            "recall": round(
                recall,
                4,
            ),
            "f1": round(
                f1,
                4,
            ),
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

    normalized_dictionary = load_dictionary()
    raw_dictionary_values = raw_dictionary()

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
                raw_dictionary_values,
            )
        )

        normalized_prediction = (
            normalized_keyword_match(
                ingredients,
                normalized_dictionary,
            )
        )

        negation_prediction = (
            normalized_with_negation(
                ingredients,
                normalized_dictionary,
            )
        )

        context_prediction = (
            normalized_with_context(
                ingredients,
                normalized_dictionary,
            )
        )

        try:

            proposed = analyze_product(
                row,
                normalized_dictionary,
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
                "normalized_negation": negation_prediction,
                "normalized_context": context_prediction,
                "proposed": proposed_prediction,
            }
        )

    print()
    print("=" * 80)
    print("ALLERGEN MATCHER ABLATION STUDY")
    print("=" * 80)
    print(
        f"Products evaluated: {len(records)}"
    )

    methods = {
        "Exact keyword": "exact_keyword",
        "Normalized keyword": "normalized_keyword",
        "Normalized + negation": "normalized_negation",
        "Normalized + context": "normalized_context",
        "Full proposed matcher": "proposed",
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
            "Allergen matcher ablation study"
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
        f"{'METHOD':<28}"
        f"{'PRECISION':>12}"
        f"{'RECALL':>12}"
        f"{'F1':>12}"
        f"{'EXACT':>12}"
    )

    print("-" * 80)

    for row in comparison:

        print(
            f"{row['method']:<28}"
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