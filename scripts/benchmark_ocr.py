"""
Research benchmark for OCR + allergen detection.

Evaluates:
1. OCR text quality using CER and WER
2. Ingredient-section extraction
3. Declared allergen detection
4. Trace allergen detection
5. Exact allergen-set agreement
6. Risk classification

Important:
Open Food Facts metadata is treated as reference metadata,
not absolute ground truth. Final paper claims should use a
manually verified held-out test set.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pandas as pd

from scripts.ocr_processor import process_image
from scripts.allergen_matcher import (
    load_dictionary,
    analyze_ingredient_text,
)


BASE_DIR = Path(__file__).resolve().parents[1]

BENCHMARK_DIR = BASE_DIR / "data" / "benchmark"
METADATA_FILE = BENCHMARK_DIR / "metadata.csv"
RESULTS_FILE = BENCHMARK_DIR / "results.csv"
SUMMARY_FILE = BENCHMARK_DIR / "summary.json"


# =========================================================
# TEXT NORMALIZATION
# =========================================================

def normalize_text(text: str) -> str:
    """
    Normalize text before CER/WER comparison.

    This is intentionally conservative because CER/WER
    should measure OCR differences rather than allergen
    normalization.
    """

    if not text:
        return ""

    text = str(text).lower()

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    text = re.sub(
        r"[^\w\s%.,;:()'/+-]",
        "",
        text,
    )

    return text.strip()


# =========================================================
# LEVENSHTEIN
# =========================================================

def levenshtein(a: str, b: str) -> int:
    """Calculate Levenshtein edit distance."""

    if a == b:
        return 0

    if not a:
        return len(b)

    if not b:
        return len(a)

    previous = list(
        range(len(b) + 1)
    )

    for i, char_a in enumerate(
        a,
        start=1,
    ):

        current = [i]

        for j, char_b in enumerate(
            b,
            start=1,
        ):

            insertion = (
                current[j - 1] + 1
            )

            deletion = (
                previous[j] + 1
            )

            substitution = (
                previous[j - 1]
                + (char_a != char_b)
            )

            current.append(
                min(
                    insertion,
                    deletion,
                    substitution,
                )
            )

        previous = current

    return previous[-1]


# =========================================================
# OCR METRICS
# =========================================================

def character_error_rate(
    reference: str,
    prediction: str,
) -> float:
    """Calculate character error rate."""

    reference = normalize_text(
        reference
    )

    prediction = normalize_text(
        prediction
    )

    if not reference:

        return (
            0.0
            if not prediction
            else 1.0
        )

    return levenshtein(
        reference,
        prediction,
    ) / len(reference)


def word_error_rate(
    reference: str,
    prediction: str,
) -> float:
    """Calculate word error rate."""

    reference_words = normalize_text(
        reference
    ).split()

    prediction_words = normalize_text(
        prediction
    ).split()

    if not reference_words:

        return (
            0.0
            if not prediction_words
            else 1.0
        )

    previous = list(
        range(
            len(prediction_words) + 1
        )
    )

    for i, word_a in enumerate(
        reference_words,
        start=1,
    ):

        current = [i]

        for j, word_b in enumerate(
            prediction_words,
            start=1,
        ):

            insertion = (
                current[j - 1] + 1
            )

            deletion = (
                previous[j] + 1
            )

            substitution = (
                previous[j - 1]
                + (word_a != word_b)
            )

            current.append(
                min(
                    insertion,
                    deletion,
                    substitution,
                )
            )

        previous = current

    return (
        previous[-1]
        / len(reference_words)
    )


# =========================================================
# TAG PARSING
# =========================================================

ALLERGEN_TAG_MAP = {
    "en:milk": "milk",

    "en:eggs": "egg",
    "en:egg": "egg",

    "en:peanuts": "peanut",
    "en:peanut": "peanut",

    "en:nuts": "tree_nut",
    "en:tree-nuts": "tree_nut",

    "en:soybeans": "soy",
    "en:soy": "soy",

    "en:gluten": "wheat_gluten",
    "en:wheat": "wheat_gluten",

    "en:fish": "fish",

    "en:crustaceans": "shellfish",
    "en:molluscs": "shellfish",

    "en:sesame-seeds": "sesame",
    "en:sesame": "sesame",
}


def parse_tags(value) -> set[str]:
    """
    Parse Open Food Facts tag fields.

    Handles:
    - Python-style lists
    - pipe-separated strings
    - comma-separated strings
    - single tags
    """

    if value is None:
        return set()

    try:
        if pd.isna(value):
            return set()
    except (TypeError, ValueError):
        pass

    if isinstance(value, list):

        raw_tags = value

    else:

        text = str(value).strip()

        if not text:
            return set()

        # Serialized Python/JSON-style list
        if (
            text.startswith("[")
            and text.endswith("]")
        ):

            try:

                parsed = ast.literal_eval(
                    text
                )

                if isinstance(
                    parsed,
                    list,
                ):
                    raw_tags = parsed

                else:
                    raw_tags = [text]

            except (
                ValueError,
                SyntaxError,
            ):

                raw_tags = [text]

        elif "|" in text:

            raw_tags = text.split("|")

        elif "," in text:

            raw_tags = text.split(",")

        else:

            raw_tags = [text]

    result = set()

    for tag in raw_tags:

        tag = str(
            tag
        ).strip().lower()

        if not tag:
            continue

        canonical = ALLERGEN_TAG_MAP.get(
            tag
        )

        if canonical:
            result.add(canonical)

    return result


# =========================================================
# METRICS
# =========================================================

def multilabel_metrics(
    references: list[set[str]],
    predictions: list[set[str]],
) -> dict:
    """
    Calculate micro multilabel precision,
    recall and F1.
    """

    true_positive = 0
    false_positive = 0
    false_negative = 0

    for reference, prediction in zip(
        references,
        predictions,
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

    precision = (
        true_positive
        / (
            true_positive
            + false_positive
        )
        if (
            true_positive
            + false_positive
        )
        else 0.0
    )

    recall = (
        true_positive
        / (
            true_positive
            + false_negative
        )
        if (
            true_positive
            + false_negative
        )
        else 0.0
    )

    f1 = (
        2 * precision * recall
        / (precision + recall)
        if precision + recall
        else 0.0
    )

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
    }


def exact_set_agreement(
    references: list[set[str]],
    predictions: list[set[str]],
) -> float:

    if not references:
        return 0.0

    correct = sum(
        reference == prediction
        for reference, prediction in zip(
            references,
            predictions,
        )
    )

    return correct / len(references)


# =========================================================
# RISK METRICS
# =========================================================

def risk_from_sets(
    declared: set[str],
    traces: set[str],
) -> str:
    """
    Convert allergen sets into the project's
    three-level risk classification.
    """

    if declared:
        return "AVOID"

    if traces:
        return "CAUTION"

    return "SAFE"


def risk_classification_metrics(
    reference_declared: list[set[str]],
    reference_traces: list[set[str]],
    predicted_declared: list[set[str]],
    predicted_traces: list[set[str]],
) -> dict:
    """
    Evaluate AVOID / CAUTION / SAFE classification
    using the reference and predicted allergen sets.
    """

    if not reference_declared:
        return {
            "accuracy": 0.0,
            "total": 0,
            "correct": 0,
        }

    correct = 0

    for (
        ref_declared,
        ref_traces,
        pred_declared,
        pred_traces,
    ) in zip(
        reference_declared,
        reference_traces,
        predicted_declared,
        predicted_traces,
    ):

        reference_risk = risk_from_sets(
            ref_declared,
            ref_traces,
        )

        predicted_risk = risk_from_sets(
            pred_declared,
            pred_traces,
        )

        if reference_risk == predicted_risk:
            correct += 1

    total = len(reference_declared)

    return {
        "accuracy": correct / total,
        "total": total,
        "correct": correct,
    }


# =========================================================
# MAIN BENCHMARK
# =========================================================

def main():

    if not METADATA_FILE.exists():

        raise FileNotFoundError(
            f"Missing benchmark metadata: "
            f"{METADATA_FILE}"
        )

    metadata = pd.read_csv(
        METADATA_FILE
    )

    dictionary = load_dictionary()

    results = []

    reference_allergens = []
    predicted_allergens = []

    reference_traces = []
    predicted_traces = []

    extraction_successes = []

    print("=" * 70)
    print("OCR + ALLERGEN BENCHMARK")
    print("=" * 70)

    print(
        f"Samples: {len(metadata)}"
    )

    for index, row in metadata.iterrows():

        code = str(
            row.get(
                "code",
                "",
            )
        )

        image_path = (
            BENCHMARK_DIR
            / str(
                row.get(
                    "image_path",
                    "",
                )
            )
        )

        # -------------------------------------------------
        # Language
        # -------------------------------------------------

        image_language = str(
            row.get(
                "image_language",
                row.get(
                    "language",
                    "en",
                ),
            )
            or "en"
        ).strip().lower()

        if not image_language:
            image_language = "en"

        print()

        print(
            f"[{index + 1}/{len(metadata)}] "
            f"{code} "
            f"(language={image_language})..."
        )

        # -------------------------------------------------
        # OCR
        # -------------------------------------------------

        try:

            output = process_image(
                image_path,
                language=image_language,
            )

            predicted_text = (
                output.get(
                    "ingredient_text",
                    "",
                )
                or ""
            )

            extraction_found = bool(
                output.get(
                    "ingredient_section_found",
                    False,
                )
            )

            confidence = float(
                output.get(
                    "ocr_confidence",
                    0.0,
                )
            )

        except Exception as exc:

            print(
                f"ERROR: {exc}"
            )

            predicted_text = ""
            extraction_found = False
            confidence = 0.0

        # -------------------------------------------------
        # Reference metadata
        # -------------------------------------------------

        reference_text = str(
            row.get(
                "reference_ingredients_text",
                "",
            )
            or ""
        )

        ref_allergens = parse_tags(
            row.get(
                "allergens_tags",
                "",
            )
        )

        ref_traces = parse_tags(
            row.get(
                "traces_tags",
                "",
            )
        )

        # -------------------------------------------------
        # Allergen analysis
        # -------------------------------------------------

        if predicted_text.strip():

            try:

                analysis = analyze_ingredient_text(
                    predicted_text,
                    dictionary,
                )

                pred_allergens = set(
                    analysis.get(
                        "declared_allergens",
                        [],
                    )
                )

                pred_traces = set(
                    analysis.get(
                        "trace_allergens",
                        [],
                    )
                )

                risk = analysis.get(
                    "risk",
                    "UNKNOWN",
                )

            except Exception as exc:

                print(
                    f"Matcher ERROR: {exc}"
                )

                pred_allergens = set()
                pred_traces = set()
                risk = "UNKNOWN"

        else:

            pred_allergens = set()
            pred_traces = set()
            risk = "UNKNOWN"

        # -------------------------------------------------
        # OCR metrics
        # -------------------------------------------------

        cer = character_error_rate(
            reference_text,
            predicted_text,
        )

        wer = word_error_rate(
            reference_text,
            predicted_text,
        )

        # -------------------------------------------------
        # Reference risk
        # -------------------------------------------------

        reference_risk = risk_from_sets(
            ref_allergens,
            ref_traces,
        )

        # -------------------------------------------------
        # Save sample result
        # -------------------------------------------------

        results.append({

            "code": code,

            "product_name": row.get(
                "product_name",
                "",
            ),

            "image_path": row.get(
                "image_path",
                "",
            ),

            "image_language": image_language,

            "ocr_language": output.get(
                "ocr_language",
                image_language,
            )
            if "output" in locals()
            and isinstance(output, dict)
            else image_language,

            "ocr_confidence": confidence,

            "reference_text": reference_text,

            "predicted_text": predicted_text,

            "cer": cer,

            "wer": wer,

            "extraction_found": extraction_found,

            "reference_allergens": "|".join(
                sorted(ref_allergens)
            ),

            "predicted_allergens": "|".join(
                sorted(pred_allergens)
            ),

            "reference_traces": "|".join(
                sorted(ref_traces)
            ),

            "predicted_traces": "|".join(
                sorted(pred_traces)
            ),

            "reference_risk": reference_risk,

            "predicted_risk": risk,

            "exact_allergen_match": (
                ref_allergens
                == pred_allergens
            ),

            "exact_trace_match": (
                ref_traces
                == pred_traces
            ),

        })

        # -------------------------------------------------
        # Aggregate arrays
        # -------------------------------------------------

        reference_allergens.append(
            ref_allergens
        )

        predicted_allergens.append(
            pred_allergens
        )

        reference_traces.append(
            ref_traces
        )

        predicted_traces.append(
            pred_traces
        )

        extraction_successes.append(
            extraction_found
        )

    # =====================================================
    # AGGREGATE METRICS
    # =====================================================

    allergen_metrics = multilabel_metrics(
        reference_allergens,
        predicted_allergens,
    )

    trace_metrics = multilabel_metrics(
        reference_traces,
        predicted_traces,
    )

    allergen_exact_match = exact_set_agreement(
        reference_allergens,
        predicted_allergens,
    )

    trace_exact_match = exact_set_agreement(
        reference_traces,
        predicted_traces,
    )

    risk_metrics = risk_classification_metrics(
        reference_allergens,
        reference_traces,
        predicted_allergens,
        predicted_traces,
    )

    # -----------------------------------------------------
    # OCR averages
    # -----------------------------------------------------

    mean_confidence = (
        sum(
            float(
                x["ocr_confidence"]
            )
            for x in results
        )
        / len(results)
        if results
        else 0.0
    )

    mean_cer = (
        sum(
            float(
                x["cer"]
            )
            for x in results
        )
        / len(results)
        if results
        else 0.0
    )

    mean_wer = (
        sum(
            float(
                x["wer"]
            )
            for x in results
        )
        / len(results)
        if results
        else 0.0
    )

    extraction_rate = (
        sum(
            extraction_successes
        )
        / len(extraction_successes)
        if extraction_successes
        else 0.0
    )

    # -----------------------------------------------------
    # Sample counts
    # -----------------------------------------------------

    reference_allergen_samples = sum(
        bool(x)
        for x in reference_allergens
    )

    reference_trace_samples = sum(
        bool(x)
        for x in reference_traces
    )

    predicted_allergen_samples = sum(
        bool(x)
        for x in predicted_allergens
    )

    predicted_trace_samples = sum(
        bool(x)
        for x in predicted_traces
    )

    # =====================================================
    # SUMMARY
    # =====================================================

    summary = {

        "samples": len(results),

        "mean_ocr_confidence":
            mean_confidence,

        "mean_cer":
            mean_cer,

        "mean_wer":
            mean_wer,

        "ingredient_extraction_rate":
            extraction_rate,

        # ---------------------------------------------
        # Declared allergens
        # ---------------------------------------------

        "reference_allergen_samples":
            reference_allergen_samples,

        "predicted_allergen_samples":
            predicted_allergen_samples,

        "allergen_precision":
            allergen_metrics["precision"],

        "allergen_recall":
            allergen_metrics["recall"],

        "allergen_f1":
            allergen_metrics["f1"],

        "allergen_true_positive":
            allergen_metrics["true_positive"],

        "allergen_false_positive":
            allergen_metrics["false_positive"],

        "allergen_false_negative":
            allergen_metrics["false_negative"],

        "allergen_exact_set_agreement":
            allergen_exact_match,

        # ---------------------------------------------
        # Trace allergens
        # ---------------------------------------------

        "reference_trace_samples":
            reference_trace_samples,

        "predicted_trace_samples":
            predicted_trace_samples,

        "trace_precision":
            trace_metrics["precision"],

        "trace_recall":
            trace_metrics["recall"],

        "trace_f1":
            trace_metrics["f1"],

        "trace_true_positive":
            trace_metrics["true_positive"],

        "trace_false_positive":
            trace_metrics["false_positive"],

        "trace_false_negative":
            trace_metrics["false_negative"],

        "trace_exact_set_agreement":
            trace_exact_match,

        # ---------------------------------------------
        # Risk classification
        # ---------------------------------------------

        "risk_accuracy":
            risk_metrics["accuracy"],

        "risk_correct":
            risk_metrics["correct"],

        "risk_total":
            risk_metrics["total"],

        # ---------------------------------------------
        # Methodological note
        # ---------------------------------------------

        "reference_note": (
            "Open Food Facts ingredient text and "
            "allergen tags are reference metadata, "
            "not absolute ground truth. A manually "
            "verified held-out set is required for "
            "final paper claims."
        ),
    }

    # =====================================================
    # SAVE RESULTS
    # =====================================================

    BENCHMARK_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    pd.DataFrame(results).to_csv(
        RESULTS_FILE,
        index=False,
    )

    with SUMMARY_FILE.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            summary,
            file,
            indent=2,
            ensure_ascii=False,
        )

    # =====================================================
    # PRINT SUMMARY
    # =====================================================

    print()
    print("=" * 70)
    print("OCR + ALLERGEN BENCHMARK RESULTS")
    print("=" * 70)

    print(
        f"\nSamples: "
        f"{summary['samples']}"
    )

    print(
        f"OCR confidence: "
        f"{summary['mean_ocr_confidence']:.4f}"
    )

    print(
        f"CER: "
        f"{summary['mean_cer']:.4f}"
    )

    print(
        f"WER: "
        f"{summary['mean_wer']:.4f}"
    )

    print(
        f"Ingredient extraction rate: "
        f"{summary['ingredient_extraction_rate']:.4f}"
    )

    print()
    print("DECLARED ALLERGENS")
    print("-" * 70)

    print(
        f"Precision: "
        f"{summary['allergen_precision']:.4f}"
    )

    print(
        f"Recall: "
        f"{summary['allergen_recall']:.4f}"
    )

    print(
        f"F1: "
        f"{summary['allergen_f1']:.4f}"
    )

    print(
        f"Exact set agreement: "
        f"{summary['allergen_exact_set_agreement']:.4f}"
    )

    print()
    print("TRACE ALLERGENS")
    print("-" * 70)

    print(
        f"Precision: "
        f"{summary['trace_precision']:.4f}"
    )

    print(
        f"Recall: "
        f"{summary['trace_recall']:.4f}"
    )

    print(
        f"F1: "
        f"{summary['trace_f1']:.4f}"
    )

    print(
        f"Exact set agreement: "
        f"{summary['trace_exact_set_agreement']:.4f}"
    )

    print()
    print("RISK CLASSIFICATION")
    print("-" * 70)

    print(
        f"Accuracy: "
        f"{summary['risk_accuracy']:.4f}"
    )

    print()
    print(
        f"Results saved to: "
        f"{RESULTS_FILE}"
    )

    print(
        f"Summary saved to: "
        f"{SUMMARY_FILE}"
    )

    print("=" * 70)


if __name__ == "__main__":
    main()