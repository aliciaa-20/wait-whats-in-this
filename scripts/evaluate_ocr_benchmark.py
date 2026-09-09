"""
Final OCR research evaluation.

Runs the real OCR pipeline (EasyOCR + preprocessing) over the 40
manually-verified images in the controlled 50-image benchmark, and
scores it against actual human transcription - not Open Food Facts
metadata, which is not guaranteed to match what is visibly printed
on the image (see scripts/download_ocr_benchmark_final.py).

For each completed row (annotation_status == "complete") this
measures:

1. OCR text quality: CER / WER against the manual transcription.
2. Ingredient-section extraction: did the pipeline find the section
   at all, given that a human confirmed it exists in every one of
   these images.
3. Allergen detection, computed TWICE so OCR-induced degradation is
   isolated from matcher-only error:
     - "ocr":   matcher run on the OCR-extracted text
     - "clean": matcher run on the manual transcription itself
   Both are scored against the same reference allergen labels (the
   declared_allergens / trace_allergens columns carried over from
   Open Food Facts during benchmark selection - reference metadata,
   not clinical ground truth, exactly as in the text-only
   benchmarks).
4. End-to-end risk classification accuracy (AVOID/CAUTION/SAFE),
   for both "ocr" and "clean" predictions.
5. A per-target-language breakdown, since this benchmark's whole
   point is controlled language coverage.

The 10 rows left annotation_status == "incomplete" (blurry, cropped,
or otherwise not legitimately transcribable) are excluded from
scoring - they were never meant to produce ground truth.

This script only reads data/benchmark/final_benchmark_metadata.csv
and images under data/benchmark/final_images/. It does not modify
the matcher, the OCR pipeline, the 300-product held-out evaluation,
or the smoke-test benchmark (data/benchmark/metadata.csv /
benchmark_ocr.py), which remain untouched.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from scripts.ocr_processor import process_image
from scripts.allergen_matcher import (
    load_dictionary,
    analyze_ingredient_text,
)
from scripts.benchmark_ocr import (
    character_error_rate,
    word_error_rate,
    multilabel_metrics,
    exact_set_agreement,
    risk_from_sets,
)


BASE_DIR = Path(__file__).resolve().parents[1]
BENCHMARK_DIR = BASE_DIR / "data" / "benchmark"

METADATA_FILE = BENCHMARK_DIR / "final_benchmark_metadata.csv"
RESULTS_FILE = BENCHMARK_DIR / "final_ocr_results.csv"
SUMMARY_FILE = BENCHMARK_DIR / "final_ocr_summary.json"


def parse_allergen_set(value) -> set[str]:
    """
    Parse the project-format pipe-separated allergen id columns
    already present in final_benchmark_metadata.csv
    (declared_allergens / trace_allergens), e.g. "milk|soy".

    Unlike scripts/benchmark_ocr.py's parse_tags(), no OFF-tag
    mapping is needed here - these columns were already converted
    to project allergen ids during benchmark selection.
    """

    if value is None:
        return set()

    try:
        if pd.isna(value):
            return set()
    except (TypeError, ValueError):
        pass

    text = str(value).strip()

    if not text:
        return set()

    return {
        item.strip()
        for item in text.split("|")
        if item.strip()
    }


def risk_accuracy(reference_risks, predicted_risks) -> dict:
    total = len(reference_risks)

    if total == 0:
        return {"accuracy": 0.0, "correct": 0, "total": 0}

    correct = sum(
        r == p for r, p in zip(reference_risks, predicted_risks)
    )

    return {
        "accuracy": correct / total,
        "correct": correct,
        "total": total,
    }


def main():

    if not METADATA_FILE.exists():
        raise FileNotFoundError(
            f"Missing {METADATA_FILE}. Run "
            "scripts/download_ocr_benchmark_final.py and complete "
            "annotation with scripts/annotate_ocr_benchmark.py first."
        )

    metadata = pd.read_csv(METADATA_FILE, dtype=str, keep_default_na=False)

    completed = metadata[
        metadata["annotation_status"] == "complete"
    ].reset_index(drop=True)

    skipped = len(metadata) - len(completed)

    dictionary = load_dictionary()

    results = []

    reference_allergens = []
    ocr_pred_allergens = []
    clean_pred_allergens = []

    reference_traces = []
    ocr_pred_traces = []
    clean_pred_traces = []

    reference_risks = []
    ocr_pred_risks = []
    clean_pred_risks = []

    extraction_successes = []

    print("=" * 70)
    print("FINAL OCR BENCHMARK EVALUATION")
    print("=" * 70)
    print(f"Total candidates       : {len(metadata)}")
    print(f"Manually verified (used): {len(completed)}")
    print(f"Excluded (incomplete)  : {skipped}")

    for index, row in completed.iterrows():

        code = row["code"]
        target_language = (row["target_language"] or "en").strip().lower()
        image_path = BENCHMARK_DIR / row["image_path"]

        print(f"\n[{index + 1}/{len(completed)}] {code} "
              f"(target_language={target_language})...")

        # ------------------------------------------------
        # OCR
        # ------------------------------------------------

        try:
            output = process_image(image_path, language=target_language)
            ocr_text = output.get("ingredient_text", "") or ""
            extraction_found = bool(
                output.get("ingredient_section_found", False)
            )
            confidence = float(output.get("ocr_confidence", 0.0))
        except Exception as exc:
            print(f"  OCR ERROR: {exc}")
            ocr_text = ""
            extraction_found = False
            confidence = 0.0

        # ------------------------------------------------
        # Ground truth (human transcription) and reference
        # allergen labels (Open Food Facts metadata, carried
        # over during benchmark selection)
        # ------------------------------------------------

        reference_text = row["manual_transcription"]

        ref_declared = parse_allergen_set(row["declared_allergens"])
        ref_trace = parse_allergen_set(row["trace_allergens"])

        # ------------------------------------------------
        # OCR-text-based allergen analysis (the real pipeline)
        # ------------------------------------------------

        if ocr_text.strip():
            try:
                ocr_analysis = analyze_ingredient_text(
                    ocr_text, dictionary
                )
                ocr_declared = set(ocr_analysis["declared_allergens"])
                ocr_trace = set(ocr_analysis["trace_allergens"])
                ocr_risk = ocr_analysis["risk"]
            except Exception as exc:
                print(f"  Matcher ERROR (OCR text): {exc}")
                ocr_declared, ocr_trace, ocr_risk = set(), set(), "UNKNOWN"
        else:
            ocr_declared, ocr_trace, ocr_risk = set(), set(), "UNKNOWN"

        # ------------------------------------------------
        # Clean-text-based allergen analysis (matcher-only
        # upper bound, given the manually verified text) -
        # isolates OCR-induced degradation from matcher error.
        # ------------------------------------------------

        clean_analysis = analyze_ingredient_text(
            reference_text, dictionary
        )
        clean_declared = set(clean_analysis["declared_allergens"])
        clean_trace = set(clean_analysis["trace_allergens"])
        clean_risk = clean_analysis["risk"]

        # ------------------------------------------------
        # OCR text-quality metrics
        # ------------------------------------------------

        cer = character_error_rate(reference_text, ocr_text)
        wer = word_error_rate(reference_text, ocr_text)

        reference_risk = risk_from_sets(ref_declared, ref_trace)

        results.append({
            "code": code,
            "product_name": row["product_name"],
            "target_language": target_language,
            "image_path": row["image_path"],
            "ocr_confidence": confidence,
            "manual_transcription": reference_text,
            "ocr_text": ocr_text,
            "cer": cer,
            "wer": wer,
            "extraction_found": extraction_found,
            "reference_declared_allergens": "|".join(sorted(ref_declared)),
            "reference_trace_allergens": "|".join(sorted(ref_trace)),
            "ocr_declared_allergens": "|".join(sorted(ocr_declared)),
            "ocr_trace_allergens": "|".join(sorted(ocr_trace)),
            "clean_declared_allergens": "|".join(sorted(clean_declared)),
            "clean_trace_allergens": "|".join(sorted(clean_trace)),
            "reference_risk": reference_risk,
            "ocr_risk": ocr_risk,
            "clean_risk": clean_risk,
        })

        reference_allergens.append(ref_declared)
        ocr_pred_allergens.append(ocr_declared)
        clean_pred_allergens.append(clean_declared)

        reference_traces.append(ref_trace)
        ocr_pred_traces.append(ocr_trace)
        clean_pred_traces.append(clean_trace)

        reference_risks.append(reference_risk)
        ocr_pred_risks.append(ocr_risk)
        clean_pred_risks.append(clean_risk)

        extraction_successes.append(extraction_found)

        print(f"  CER={cer:.4f} WER={wer:.4f} "
              f"extraction_found={extraction_found}")

    # =====================================================
    # AGGREGATE METRICS
    # =====================================================

    n = len(results)

    ocr_allergen_metrics = multilabel_metrics(
        reference_allergens, ocr_pred_allergens
    )
    clean_allergen_metrics = multilabel_metrics(
        reference_allergens, clean_pred_allergens
    )

    ocr_trace_metrics = multilabel_metrics(
        reference_traces, ocr_pred_traces
    )
    clean_trace_metrics = multilabel_metrics(
        reference_traces, clean_pred_traces
    )

    ocr_allergen_exact = exact_set_agreement(
        reference_allergens, ocr_pred_allergens
    )
    clean_allergen_exact = exact_set_agreement(
        reference_allergens, clean_pred_allergens
    )

    ocr_trace_exact = exact_set_agreement(
        reference_traces, ocr_pred_traces
    )
    clean_trace_exact = exact_set_agreement(
        reference_traces, clean_pred_traces
    )

    ocr_risk_acc = risk_accuracy(reference_risks, ocr_pred_risks)
    clean_risk_acc = risk_accuracy(reference_risks, clean_pred_risks)

    mean_cer = sum(r["cer"] for r in results) / n if n else 0.0
    mean_wer = sum(r["wer"] for r in results) / n if n else 0.0
    mean_confidence = (
        sum(r["ocr_confidence"] for r in results) / n if n else 0.0
    )
    extraction_rate = (
        sum(extraction_successes) / n if n else 0.0
    )

    # ---------------------------------------------------
    # Per-target-language breakdown
    # ---------------------------------------------------

    per_language = {}

    for language in sorted(set(r["target_language"] for r in results)):
        subset = [r for r in results if r["target_language"] == language]
        m = len(subset)
        per_language[language] = {
            "samples": m,
            "mean_cer": sum(r["cer"] for r in subset) / m,
            "mean_wer": sum(r["wer"] for r in subset) / m,
            "extraction_rate": (
                sum(r["extraction_found"] for r in subset) / m
            ),
        }

    summary = {
        "evaluation_type": (
            "Final controlled OCR benchmark - image-to-risk pipeline "
            "evaluated against manually verified ground truth"
        ),
        "samples_total_candidates": len(metadata),
        "samples_evaluated": n,
        "samples_excluded_incomplete": skipped,
        "excluded_note": (
            "Excluded rows are images marked incomplete during manual "
            "annotation (blurry, cropped, or otherwise not legitimately "
            "transcribable) - they were never treated as ground truth."
        ),
        "ocr_text_quality": {
            "mean_ocr_confidence": mean_confidence,
            "mean_cer": mean_cer,
            "mean_wer": mean_wer,
            "ingredient_section_extraction_rate": extraction_rate,
        },
        "declared_allergens": {
            "ocr_pipeline": {
                "precision": ocr_allergen_metrics["precision"],
                "recall": ocr_allergen_metrics["recall"],
                "f1": ocr_allergen_metrics["f1"],
                "exact_set_agreement": ocr_allergen_exact,
                "true_positive": ocr_allergen_metrics["true_positive"],
                "false_positive": ocr_allergen_metrics["false_positive"],
                "false_negative": ocr_allergen_metrics["false_negative"],
            },
            "clean_text_upper_bound": {
                "precision": clean_allergen_metrics["precision"],
                "recall": clean_allergen_metrics["recall"],
                "f1": clean_allergen_metrics["f1"],
                "exact_set_agreement": clean_allergen_exact,
                "true_positive": clean_allergen_metrics["true_positive"],
                "false_positive": clean_allergen_metrics["false_positive"],
                "false_negative": clean_allergen_metrics["false_negative"],
            },
        },
        "trace_allergens": {
            "ocr_pipeline": {
                "precision": ocr_trace_metrics["precision"],
                "recall": ocr_trace_metrics["recall"],
                "f1": ocr_trace_metrics["f1"],
                "exact_set_agreement": ocr_trace_exact,
                "true_positive": ocr_trace_metrics["true_positive"],
                "false_positive": ocr_trace_metrics["false_positive"],
                "false_negative": ocr_trace_metrics["false_negative"],
            },
            "clean_text_upper_bound": {
                "precision": clean_trace_metrics["precision"],
                "recall": clean_trace_metrics["recall"],
                "f1": clean_trace_metrics["f1"],
                "exact_set_agreement": clean_trace_exact,
                "true_positive": clean_trace_metrics["true_positive"],
                "false_positive": clean_trace_metrics["false_positive"],
                "false_negative": clean_trace_metrics["false_negative"],
            },
        },
        "risk_classification": {
            "ocr_pipeline_accuracy": ocr_risk_acc,
            "clean_text_upper_bound_accuracy": clean_risk_acc,
        },
        "per_target_language": per_language,
        "reference_note": (
            "declared_allergens/trace_allergens reference labels are "
            "Open Food Facts metadata carried over during benchmark "
            "selection - reference metadata, not clinical ground "
            "truth. manual_transcription IS the OCR ground truth "
            "(human-verified against the actual image)."
        ),
    }

    # =====================================================
    # SAVE
    # =====================================================

    BENCHMARK_DIR.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(results).to_csv(RESULTS_FILE, index=False)

    with SUMMARY_FILE.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    # =====================================================
    # PRINT
    # =====================================================

    print()
    print("=" * 70)
    print("RESULTS")
    print("=" * 70)
    print(f"Samples evaluated : {n}")
    print(f"Mean CER          : {mean_cer:.4f}")
    print(f"Mean WER          : {mean_wer:.4f}")
    print(f"Extraction rate   : {extraction_rate:.4f}")

    print()
    print("DECLARED ALLERGENS (OCR pipeline vs clean-text upper bound)")
    print("-" * 70)
    print(f"OCR   P={ocr_allergen_metrics['precision']:.4f} "
          f"R={ocr_allergen_metrics['recall']:.4f} "
          f"F1={ocr_allergen_metrics['f1']:.4f} "
          f"Exact={ocr_allergen_exact:.4f}")
    print(f"Clean P={clean_allergen_metrics['precision']:.4f} "
          f"R={clean_allergen_metrics['recall']:.4f} "
          f"F1={clean_allergen_metrics['f1']:.4f} "
          f"Exact={clean_allergen_exact:.4f}")

    print()
    print("TRACE ALLERGENS (OCR pipeline vs clean-text upper bound)")
    print("-" * 70)
    print(f"OCR   P={ocr_trace_metrics['precision']:.4f} "
          f"R={ocr_trace_metrics['recall']:.4f} "
          f"F1={ocr_trace_metrics['f1']:.4f} "
          f"Exact={ocr_trace_exact:.4f}")
    print(f"Clean P={clean_trace_metrics['precision']:.4f} "
          f"R={clean_trace_metrics['recall']:.4f} "
          f"F1={clean_trace_metrics['f1']:.4f} "
          f"Exact={clean_trace_exact:.4f}")

    print()
    print("RISK CLASSIFICATION ACCURACY")
    print("-" * 70)
    print(f"OCR pipeline : {ocr_risk_acc['accuracy']:.4f} "
          f"({ocr_risk_acc['correct']}/{ocr_risk_acc['total']})")
    print(f"Clean text   : {clean_risk_acc['accuracy']:.4f} "
          f"({clean_risk_acc['correct']}/{clean_risk_acc['total']})")

    print()
    print("PER TARGET LANGUAGE")
    print("-" * 70)
    for language, stats in sorted(per_language.items()):
        print(f"{language:4s} n={stats['samples']:2d} "
              f"CER={stats['mean_cer']:.4f} "
              f"WER={stats['mean_wer']:.4f} "
              f"extraction={stats['extraction_rate']:.4f}")

    print()
    print(f"Results saved to : {RESULTS_FILE}")
    print(f"Summary saved to : {SUMMARY_FILE}")
    print("=" * 70)


if __name__ == "__main__":
    main()
