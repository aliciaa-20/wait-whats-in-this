"""
Error analysis for the text-only allergen matcher.

Uses the saved matcher benchmark results to identify:
- false negatives
- false positives
- partial matches
- exact matches

The analysis is descriptive. Open Food Facts metadata is treated
as reference metadata, not absolute ground truth.
"""

import json
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent
RESULTS_FILE = BASE_DIR / "data" / "benchmark" / "matcher_results.csv"
OUTPUT_DIR = BASE_DIR / "data" / "benchmark"

ERROR_FILE = OUTPUT_DIR / "matcher_error_analysis.csv"
SUMMARY_FILE = OUTPUT_DIR / "matcher_error_summary.json"


def parse_set(value):
    """Convert pipe-separated CSV value into a set."""

    if pd.isna(value):
        return set()

    value = str(value).strip()

    if not value:
        return set()

    return {
        item.strip()
        for item in value.split("|")
        if item.strip()
    }


def classify_error(reference, predicted):
    """Classify the relationship between reference and prediction."""

    if reference == predicted:
        return "exact_match"

    if reference and not predicted:
        return "false_negative"

    if predicted and not reference:
        return "false_positive"

    if reference & predicted:
        return "partial_match"

    return "mismatch"


def main():

    if not RESULTS_FILE.exists():
        raise FileNotFoundError(
            f"Benchmark results not found: {RESULTS_FILE}"
        )

    df = pd.read_csv(RESULTS_FILE)

    analysis_rows = []

    for _, row in df.iterrows():

        reference = parse_set(
            row["reference_allergens"]
        )

        predicted = parse_set(
            row["predicted_allergens"]
        )

        missed = reference - predicted
        extra = predicted - reference
        correct = reference & predicted

        category = classify_error(
            reference,
            predicted,
        )

        analysis_rows.append(
            {
                "code": row["code"],
                "product_name": row["product_name"],
                "reference_allergens": "|".join(
                    sorted(reference)
                ),
                "predicted_allergens": "|".join(
                    sorted(predicted)
                ),
                "correct_allergens": "|".join(
                    sorted(correct)
                ),
                "missed_allergens": "|".join(
                    sorted(missed)
                ),
                "extra_allergens": "|".join(
                    sorted(extra)
                ),
                "error_type": category,
                "exact_allergen_match": row[
                    "exact_allergen_match"
                ],
            }
        )

    analysis_df = pd.DataFrame(
        analysis_rows
    )

    analysis_df.to_csv(
        ERROR_FILE,
        index=False,
    )

    total = len(
        analysis_df
    )

    counts = (
        analysis_df["error_type"]
        .value_counts()
        .to_dict()
    )

    # Count individual missed and extra allergens.
    missed_counts = {}

    extra_counts = {}

    for _, row in analysis_df.iterrows():

        missed = parse_set(
            row["missed_allergens"]
        )

        extra = parse_set(
            row["extra_allergens"]
        )

        for allergen in missed:
            missed_counts[allergen] = (
                missed_counts.get(
                    allergen,
                    0,
                )
                + 1
            )

        for allergen in extra:
            extra_counts[allergen] = (
                extra_counts.get(
                    allergen,
                    0,
                )
                + 1
            )

    # Sort by frequency.
    missed_counts = dict(
        sorted(
            missed_counts.items(),
            key=lambda item: (
                -item[1],
                item[0],
            ),
        )
    )

    extra_counts = dict(
        sorted(
            extra_counts.items(),
            key=lambda item: (
                -item[1],
                item[0],
            ),
        )
    )

    summary = {
        "benchmark": (
            "Text-only allergen matcher error analysis"
        ),
        "source": str(
            RESULTS_FILE
        ),
        "products_evaluated": total,

        "error_type_counts": {
            key: int(value)
            for key, value in counts.items()
        },

        "error_type_percentages": {
            key: round(
                value / total * 100,
                2,
            )
            for key, value in counts.items()
        },

        "missed_allergens": {
            key: int(value)
            for key, value in missed_counts.items()
        },

        "extra_allergens": {
            key: int(value)
            for key, value in extra_counts.items()
        },

        "note": (
            "Differences from Open Food Facts metadata "
            "are not necessarily matcher errors because "
            "the metadata may be incomplete or incorrect. "
            "Manual verification is required before "
            "assigning definitive error causes."
        ),
    }

    with open(
        SUMMARY_FILE,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            summary,
            file,
            indent=2,
            ensure_ascii=False,
        )

    print()
    print("=" * 70)
    print("MATCHER ERROR ANALYSIS")
    print("=" * 70)

    print(
        f"Products evaluated: {total}"
    )

    print()
    print("ERROR CATEGORIES")
    print("-" * 70)

    category_order = [
        "exact_match",
        "partial_match",
        "false_negative",
        "false_positive",
        "mismatch",
    ]

    for category in category_order:

        count = counts.get(
            category,
            0,
        )

        percentage = (
            count / total * 100
            if total
            else 0
        )

        print(
            f"{category:<20}"
            f"{count:>8}"
            f"{percentage:>11.2f}%"
        )

    print()
    print("MOST FREQUENT MISSED ALLERGENS")
    print("-" * 70)

    if missed_counts:

        for allergen, count in (
            list(
                missed_counts.items()
            )[:10]
        ):

            print(
                f"{allergen:<20}"
                f"{count:>8}"
            )

    else:
        print("None")

    print()
    print("MOST FREQUENT EXTRA ALLERGENS")
    print("-" * 70)

    if extra_counts:

        for allergen, count in (
            list(
                extra_counts.items()
            )[:10]
        ):

            print(
                f"{allergen:<20}"
                f"{count:>8}"
            )

    else:
        print("None")

    print()
    print(
        f"Detailed results saved to: "
        f"{ERROR_FILE}"
    )

    print(
        f"Summary saved to: "
        f"{SUMMARY_FILE}"
    )


if __name__ == "__main__":
    main()