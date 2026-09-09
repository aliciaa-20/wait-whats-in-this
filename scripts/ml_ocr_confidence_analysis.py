"""
Phase 5 of the approved ML extension: does ocr_confidence (already
computed by scripts/ocr_processor.py, currently unused downstream)
actually correlate with OCR text quality (CER)?

Decision gate per ML_EXTENSION_PLAN.md: only wire ocr_confidence into
downstream confidence-aware flagging (Phase 4) if this analysis
supports it. No new OCR runs - reuses the already-collected 39-image
benchmark results (data/benchmark/final_ocr_results.csv), which is
untouched by this script (read-only).

Usage:
    ./venv/bin/python -m scripts.ml_ocr_confidence_analysis
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats


BASE_DIR = Path(__file__).resolve().parent.parent
RESULTS_FILE = BASE_DIR / "data" / "benchmark" / "final_ocr_results.csv"
OUTPUT_DIR = BASE_DIR / "data" / "research" / "ml" / "ocr_confidence_analysis_v1"


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not RESULTS_FILE.exists():
        raise FileNotFoundError(
            f"Missing {RESULTS_FILE}. This reuses the existing frozen "
            "39-image OCR benchmark results - run "
            "scripts/evaluate_ocr_benchmark.py first if it's missing."
        )

    df = pd.read_csv(RESULTS_FILE, dtype={"code": str})
    n = len(df)
    print(f"Loaded {n} rows from the frozen 39-image OCR benchmark (read-only).")

    confidence = df["ocr_confidence"].to_numpy()
    cer = df["cer"].to_numpy()
    extraction_found = df["extraction_found"].to_numpy()

    pearson_r, pearson_p = stats.pearsonr(confidence, cer)
    spearman_r, spearman_p = stats.spearmanr(confidence, cer)

    print(f"\nPearson  r={pearson_r:.4f}  p={pearson_p:.4f}")
    print(f"Spearman r={spearman_r:.4f}  p={spearman_p:.4f}")
    print("(negative r is the expected direction: higher OCR confidence -> lower CER)")

    # Split by extraction outcome too - does confidence differ between
    # rows where section extraction succeeded vs. failed?
    conf_found = df.loc[df["extraction_found"], "ocr_confidence"]
    conf_not_found = df.loc[~df["extraction_found"], "ocr_confidence"]

    print(f"\nMean ocr_confidence, extraction succeeded (n={len(conf_found)}): {conf_found.mean():.4f}")
    print(f"Mean ocr_confidence, extraction failed    (n={len(conf_not_found)}): {conf_not_found.mean():.4f}")

    mannwhitney_stat, mannwhitney_p = stats.mannwhitneyu(
        conf_found, conf_not_found, alternative="greater"
    )
    print(f"Mann-Whitney U (confidence higher when extraction succeeds): "
          f"p={mannwhitney_p:.4f}")

    # --- Threshold check: at what confidence cutoff would flagging
    # actually separate high-CER from low-CER rows? ---
    threshold_grid = [0.3, 0.4, 0.5, 0.6, 0.7]
    threshold_analysis = []
    for t in threshold_grid:
        below = df[df["ocr_confidence"] < t]
        above = df[df["ocr_confidence"] >= t]
        threshold_analysis.append({
            "threshold": t,
            "n_below": len(below),
            "mean_cer_below": round(float(below["cer"].mean()), 4) if len(below) else None,
            "n_above": len(above),
            "mean_cer_above": round(float(above["cer"].mean()), 4) if len(above) else None,
        })
        print(f"  threshold={t}: below(n={len(below)}, mean CER={below['cer'].mean() if len(below) else float('nan'):.4f}) "
              f"vs above(n={len(above)}, mean CER={above['cer'].mean() if len(above) else float('nan'):.4f})")

    # --- Decision ---
    # A meaningful, statistically supported negative correlation, AND a
    # confidence gap between successful/failed extraction, is the bar
    # for "the data supports wiring this into downstream flagging."
    correlation_supports = pearson_r < -0.2 and pearson_p < 0.05
    separation_supports = mannwhitney_p < 0.05

    decision = correlation_supports and separation_supports

    print()
    print("=" * 70)
    print(f"DECISION: {'WIRE UP OCR-CONFIDENCE FLAGGING' if decision else 'DO NOT WIRE UP — insufficient support in the data'}")
    print("=" * 70)
    print(f"Correlation supports it (r < -0.2, p < 0.05): {correlation_supports} (r={pearson_r:.4f}, p={pearson_p:.4f})")
    print(f"Confidence separates success/failure (p < 0.05): {separation_supports} (p={mannwhitney_p:.4f})")

    result = {
        "n_samples": n,
        "note": "Analysis of the existing frozen 39-image OCR benchmark. Read-only - no OCR re-run, no benchmark file modified.",
        "pearson": {"r": round(float(pearson_r), 4), "p": round(float(pearson_p), 4)},
        "spearman": {"r": round(float(spearman_r), 4), "p": round(float(spearman_p), 4)},
        "confidence_by_extraction_outcome": {
            "mean_confidence_extraction_succeeded": round(float(conf_found.mean()), 4),
            "mean_confidence_extraction_failed": round(float(conf_not_found.mean()), 4),
            "mannwhitney_p": round(float(mannwhitney_p), 4),
        },
        "threshold_analysis": threshold_analysis,
        "decision": {
            "wire_up_ocr_confidence_flagging": bool(decision),
            "correlation_supports": bool(correlation_supports),
            "separation_supports": bool(separation_supports),
        },
    }

    with (OUTPUT_DIR / "correlation_analysis.json").open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(f"\nSaved to: {OUTPUT_DIR / 'correlation_analysis.json'}")

    return decision


if __name__ == "__main__":
    main()
