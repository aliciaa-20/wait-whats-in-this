"""
Error analysis for the final OCR benchmark.

Uses data/benchmark/final_ocr_results.csv (produced by
scripts/evaluate_ocr_benchmark.py) to break down:

- Ingredient-section extraction failures
- Worst CER/WER cases (largest OCR text-quality gaps)
- Declared and trace allergen false negatives / false positives,
  per allergen, isolating how many are caused by OCR (present in
  clean-text prediction but not OCR prediction) vs already wrong
  on clean text (matcher-only error)
- Per-target-language summary

The analysis is descriptive. Reference allergen labels are Open
Food Facts metadata, not clinical ground truth; manual_transcription
is genuine human-verified OCR ground truth.
"""

import json
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent
RESULTS_FILE = BASE_DIR / "data" / "benchmark" / "final_ocr_results.csv"
OUTPUT_DIR = BASE_DIR / "data" / "benchmark"

SUMMARY_FILE = OUTPUT_DIR / "final_ocr_error_analysis.json"

ALLERGENS = [
    "milk", "egg", "peanut", "tree_nut", "soy",
    "wheat_gluten", "fish", "shellfish", "sesame",
]


def parse_set(value):
    if pd.isna(value):
        return set()

    value = str(value).strip()

    if not value:
        return set()

    return {item.strip() for item in value.split("|") if item.strip()}


def classify_error(reference, predicted):
    if reference == predicted:
        return "exact_match"
    if reference and not predicted:
        return "false_negative"
    if predicted and not reference:
        return "false_positive"
    if reference & predicted:
        return "partial_match"
    return "true_negative"


