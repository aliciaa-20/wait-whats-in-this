import ast
import json
from pathlib import Path

import pandas as pd

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.allergen_matcher import (
    analyze_ingredient_text,
    load_dictionary,
)


# ============================================================
# Configuration
# ============================================================

INPUT_FILE = Path("data/research/ground_truth.csv")

OUTPUT_PREDICTIONS = Path(
    "data/research/heldout_predictions.csv"
)

OUTPUT_RESULTS = Path(
    "data/research/heldout_results.json"
)


ALLERGENS = [
    "milk",
    "egg",
    "peanut",
    "tree_nut",
    "soy",
    "wheat_gluten",
    "fish",
    "shellfish",
    "sesame",
]


# ============================================================
# Helpers
# ============================================================

def parse_allergens(value):
    """
    Convert comma-separated allergen IDs into a set.
    """

    if pd.isna(value):
        return set()

    value = str(value).strip()

    if not value or value.lower() == "nan":
        return set()

    return {
        item.strip()
        for item in value.split(",")
        if item.strip()
    }


def safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def extract_prediction(result):
    """
    Extract declared and trace allergen predictions from the
    existing matcher output.

    This function is deliberately defensive because the matcher
    output structure may contain additional fields.
    """

    declared = set()
    trace = set()

    if not isinstance(result, dict):
        return declared, trace

    # --------------------------------------------------------
    # Common direct fields
    # --------------------------------------------------------

    possible_declared = [
        "declared_allergens",
        "declared",
        "detected_allergens",
    ]

    possible_trace = [
        "trace_allergens",
        "trace",
        "traces",
    ]

    for field in possible_declared:
        value = result.get(field)

        if isinstance(value, list):
            declared.update(
                str(x).strip()
                for x in value
                if str(x).strip()
            )

        elif isinstance(value, str):
            declared.update(
                x.strip()
                for x in value.split(",")
                if x.strip()
            )

    for field in possible_trace:
        value = result.get(field)

        if isinstance(value, list):
            trace.update(
                str(x).strip()
                for x in value
                if str(x).strip()
            )

        elif isinstance(value, str):
            trace.update(
                x.strip()
                for x in value.split(",")
                if x.strip()
            )

    # --------------------------------------------------------
    # Normalize to supported allergen IDs
    # --------------------------------------------------------

    declared &= set(ALLERGENS)
    trace &= set(ALLERGENS)

    return declared, trace


def calculate_metrics(reference_sets, prediction_sets):
    """
    Calculate micro-level multilabel precision, recall and F1.
    """

    true_positive = 0
    false_positive = 0
    false_negative = 0

    exact_matches = 0

    for reference, prediction in zip(
        reference_sets,
        prediction_sets
    ):

        true_positive += len(
            reference & prediction
        )

        false_positive += len(
            prediction - reference
        )

        false_negative += len(
            reference - prediction
        )

        if reference == prediction:
            exact_matches += 1

    precision = (
        true_positive /
        (true_positive + false_positive)
        if true_positive + false_positive > 0
        else 0.0
    )

    recall = (
        true_positive /
        (true_positive + false_negative)
        if true_positive + false_negative > 0
        else 0.0
    )

    f1 = (
        2 * precision * recall /
        (precision + recall)
        if precision + recall > 0
        else 0.0
    )

    exact_match = (
        exact_matches / len(reference_sets)
        if reference_sets
        else 0.0
    )

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "exact_match": exact_match,
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
    }


def calculate_per_allergen(
    reference_sets,
    prediction_sets
):
    """
    Calculate binary classification metrics for each allergen.
    """

    results = {}

    for allergen in ALLERGENS:

        tp = 0
        fp = 0
        fn = 0
        support = 0

        for reference, prediction in zip(
            reference_sets,
            prediction_sets
        ):

            reference_has = allergen in reference
            prediction_has = allergen in prediction

            if reference_has:
                support += 1

            if reference_has and prediction_has:
                tp += 1

            elif not reference_has and prediction_has:
                fp += 1

            elif reference_has and not prediction_has:
                fn += 1

        precision = (
            tp / (tp + fp)
            if tp + fp > 0
            else 0.0
        )

        recall = (
            tp / (tp + fn)
            if tp + fn > 0
            else 0.0
        )

        f1 = (
            2 * precision * recall /
            (precision + recall)
            if precision + recall > 0
            else 0.0
        )

        results[allergen] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": support,
            "true_positive": tp,
            "false_positive": fp,
            "false_negative": fn,
        }

    return results


def risk_from_sets(declared, trace):
    """
    Convert allergen sets to the general risk category used
    by the existing project logic.
    """

    if declared:
        return "AVOID"

    if trace:
        return "CAUTION"

    return "SAFE"


