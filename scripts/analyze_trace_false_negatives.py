"""
Phase B #3 - trace-recall diagnostic analysis (READ-ONLY).

Purpose: understand *why* trace-allergen recall is low (rule-only matcher:
~0.38-0.41 across every evaluation run to date), not to fix it. This script
does not touch the matcher, the dictionary, the held-out set, or any frozen
research result - it only reads existing evaluation outputs and the raw
ingredient text behind each trace false negative, and buckets each one into
a failure-mode category using the matcher's own trace-detection primitives
(trace_marker_match, split_declared_and_trace_text, dictionary lookups).

Two independent evaluation sources are analyzed:
  1. The 1,263-product OFF-tag evaluation (data/benchmark/matcher_results.csv),
     joined back to data/cleaned_products.csv for raw ingredients_text + lang.
  2. The 300-product manually-annotated held-out set
     (data/research/heldout_predictions.csv), joined to
     data/research/ground_truth.csv for raw reference_ingredients + lang.

Both are read-only. No dictionary term is added, no matcher code path is
changed, and nothing is written back into data/research/heldout_*.

Usage:
    ./venv/bin/python -m scripts.analyze_trace_false_negatives
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

from scripts.allergen_matcher import (
    ALLERGENS,
    load_dictionary,
    normalize_text,
    phrase_in_text,
    trace_marker_match,
    split_declared_and_trace_text,
)

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "data" / "research" / "ml" / "trace_fn_diagnostic_v1"

MATCHER_RESULTS = BASE_DIR / "data" / "benchmark" / "matcher_results.csv"
CLEANED_PRODUCTS = BASE_DIR / "data" / "cleaned_products.csv"

HELDOUT_PREDICTIONS = BASE_DIR / "data" / "research" / "heldout_predictions.csv"
GROUND_TRUTH = BASE_DIR / "data" / "research" / "ground_truth.csv"

# Languages the TRACE_REGEXES list in allergen_matcher.py has explicit
# precautionary-statement phrasing for (en, fr, de, es, pt, nl, no/da/sv, ar).
COVERED_TRACE_LANGS = {"en", "fr", "de", "es", "pt", "nl", "nb", "no", "da", "sv", "ar"}

# Loose, allergen-related surface keywords used ONLY to detect "the concept
# of this allergen is mentioned somewhere nearby" vs "not mentioned at all".
# This is intentionally broader/looser than the production dictionary - it is
# a diagnostic signal, not a proposed addition.
RELATED_KEYWORDS = {
    "milk": ["milk", "lait", "milch", "leche", "leite", "melk", "latte", "dairy", "laiti", "lacteo", "lactos"],
    "egg": ["egg", "oeuf", "ei ", "eier", "huevo", "ovo", "uovo", "ei_"],
    "peanut": ["peanut", "cacahuete", "cacahouet", "arachide", "erdnuss", "amendoim", "arachidi"],
    "tree_nut": ["nut", "noix", "nuss", "fruit a coque", "frutos secos", "noce", "amande", "almond",
                 "hazelnut", "noisette", "haselnuss", "cashew", "pistachio", "pistache", "walnut",
                 "avellana", "nueces", "castanha"],
    "soy": ["soy", "soja", "soya", "sojabohn"],
    "wheat_gluten": ["wheat", "gluten", "ble ", "weizen", "trigo", "grano", "farine", "farina", "mehl"],
    "fish": ["fish", "poisson", "fisch", "pescado", "peixe", "pesce", "salmon", "tuna", "thon", "atun"],
    "shellfish": ["crustace", "shellfish", "crustacean", "mollus", "krebstier", "crustaceo", "marisco",
                   "shrimp", "prawn", "crevette", "gamba"],
    "sesame": ["sesame", "sesamo", "sesam", "susam", "gergelim", "simsim"],
}


def parse_pipe_set(value):
    if pd.isna(value) or not str(value).strip():
        return set()
    return set(p.strip() for p in str(value).split("|") if p.strip())


def parse_commaspace_set(value):
    if pd.isna(value) or not str(value).strip():
        return set()
    return set(p.strip() for p in str(value).split(",") if p.strip())


def keyword_present(text_norm: str, allergen: str) -> bool:
    return any(kw in text_norm for kw in RELATED_KEYWORDS.get(allergen, []))


def loose_trace_phrase_present(text_norm: str) -> bool:
    """
    Looser-than-regex check for "some precautionary-style wording is
    probably here" - used to separate "marker regex is too narrow / missed
    a variant" from "there is genuinely no precautionary statement in this
    text at all".
    """
    loose_markers = [
        "may contain", "trace", "peut contenir", "kann", "spuren",
        "puede contener", "traza", "pode conter", "vestigio", "traco",
        "kan bevatten", "spoor", "kan inneholde", "spor",
        "قد يحتوي",  # qad yahtawi (may contain, ar)
        "آثار",  # athar (traces, ar)
    ]
    return any(m in text_norm for m in loose_markers)


def categorize(text: str, allergen: str, lang: str, dictionary) -> tuple[str, dict]:
    """
    Returns (category, debug_info) for one (product, missed trace allergen)
    false negative.
    """
    text = text or ""
    text_norm = normalize_text(text)
    marker = trace_marker_match(text)

    info = {"lang": lang, "has_marker": marker is not None}

    if marker is None:
        # No recognized precautionary phrase anywhere -> whole text is
        # treated as "declared" and the trace section is empty. Split into
        # two sub-cases based on whether *some* precautionary-style wording
        # is present but just outside our regex list (a real detection
        # gap) vs. no such wording exists in the text at all (the
        # reference tag has no textual counterpart to find).
        if loose_trace_phrase_present(text_norm):
            return "trace_marker_detection_gap", info
        if keyword_present(text_norm, allergen):
            # Allergen is mentioned, but nowhere near any precautionary
            # phrasing - most often it's actually a declared/negated
            # mention, or the OFF trace tag has no textual basis at all.
            return "off_reference_label_limitation", info
        return "off_reference_label_limitation", info

    # A trace marker WAS found - see what happened inside the split trace
    # section.
    declared_text, trace_text = split_declared_and_trace_text(text)
    trace_norm = normalize_text(trace_text)
    info["trace_text"] = trace_text[:200]

    terms = dictionary.get(allergen, set())
    literal_hit = any(phrase_in_text(t, trace_text) for t in terms)

    if literal_hit:
        # The correct dictionary term IS present in the trace section, yet
        # this was still scored a false negative - almost always a
        # negation/validity-filter edge case in matcher logic, not a
        # vocabulary or splitting problem.
        return "matcher_logic_edge_case", info

    if keyword_present(trace_norm, allergen):
        return "ontology_dictionary_gap", info

    if keyword_present(normalize_text(text), allergen):
        # Allergen keyword exists in the product's text but landed on the
        # DECLARED side of the split, not the trace side - a
        # section-splitting/context problem, not a vocabulary problem.
        return "section_splitting_context_gap", info

    return "off_reference_label_limitation", info


def build_matcher_1263_fn_records():
    if not MATCHER_RESULTS.exists():
        return []
    results = pd.read_csv(MATCHER_RESULTS, dtype={"code": str})
    products = pd.read_csv(CLEANED_PRODUCTS, dtype={"code": str})[
        ["code", "ingredients_text", "lang"]
    ]
    merged = results.merge(products, on="code", how="left")

    records = []
    for _, row in merged.iterrows():
        ref = parse_pipe_set(row.get("reference_traces"))
        pred = parse_pipe_set(row.get("predicted_traces"))
        missed = ref - pred
        for allergen in missed:
            records.append(
                {
                    "source": "1263_off_tag_eval",
                    "code": row["code"],
                    "product_name": row.get("product_name", ""),
                    "allergen": allergen,
                    "lang": row.get("lang", ""),
                    "text": row.get("ingredients_text", ""),
                }
            )
    return records


def build_heldout_300_fn_records():
    if not HELDOUT_PREDICTIONS.exists():
        return []
    preds = pd.read_csv(HELDOUT_PREDICTIONS, dtype={"code": str})
    gt = pd.read_csv(GROUND_TRUTH, dtype={"code": str})[
        ["code", "reference_ingredients", "lang", "notes", "evidence"]
    ]
    merged = preds.merge(gt, on="code", how="left", suffixes=("", "_gt"))

    records = []
    for _, row in merged.iterrows():
        ref = parse_commaspace_set(row.get("reference_trace"))
        pred = parse_commaspace_set(row.get("predicted_trace"))
        missed = ref - pred
        text = row.get("reference_ingredients", "")
        for allergen in missed:
            records.append(
                {
                    "source": "300_heldout_manual_eval",
                    "code": row["code"],
                    "product_name": row.get("product_name", ""),
                    "allergen": allergen,
                    "lang": row.get("lang", ""),
                    "text": text,
                    "notes": row.get("notes", ""),
                }
            )
    return records


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    dictionary = load_dictionary()

    fn_1263 = build_matcher_1263_fn_records()
    fn_300 = build_heldout_300_fn_records()

    print(f"Trace false negatives in 1,263-product OFF-tag eval: {len(fn_1263)}")
    print(f"Trace false negatives in 300-product held-out eval:  {len(fn_300)}")

    all_records = fn_1263 + fn_300
    for rec in all_records:
        category, info = categorize(rec["text"], rec["allergen"], rec.get("lang", ""), dictionary)
        rec["category"] = category
        rec["multilingual_uncovered"] = str(rec.get("lang", "")).lower() not in COVERED_TRACE_LANGS

    # ---- Aggregate ----
    def summarize(records, label):
        n = len(records)
        cat_counts = Counter(r["category"] for r in records)
        allergen_counts = Counter(r["allergen"] for r in records)
        multilingual_n = sum(1 for r in records if r["multilingual_uncovered"])
        lang_counts = Counter(str(r.get("lang", "")) for r in records)

        by_category_allergen = defaultdict(Counter)
        for r in records:
            by_category_allergen[r["category"]][r["allergen"]] += 1

        examples_by_category = defaultdict(list)
        for r in records:
            if len(examples_by_category[r["category"]]) < 4:
                examples_by_category[r["category"]].append(
                    {
                        "code": r["code"],
                        "product_name": r.get("product_name", ""),
                        "allergen": r["allergen"],
                        "lang": r.get("lang", ""),
                        "text_excerpt": str(r.get("text", ""))[:220],
                    }
                )

        return {
            "source": label,
            "total_trace_false_negatives": n,
            "category_counts": dict(cat_counts),
            "category_percentages": {
                k: round(100 * v / n, 1) for k, v in cat_counts.items()
            } if n else {},
            "allergen_counts": dict(allergen_counts),
            "language_counts": dict(lang_counts),
            "multilingual_uncovered_lang_count": multilingual_n,
            "multilingual_uncovered_lang_pct": round(100 * multilingual_n / n, 1) if n else 0,
            "category_by_allergen": {k: dict(v) for k, v in by_category_allergen.items()},
            "representative_examples": dict(examples_by_category),
        }

    summary_1263 = summarize(fn_1263, "1263_off_tag_eval")
    summary_300 = summarize(fn_300, "300_heldout_manual_eval")
    summary_combined = summarize(all_records, "combined")

    result = {
        "diagnostic_type": "trace_recall_false_negative_categorization",
        "not_a_model_change": True,
        "held_out_300_touched_for_tuning": False,
        "dictionary_touched": False,
        "matcher_touched": False,
        "sources": {
            "1263_off_tag_eval": str(MATCHER_RESULTS.relative_to(BASE_DIR)),
            "300_heldout_manual_eval": str(HELDOUT_PREDICTIONS.relative_to(BASE_DIR)),
        },
        "by_source": {
            "1263_off_tag_eval": summary_1263,
            "300_heldout_manual_eval": summary_300,
        },
        "combined": summary_combined,
    }

    out_file = OUTPUT_DIR / "trace_fn_categorization.json"
    with out_file.open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    # Also dump the raw per-record table for further manual inspection.
    raw_df = pd.DataFrame(all_records)
    raw_df.to_csv(OUTPUT_DIR / "trace_fn_raw_records.csv", index=False)

    print("\n=== COMBINED CATEGORY BREAKDOWN ===")
    for cat, pct in sorted(summary_combined["category_percentages"].items(), key=lambda x: -x[1]):
        print(f"  {cat:35s} {summary_combined['category_counts'][cat]:4d}  ({pct}%)")
    print(f"\n  multilingual (lang without explicit trace-phrase coverage): "
          f"{summary_combined['multilingual_uncovered_lang_count']} "
          f"({summary_combined['multilingual_uncovered_lang_pct']}%)")

    print(f"\nFull results: {out_file}")
    print(f"Raw records:  {OUTPUT_DIR / 'trace_fn_raw_records.csv'}")


if __name__ == "__main__":
    main()
