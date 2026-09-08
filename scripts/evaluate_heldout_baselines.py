import json
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.allergen_matcher import (
    analyze_ingredient_text,
    load_dictionary,
    normalize_text,
)


INPUT_FILE = Path("data/research/ground_truth.csv")

OUTPUT_FILE = Path(
    "data/research/heldout_baseline_comparison.json"
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


KEYWORDS = {
    "milk": [
        "milk", "lait", "leche", "leite", "milch", "melk",
        "latte", "lactose", "whey", "casein", "caseinate",
        "cream", "creme", "crème", "butter", "beurre",
    ],
    "egg": [
        "egg", "eggs", "oeuf", "oeufs", "huevo", "huevos",
        "ovo", "eier", "ei",
    ],
    "peanut": [
        "peanut", "peanuts", "arachide", "arachides",
        "cacahuete", "cacahuètes", "amendoim", "erdnuss",
    ],
    "tree_nut": [
        "almond", "almonds", "amande", "amandes",
        "almendra", "almendras", "hazelnut", "hazelnuts",
        "noisette", "noisettes", "hazelnuss",
        "walnut", "walnuts", "noix", "pecan", "pecans",
        "pistachio", "pistachios", "pistache",
        "cashew", "cashews", "cajou", "macadamia",
        "nut", "nuts", "nueces", "fruits à coque",
    ],
    "soy": [
        "soy", "soya", "soybean", "soybeans", "soja",
        "sojabohne", "sojabohnen",
    ],
    "wheat_gluten": [
        "wheat", "wheat flour", "flour", "gluten",
        "wheat gluten", "ble", "blé", "farine",
        "farine de blé", "trigo", "harina",
        "harina de trigo", "weizen", "weizenmehl", "mehl",
    ],
    "fish": [
        "fish", "poisson", "pescado", "peixe", "fisch",
        "tuna", "thon", "salmon", "saumon", "salmón",
        "anchovy", "anchois",
    ],
    "shellfish": [
        "shellfish", "crustacean", "crustaceans",
        "crustacé", "crustacés", "crustaceo", "crustaceos",
        "shrimp", "prawn", "crevette", "crevettes",
        "gamba", "gambas", "scampi", "crab", "crabe",
        "lobster", "homard", "mollusc", "molluscs",
        "mollusque", "mollusques",
    ],
    "sesame": [
        "sesame", "sésame", "sesamo", "gergelim", "sesam",
    ],
}


def parse_allergens(value):
    if pd.isna(value):
        return set()

    value = str(value).strip()

    if not value or value.lower() == "nan":
        return set()

    return {
        x.strip()
        for x in value.split(",")
        if x.strip() in ALLERGENS
    }


def exact_keyword_match(text):
    predicted = set()

    lower_text = text.lower()

    for allergen, terms in KEYWORDS.items():
        for term in terms:
            if term.lower() in lower_text:
                predicted.add(allergen)
                break

    return predicted


def normalized_keyword_match(text):
    normalized = normalize_text(text)

    predicted = set()

    for allergen, terms in KEYWORDS.items():
        for term in terms:
            normalized_term = normalize_text(term)

            if normalized_term and normalized_term in normalized:
                predicted.add(allergen)
                break

    return predicted


def extract_proposed_declared(result):
    if not isinstance(result, dict):
        return set()

    value = result.get("declared_allergens", [])

    if isinstance(value, list):
        return {
            str(x).strip()
            for x in value
            if str(x).strip() in ALLERGENS
        }

    if isinstance(value, str):
        return {
            x.strip()
            for x in value.split(",")
            if x.strip() in ALLERGENS
        }

    return set()


def extract_proposed_trace(result):
    if not isinstance(result, dict):
        return set()

    value = result.get("trace_allergens", [])

    if isinstance(value, list):
        return {
            str(x).strip()
            for x in value
            if str(x).strip() in ALLERGENS
        }

    if isinstance(value, str):
        return {
            x.strip()
            for x in value.split(",")
            if x.strip() in ALLERGENS
        }

    return set()


def metrics(references, predictions):
    tp = fp = fn = exact = 0

    for reference, prediction in zip(references, predictions):
        tp += len(reference & prediction)
        fp += len(prediction - reference)
        fn += len(reference - prediction)

        if reference == prediction:
            exact += 1

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0

    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )

    exact_match = exact / len(references) if references else 0.0

    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "exact_match": round(exact_match, 4),
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
    }


def per_allergen_metrics(references, predictions):
    results = {}

    for allergen in ALLERGENS:
        tp = fp = fn = 0

        for reference, prediction in zip(
            references,
            predictions,
        ):
            ref = allergen in reference
            pred = allergen in prediction

            if ref and pred:
                tp += 1
            elif not ref and pred:
                fp += 1
            elif ref and not pred:
                fn += 1

        support = tp + fn

        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0

        f1 = (
            2 * precision * recall / (precision + recall)
            if precision + recall
            else 0.0
        )

        results[allergen] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "support": support,
        }

    return results