def main():

    if not RESULTS_FILE.exists():
        raise FileNotFoundError(
            f"Missing {RESULTS_FILE}. Run "
            "scripts/evaluate_ocr_benchmark.py first."
        )

    df = pd.read_csv(RESULTS_FILE)

    n = len(df)

    print("=" * 70)
    print("FINAL OCR BENCHMARK ERROR ANALYSIS")
    print("=" * 70)
    print(f"Samples analyzed: {n}")

    # ---------------------------------------------------
    # Extraction failures
    # ---------------------------------------------------

    extraction_failures = df[~df["extraction_found"]]

    print()
    print(f"Ingredient-section extraction failures: "
          f"{len(extraction_failures)}/{n}")

    for _, row in extraction_failures.iterrows():
        print(f"  {row['code']} ({row['target_language']}) "
              f"- {row['product_name']}")

    # ---------------------------------------------------
    # Worst CER / WER cases
    # ---------------------------------------------------

    worst_cer = df.sort_values("cer", ascending=False).head(10)
    worst_wer = df.sort_values("wer", ascending=False).head(10)

    print()
    print("Worst 10 by CER:")
    for _, row in worst_cer.iterrows():
        print(f"  {row['code']} ({row['target_language']}) "
              f"CER={row['cer']:.4f} WER={row['wer']:.4f} "
              f"extraction_found={row['extraction_found']}")

    # ---------------------------------------------------
    # Allergen-level error breakdown
    # ---------------------------------------------------

    per_allergen_declared = {}
    per_allergen_trace = {}

    ocr_induced_declared_fn = []
    ocr_induced_trace_fn = []
    ocr_induced_declared_fp = []
    ocr_induced_trace_fp = []

    matcher_only_declared_fn = []
    matcher_only_trace_fn = []

    for _, row in df.iterrows():

        ref_declared = parse_set(row["reference_declared_allergens"])
        ref_trace = parse_set(row["reference_trace_allergens"])

        ocr_declared = parse_set(row["ocr_declared_allergens"])
        ocr_trace = parse_set(row["ocr_trace_allergens"])

        clean_declared = parse_set(row["clean_declared_allergens"])
        clean_trace = parse_set(row["clean_trace_allergens"])

        for allergen in ALLERGENS:

            # Declared, OCR pipeline vs reference
            in_ref = allergen in ref_declared
            in_ocr = allergen in ocr_declared
            in_clean = allergen in clean_declared

            bucket = per_allergen_declared.setdefault(
                allergen,
                {"tp": 0, "fp": 0, "fn": 0, "support": 0},
            )
            if in_ref:
                bucket["support"] += 1
            if in_ref and in_ocr:
                bucket["tp"] += 1
            elif in_ref and not in_ocr:
                bucket["fn"] += 1
                # OCR-induced FN: reference says present, clean-text
                # matcher also finds it (so ground truth text supports
                # it), but OCR text lost it.
                if in_clean:
                    ocr_induced_declared_fn.append(
                        (row["code"], allergen)
                    )
                else:
                    matcher_only_declared_fn.append(
                        (row["code"], allergen)
                    )
            elif not in_ref and in_ocr:
                bucket["fp"] += 1
                if not in_clean:
                    ocr_induced_declared_fp.append(
                        (row["code"], allergen)
                    )

            # Trace, OCR pipeline vs reference
            in_ref_t = allergen in ref_trace
            in_ocr_t = allergen in ocr_trace
            in_clean_t = allergen in clean_trace

            bucket_t = per_allergen_trace.setdefault(
                allergen,
                {"tp": 0, "fp": 0, "fn": 0, "support": 0},
            )
            if in_ref_t:
                bucket_t["support"] += 1
            if in_ref_t and in_ocr_t:
                bucket_t["tp"] += 1
            elif in_ref_t and not in_ocr_t:
                bucket_t["fn"] += 1
                if in_clean_t:
                    ocr_induced_trace_fn.append((row["code"], allergen))
                else:
                    matcher_only_trace_fn.append((row["code"], allergen))
            elif not in_ref_t and in_ocr_t:
                bucket_t["fp"] += 1
                if not in_clean_t:
                    ocr_induced_trace_fp.append((row["code"], allergen))

    print()
    print("DECLARED ALLERGENS - per-allergen (OCR pipeline)")
    print("-" * 70)
    for allergen, b in sorted(
        per_allergen_declared.items(), key=lambda x: -x[1]["support"]
    ):
        if b["support"] == 0 and b["fp"] == 0:
            continue
        print(f"  {allergen:14s} support={b['support']:2d} "
              f"tp={b['tp']:2d} fp={b['fp']:2d} fn={b['fn']:2d}")

    print()
    print("TRACE ALLERGENS - per-allergen (OCR pipeline)")
    print("-" * 70)
    for allergen, b in sorted(
        per_allergen_trace.items(), key=lambda x: -x[1]["support"]
    ):
        if b["support"] == 0 and b["fp"] == 0:
            continue
        print(f"  {allergen:14s} support={b['support']:2d} "
              f"tp={b['tp']:2d} fp={b['fp']:2d} fn={b['fn']:2d}")

    print()
    print("OCR-INDUCED vs MATCHER-ONLY FALSE NEGATIVES")
    print("-" * 70)
    print(f"Declared FN caused by OCR text loss    : "
          f"{len(ocr_induced_declared_fn)}")
    print(f"Declared FN present even on clean text : "
          f"{len(matcher_only_declared_fn)}")
    print(f"Trace FN caused by OCR text loss        : "
          f"{len(ocr_induced_trace_fn)}")
    print(f"Trace FN present even on clean text    : "
          f"{len(matcher_only_trace_fn)}")

    # ---------------------------------------------------
    # Per-language summary
    # ---------------------------------------------------

    per_language = (
        df.groupby("target_language")
        .agg(
            samples=("code", "count"),
            mean_cer=("cer", "mean"),
            mean_wer=("wer", "mean"),
            extraction_rate=("extraction_found", "mean"),
        )
        .round(4)
        .to_dict(orient="index")
    )

    print()
    print("PER TARGET LANGUAGE")
    print("-" * 70)
    for language, stats in sorted(per_language.items()):
        print(f"  {language:4s} {stats}")

    # ---------------------------------------------------
    # Save
    # ---------------------------------------------------

    summary = {
        "samples_analyzed": n,
        "extraction_failures": {
            "count": len(extraction_failures),
            "codes": extraction_failures["code"].tolist(),
        },
        "worst_cer_examples": worst_cer[
            ["code", "target_language", "cer", "wer", "extraction_found"]
        ].to_dict(orient="records"),
        "declared_allergens_per_allergen": per_allergen_declared,
        "trace_allergens_per_allergen": per_allergen_trace,
        "ocr_induced_vs_matcher_only": {
            "declared_fn_caused_by_ocr": len(ocr_induced_declared_fn),
            "declared_fn_present_on_clean_text": len(
                matcher_only_declared_fn
            ),
            "declared_fp_caused_by_ocr": len(ocr_induced_declared_fp),
            "trace_fn_caused_by_ocr": len(ocr_induced_trace_fn),
            "trace_fn_present_on_clean_text": len(matcher_only_trace_fn),
            "trace_fp_caused_by_ocr": len(ocr_induced_trace_fp),
        },
        "per_target_language": per_language,
    }

    with SUMMARY_FILE.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print()
    print(f"Summary saved to: {SUMMARY_FILE}")
    print("=" * 70)


if __name__ == "__main__":
    main()