# ============================================================
# Main evaluation
# ============================================================

def main():

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Could not find {INPUT_FILE}"
        )

    print()
    print("=" * 70)
    print("WAIT, WHAT'S IN THIS?")
    print("HELD-OUT EVALUATION")
    print("=" * 70)

    # --------------------------------------------------------
    # Load data
    # --------------------------------------------------------

    df = pd.read_csv(INPUT_FILE)

    print(
        f"Products loaded: {len(df)}"
    )

    if len(df) == 0:
        raise ValueError(
            "Held-out dataset is empty."
        )

    # --------------------------------------------------------
    # Load dictionary
    # --------------------------------------------------------

    dictionary = load_dictionary()

    # --------------------------------------------------------
    # Evaluation storage
    # --------------------------------------------------------

    declared_references = []
    declared_predictions = []

    trace_references = []
    trace_predictions = []

    prediction_rows = []

    # --------------------------------------------------------
    # Process every product
    # --------------------------------------------------------

    for index, row in df.iterrows():

        code = str(
            row.get("code", "")
        ).strip()

        product_name = str(
            row.get("product_name", "")
        ).strip()

        ingredients = str(
            row.get("reference_ingredients", "")
        ).strip()

        # ----------------------------------------------------
        # Reference labels
        # ----------------------------------------------------

        reference_declared = parse_allergens(
            row.get("off_declared_allergens")
        )

        reference_trace = parse_allergens(
            row.get("off_trace_allergens")
        )

        # ----------------------------------------------------
        # Run proposed matcher
        # ----------------------------------------------------

        try:

            result = analyze_ingredient_text(
                ingredients,
                dictionary
            )

            predicted_declared, predicted_trace = (
                extract_prediction(result)
            )

            matcher_error = ""

        except Exception as exc:

            predicted_declared = set()
            predicted_trace = set()

            matcher_error = str(exc)

        # ----------------------------------------------------
        # Store sets
        # ----------------------------------------------------

        declared_references.append(
            reference_declared
        )

        declared_predictions.append(
            predicted_declared
        )

        trace_references.append(
            reference_trace
        )

        trace_predictions.append(
            predicted_trace
        )

        # ----------------------------------------------------
        # Status
        # ----------------------------------------------------

        declared_exact = (
            reference_declared ==
            predicted_declared
        )

        trace_exact = (
            reference_trace ==
            predicted_trace
        )

        overall_exact = (
            declared_exact and
            trace_exact
        )

        if overall_exact:
            status = "exact_match"

        elif (
            predicted_declared - reference_declared
            or predicted_trace - reference_trace
        ) and (
            reference_declared - predicted_declared
            or reference_trace - predicted_trace
        ):
            status = "mismatch"

        elif (
            predicted_declared - reference_declared
            or predicted_trace - reference_trace
        ):
            status = "false_positive"

        elif (
            reference_declared - predicted_declared
            or reference_trace - predicted_trace
        ):
            status = "false_negative"

        else:
            status = "partial_match"

        # ----------------------------------------------------
        # Risk
        # ----------------------------------------------------

        reference_risk = risk_from_sets(
            reference_declared,
            reference_trace
        )

        predicted_risk = risk_from_sets(
            predicted_declared,
            predicted_trace
        )

        risk_correct = (
            reference_risk ==
            predicted_risk
        )

        # ----------------------------------------------------
        # Prediction row
        # ----------------------------------------------------

        prediction_rows.append({
            "code": code,
            "product_name": product_name,
            "lang": row.get("lang", ""),

            "reference_declared": ", ".join(
                sorted(reference_declared)
            ),

            "predicted_declared": ", ".join(
                sorted(predicted_declared)
            ),

            "reference_trace": ", ".join(
                sorted(reference_trace)
            ),

            "predicted_trace": ", ".join(
                sorted(predicted_trace)
            ),

            "reference_risk": reference_risk,
            "predicted_risk": predicted_risk,
            "risk_correct": risk_correct,

            "declared_exact": declared_exact,
            "trace_exact": trace_exact,
            "overall_exact": overall_exact,

            "status": status,

            "matcher_error": matcher_error,
        })

        # ----------------------------------------------------
        # Progress
        # ----------------------------------------------------

        if (
            (index + 1) % 50 == 0
            or index + 1 == len(df)
        ):
            print(
                f"Processed {index + 1} / {len(df)}"
            )

    # ========================================================
    # Metrics
    # ========================================================

    declared_metrics = calculate_metrics(
        declared_references,
        declared_predictions
    )

    trace_metrics = calculate_metrics(
        trace_references,
        trace_predictions
    )

    declared_per_allergen = calculate_per_allergen(
        declared_references,
        declared_predictions
    )

    trace_per_allergen = calculate_per_allergen(
        trace_references,
        trace_predictions
    )

    # --------------------------------------------------------
    # Overall exact match
    # --------------------------------------------------------

    exact_count = sum(
        row["overall_exact"]
        for row in prediction_rows
    )

    exact_match = (
        exact_count / len(prediction_rows)
    )

    # --------------------------------------------------------
    # Risk accuracy
    # --------------------------------------------------------

    risk_correct_count = sum(
        row["risk_correct"]
        for row in prediction_rows
    )

    risk_accuracy = (
        risk_correct_count /
        len(prediction_rows)
    )

    # --------------------------------------------------------
    # Status distribution
    # --------------------------------------------------------

    status_counts = (
        pd.Series(
            row["status"]
            for row in prediction_rows
        )
        .value_counts()
        .to_dict()
    )

    # --------------------------------------------------------
    # Language distribution
    # --------------------------------------------------------

    language_counts = (
        pd.Series(
            row["lang"]
            for row in prediction_rows
        )
        .fillna("unknown")
        .value_counts()
        .to_dict()
    )

    # ========================================================
    # Save prediction CSV
    # ========================================================

    predictions_df = pd.DataFrame(
        prediction_rows
    )

    OUTPUT_PREDICTIONS.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    predictions_df.to_csv(
        OUTPUT_PREDICTIONS,
        index=False,
        encoding="utf-8"
    )

    # ========================================================
    # Save results JSON
    # ========================================================

    results = {
        "evaluation_type": (
            "held-out evaluation against "
            "Open Food Facts reference annotations"
        ),

        "dataset": {
            "products_evaluated": len(df),
            "input_file": str(INPUT_FILE),
            "language_distribution": language_counts,
        },

        "declared_allergens": declared_metrics,

        "trace_allergens": trace_metrics,

        "overall": {
            "exact_match": exact_match,
            "exact_match_count": exact_count,
            "risk_accuracy": risk_accuracy,
            "risk_correct_count": risk_correct_count,
        },

        "declared_per_allergen": (
            declared_per_allergen
        ),

        "trace_per_allergen": (
            trace_per_allergen
        ),

        "status_distribution": status_counts,

        "methodology_notes": [
            (
                "Products were sampled as a held-out set "
                "and excluded from the previous 18-image OCR benchmark."
            ),
            (
                "Reference annotations are Open Food Facts "
                "metadata and are not treated as manually verified ground truth."
            ),
            (
                "The proposed matcher was evaluated without "
                "changing its rules based on this held-out set."
            ),
            (
                "Results should be interpreted in light of "
                "the crowdsourced nature of Open Food Facts annotations."
            ),
        ],
    }

    with open(
        OUTPUT_RESULTS,
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            results,
            f,
            indent=2,
            ensure_ascii=False
        )

    # ========================================================
    # Print results
    # ========================================================

    print()
    print("=" * 70)
    print("HELD-OUT RESULTS")
    print("=" * 70)

    print()
    print("Products evaluated:", len(df))

    print()
    print("DECLARED ALLERGENS")
    print(
        f"Precision: {declared_metrics['precision']:.4f}"
    )
    print(
        f"Recall:    {declared_metrics['recall']:.4f}"
    )
    print(
        f"F1:        {declared_metrics['f1']:.4f}"
    )
    print(
        f"Exact:     {declared_metrics['exact_match']:.4f}"
    )

    print()
    print("TRACE ALLERGENS")
    print(
        f"Precision: {trace_metrics['precision']:.4f}"
    )
    print(
        f"Recall:    {trace_metrics['recall']:.4f}"
    )
    print(
        f"F1:        {trace_metrics['f1']:.4f}"
    )
    print(
        f"Exact:     {trace_metrics['exact_match']:.4f}"
    )

    print()
    print("OVERALL")
    print(
        f"Exact match:   {exact_match:.4f}"
    )
    print(
        f"Risk accuracy: {risk_accuracy:.4f}"
    )

    print()
    print("STATUS DISTRIBUTION")

    for status, count in sorted(
        status_counts.items()
    ):
        print(
            f"{status:18s}: {count}"
        )

    print()
    print("PER-ALLERGEN DECLARED F1")

    for allergen in ALLERGENS:

        metrics = declared_per_allergen[
            allergen
        ]

        print(
            f"{allergen:15s} "
            f"P={metrics['precision']:.4f} "
            f"R={metrics['recall']:.4f} "
            f"F1={metrics['f1']:.4f} "
            f"Support={metrics['support']}"
        )

    print()
    print("=" * 70)

    print(
        f"Predictions saved to: {OUTPUT_PREDICTIONS}"
    )

    print(
        f"Results saved to: {OUTPUT_RESULTS}"
    )

    print("=" * 70)


if __name__ == "__main__":
    main()