def main():
    print()
    print("=" * 70)
    print("WAIT, WHAT'S IN THIS?")
    print("HELD-OUT BASELINE COMPARISON")
    print("=" * 70)

    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Missing {INPUT_FILE}")

    df = pd.read_csv(INPUT_FILE)

    print(f"Products evaluated: {len(df)}")

    dictionary = load_dictionary()

    declared_references = []

    exact_predictions = []
    normalized_predictions = []
    proposed_predictions = []

    trace_references = []
    proposed_trace_predictions = []

    for index, row in df.iterrows():

        ingredients = str(
            row.get("reference_ingredients", "")
        ).strip()

        declared_reference = parse_allergens(
            row.get("off_declared_allergens")
        )

        trace_reference = parse_allergens(
            row.get("off_trace_allergens")
        )

        exact_prediction = exact_keyword_match(
            ingredients
        )

        normalized_prediction = normalized_keyword_match(
            ingredients
        )

        try:
            result = analyze_ingredient_text(
                ingredients,
                dictionary,
            )

            proposed_declared = extract_proposed_declared(
                result
            )

            proposed_trace = extract_proposed_trace(
                result
            )

        except Exception as exc:
            print(
                f"Warning: matcher error on row "
                f"{index + 1}: {exc}"
            )

            proposed_declared = set()
            proposed_trace = set()

        declared_references.append(
            declared_reference
        )

        exact_predictions.append(
            exact_prediction
        )

        normalized_predictions.append(
            normalized_prediction
        )

        proposed_predictions.append(
            proposed_declared
        )

        trace_references.append(
            trace_reference
        )

        proposed_trace_predictions.append(
            proposed_trace
        )

        if (
            (index + 1) % 50 == 0
            or index + 1 == len(df)
        ):
            print(
                f"Processed {index + 1} / {len(df)}"
            )

    # --------------------------------------------------------
    # Declared allergen comparison
    # --------------------------------------------------------

    exact_metrics = metrics(
        declared_references,
        exact_predictions,
    )

    normalized_metrics = metrics(
        declared_references,
        normalized_predictions,
    )

    proposed_metrics = metrics(
        declared_references,
        proposed_predictions,
    )

    exact_per_allergen = per_allergen_metrics(
        declared_references,
        exact_predictions,
    )

    normalized_per_allergen = per_allergen_metrics(
        declared_references,
        normalized_predictions,
    )

    proposed_per_allergen = per_allergen_metrics(
        declared_references,
        proposed_predictions,
    )

    # --------------------------------------------------------
    # Trace evaluation
    # --------------------------------------------------------

    proposed_trace_metrics = metrics(
        trace_references,
        proposed_trace_predictions,
    )

    proposed_trace_per_allergen = per_allergen_metrics(
        trace_references,
        proposed_trace_predictions,
    )

    results = {
        "evaluation_type": (
            "Held-out declared-allergen baseline comparison "
            "and proposed trace-allergen evaluation"
        ),

        "products_evaluated": len(df),

        "declared_allergen_baselines": {
            "exact_keyword": exact_metrics,
            "normalized_keyword": normalized_metrics,
            "proposed_matcher": proposed_metrics,
        },

        "declared_per_allergen": {
            "exact_keyword": exact_per_allergen,
            "normalized_keyword": normalized_per_allergen,
            "proposed_matcher": proposed_per_allergen,
        },

        "trace_allergen_evaluation": {
            "proposed_matcher": proposed_trace_metrics,
        },

        "trace_per_allergen": {
            "proposed_matcher": proposed_trace_per_allergen,
        },

        "reference_definition": (
            "Open Food Facts declared and trace allergen "
            "annotations are used as reference metadata. "
            "They are not assumed to be absolute ground truth."
        ),

        "methodology_notes": [
            (
                "The three baseline methods are compared "
                "only for declared allergen detection because "
                "the keyword baselines do not distinguish "
                "declared allergens from precautionary traces."
            ),
            (
                "Trace allergen performance is evaluated "
                "separately for the proposed matcher."
            ),
            (
                "All methods were evaluated on the same "
                "300 held-out products."
            ),
            (
                "The proposed matcher was not modified during "
                "this evaluation."
            ),
        ],
    }

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            results,
            f,
            indent=2,
            ensure_ascii=False,
        )

    # --------------------------------------------------------
    # Print
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("DECLARED ALLERGEN BASELINE RESULTS")
    print("=" * 70)

    print()
    print(
        f"{'Method':25s}"
        f"{'Precision':>12s}"
        f"{'Recall':>12s}"
        f"{'F1':>12s}"
        f"{'Exact':>12s}"
    )

    print("-" * 70)

    for name, result in [
        ("Exact keyword", exact_metrics),
        ("Normalized keyword", normalized_metrics),
        ("Proposed matcher", proposed_metrics),
    ]:
        print(
            f"{name:25s}"
            f"{result['precision']:>12.4f}"
            f"{result['recall']:>12.4f}"
            f"{result['f1']:>12.4f}"
            f"{result['exact_match']:>12.4f}"
        )

    print()
    print("PROPOSED MATCHER TRACE RESULTS")
    print("-" * 70)

    print(
        f"Precision: "
        f"{proposed_trace_metrics['precision']:.4f}"
    )

    print(
        f"Recall:    "
        f"{proposed_trace_metrics['recall']:.4f}"
    )

    print(
        f"F1:        "
        f"{proposed_trace_metrics['f1']:.4f}"
    )

    print(
        f"Exact:     "
        f"{proposed_trace_metrics['exact_match']:.4f}"
    )

    print()
    print("PROPOSED MATCHER DECLARED PER-ALLERGEN F1")
    print("-" * 70)

    for allergen in ALLERGENS:
        result = proposed_per_allergen[allergen]

        print(
            f"{allergen:15s}"
            f"F1={result['f1']:.4f} "
            f"Support={result['support']}"
        )

    print()
    print(
        f"Results saved to: {OUTPUT_FILE}"
    )

    print("=" * 70)


if __name__ == "__main__":
    main()