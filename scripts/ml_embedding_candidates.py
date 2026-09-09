"""
Phase 2 of the approved ML extension: embedding-based candidate
generation for allergen mentions the exact/fuzzy dictionary matcher
misses.

Frozen multilingual sentence embeddings (sentence-transformers/
paraphrase-multilingual-MiniLM-L12-v2), used zero-shot - no training,
no fine-tuning. The dictionary's own synonym terms ARE the reference
set; nothing new is learned from the dataset.

Safety design (per ML_EXTENSION_PLAN.md / approved architecture):
- Embeddings only ever ADD candidate allergens the exact matcher did not
  already find - they never override or remove an exact match.
- Every candidate is routed through the SAME unmodified negation
  (is_negated) and context-exclusion (_is_valid_match) checks that
  exact matches already go through. Embeddings never decide risk
  directly.
- allergen_matcher.py is not modified. This script imports it read-only.

Threshold selection uses ONLY the 963-product leak-free dev set (see
scripts/ml_trace_classifier.py for how that set was derived and why).
The 300-product held-out set is never read by this script.

Usage:
    ./venv/bin/python -m scripts.ml_embedding_candidates
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.metrics import precision_recall_fscore_support

from scripts.allergen_matcher import (
    ALLERGENS,
    load_dictionary,
    normalize_text,
    split_declared_and_trace_text,
    detect_allergen_matches,
    is_negated,
    _is_valid_match,
)


BASE_DIR = Path(__file__).resolve().parent.parent
DATASET_FILE = BASE_DIR / "data" / "cleaned_products.csv"
HELDOUT_FILE = BASE_DIR / "data" / "research" / "ground_truth.csv"

OUTPUT_DIR = BASE_DIR / "data" / "research" / "ml" / "embedding_candidates_v1"

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# Candidate thresholds to sweep on the dev set - chosen only, never
# tuned against the held-out set.
THRESHOLD_GRID = [0.60, 0.65, 0.70, 0.75, 0.80, 0.85]


# ============================================================
# DATA (mirrors ml_trace_classifier.py's leak-free dev set exactly)
# ============================================================

def load_leak_free_dev_set() -> pd.DataFrame:
    df = pd.read_csv(DATASET_FILE, dtype={"code": str})
    heldout = pd.read_csv(HELDOUT_FILE, dtype={"code": str})
    heldout_codes = set(heldout["code"])

    df["ingredients_text"] = df["ingredients_text"].fillna("").astype(str)
    df = df[df["ingredients_text"].str.strip() != ""].copy()
    df = df[~df["code"].isin(heldout_codes)].copy()

    return df.reset_index(drop=True)


TAG_TO_ALLERGEN = {
    "en:milk": "milk", "en:eggs": "egg", "en:peanuts": "peanut",
    "en:nuts": "tree_nut", "en:soybeans": "soy", "en:gluten": "wheat_gluten",
    "en:wheat": "wheat_gluten", "en:fish": "fish",
    "en:crustaceans": "shellfish", "en:molluscs": "shellfish",
    "en:sesame-seeds": "sesame",
}


def parse_tags(value):
    if pd.isna(value):
        return set()
    text = str(value).strip().strip("[]")
    if not text:
        return set()
    result = set()
    for part in re.split(r"[,|;]", text):
        tag = part.strip().strip("'\"").lower()
        if tag in TAG_TO_ALLERGEN:
            result.add(TAG_TO_ALLERGEN[tag])
    return result


MIN_PHRASE_WORDS = 2


def split_ingredient_phrases(text: str) -> list[str]:
    """
    Ingredient lists are comma-separated by convention - this is the
    natural unit for candidate generation, unlike the clause-level split
    used for trace/declared classification.

    Restricted to multi-word phrases (>= 2 words): single short words
    (e.g. "sel", "amidon") produce unreliable embeddings with this model
    - cosine similarity between unrelated short tokens routinely exceeds
    0.85, which single-handedly broke candidate generation in initial
    testing (see threshold_sweep.json for the false-positive evidence).
    Single-word ingredients are also exactly where the existing exact/
    fuzzy dictionary matcher already performs best, so this costs little
    real recall potential - the exercise here is candidates the exact
    matcher misses, which skew toward multi-word compound/derivative
    phrasing anyway.
    """
    if not text:
        return []
    phrases = re.split(r"[,;]", text)
    return [
        p.strip() for p in phrases
        if len(p.strip()) >= 3 and len(p.strip().split()) >= MIN_PHRASE_WORDS
    ]


# ============================================================
# EMBEDDING INDEX OVER THE DICTIONARY
# ============================================================

def build_dictionary_embedding_index(model, dictionary):
    """Returns (terms: list[str], allergens: list[str], embeddings: np.ndarray)
    - one row per dictionary synonym term, tagged with its allergen."""

    terms = []
    allergens = []

    for allergen in ALLERGENS:
        for term in sorted(dictionary.get(allergen, set())):
            if len(term) < 3:  # skip near-empty/too-generic terms
                continue
            terms.append(term)
            allergens.append(allergen)

    embeddings = model.encode(terms, normalize_embeddings=True, show_progress_bar=False)

    return terms, allergens, embeddings


def best_candidate_per_allergen(phrase_embedding, dict_terms, dict_allergens, dict_embeddings):
    """Cosine similarity (embeddings are pre-normalized, so dot product
    suffices) between one phrase and every dictionary term; returns the
    best (allergen, term, similarity) per allergen."""

    sims = dict_embeddings @ phrase_embedding

    best = {}
    for term, allergen, sim in zip(dict_terms, dict_allergens, sims):
        if allergen not in best or sim > best[allergen][1]:
            best[allergen] = (term, float(sim))

    return best


# ============================================================
# CANDIDATE GENERATION + SAFETY-GATED VERIFICATION
#
# Split into an embedding step (expensive, threshold-independent, run
# ONCE) and a decision step (cheap, run once per swept threshold) so a
# multi-threshold sweep doesn't re-embed the same phrases repeatedly.
# ============================================================

def embed_section(text_section, model, dict_terms, dict_allergens, dict_embeddings):
    """One-time embedding + best-match lookup for a text section.
    Returns a list of (phrase, normalized_section, best_per_allergen)
    that decide_candidates() can reuse across every threshold."""

    phrases = split_ingredient_phrases(text_section)
    if not phrases:
        return []

    normalized_phrases = [normalize_text(p) for p in phrases]
    phrase_embeddings = model.encode(
        normalized_phrases, normalize_embeddings=True, show_progress_bar=False
    )
    normalized_section = normalize_text(text_section)

    prepared = []
    for phrase, phrase_emb in zip(phrases, phrase_embeddings):
        best = best_candidate_per_allergen(
            phrase_emb, dict_terms, dict_allergens, dict_embeddings
        )
        prepared.append((phrase, normalized_section, best))

    return prepared


def decide_candidates(prepared, existing_detected, threshold):
    """Cheap, threshold-dependent decision over pre-embedded phrases.
    Applies the same negation + context-exclusion safety gate an exact
    match would face. Only ever ADDS allergens beyond existing_detected."""

    confirmed = set()
    evidence = []

    for phrase, normalized_section, best in prepared:
        for allergen, (term, similarity) in best.items():
            if allergen in existing_detected or allergen in confirmed:
                continue
            if similarity < threshold:
                continue
            if is_negated(allergen, normalized_section):
                continue
            if not _is_valid_match(allergen, term, normalized_section):
                continue

            confirmed.add(allergen)
            evidence.append({
                "allergen": allergen,
                "phrase": phrase,
                "matched_dictionary_term": term,
                "similarity": round(similarity, 4),
            })

    return confirmed, evidence


# ============================================================
# EVALUATION AT ONE THRESHOLD
# ============================================================

def multilabel_metrics(records, true_key, pred_key):
    labels = sorted(set(a for r in records for a in r[true_key] | r[pred_key]))
    if not labels:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    y_true = [[int(l in r[true_key]) for l in labels] for r in records]
    y_pred = [[int(l in r[pred_key]) for l in labels] for r in records]
    p, r, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average="micro", zero_division=0
    )
    return {"precision": round(float(p), 4), "recall": round(float(r), 4), "f1": round(float(f1), 4)}


def exact_match_rate(records, true_key, pred_key):
    if not records:
        return 0.0
    return round(sum(r[true_key] == r[pred_key] for r in records) / len(records), 4)


def precompute_dev_set(dev_df, dictionary, model, dict_terms, dict_allergens, dict_embeddings):
    """One pass: rule-only detection + embedding of every phrase, for
    every product. Threshold sweeps below reuse this without any further
    model.encode() calls."""

    prepared_rows = []

    for i, (_, row) in enumerate(dev_df.iterrows()):
        text = row["ingredients_text"]
        true_declared = parse_tags(row.get("allergens_tags", ""))
        true_trace = parse_tags(row.get("traces_tags", ""))

        declared_text, trace_text = split_declared_and_trace_text(text)

        rule_declared = detect_allergen_matches(declared_text, dictionary)["detected"]
        rule_trace = detect_allergen_matches(trace_text, dictionary)["detected"]

        declared_prepared = embed_section(declared_text, model, dict_terms, dict_allergens, dict_embeddings)
        trace_prepared = embed_section(trace_text, model, dict_terms, dict_allergens, dict_embeddings)

        prepared_rows.append({
            "code": row["code"],
            "true_declared": true_declared,
            "true_trace": true_trace,
            "rule_declared": rule_declared,
            "rule_trace": rule_trace,
            "declared_prepared": declared_prepared,
            "trace_prepared": trace_prepared,
        })

        if (i + 1) % 200 == 0:
            print(f"  embedded {i + 1}/{len(dev_df)} products...")

    return prepared_rows


def evaluate_at_threshold(prepared_rows, threshold):
    declared_records = []
    trace_records = []
    all_evidence = []

    for row in prepared_rows:
        new_declared, declared_evidence = decide_candidates(
            row["declared_prepared"], row["rule_declared"], threshold
        )
        new_trace, trace_evidence = decide_candidates(
            row["trace_prepared"], row["rule_trace"], threshold
        )

        hybrid_declared = row["rule_declared"] | new_declared
        hybrid_trace = row["rule_trace"] | new_trace

        declared_records.append({
            "reference_allergens": row["true_declared"],
            "predicted_allergens": hybrid_declared,
        })
        trace_records.append({
            "reference_allergens": row["true_trace"],
            "predicted_allergens": hybrid_trace,
        })

        for e in declared_evidence:
            all_evidence.append({"code": row["code"], "section": "declared", **e})
        for e in trace_evidence:
            all_evidence.append({"code": row["code"], "section": "trace", **e})

    return {
        "declared": {
            **multilabel_metrics(declared_records, "reference_allergens", "predicted_allergens"),
            "exact_match": exact_match_rate(declared_records, "reference_allergens", "predicted_allergens"),
        },
        "trace": {
            **multilabel_metrics(trace_records, "reference_allergens", "predicted_allergens"),
            "exact_match": exact_match_rate(trace_records, "reference_allergens", "predicted_allergens"),
        },
        "n_candidates_confirmed": len(all_evidence),
        "evidence_sample": all_evidence[:25],
    }


# ============================================================
# MAIN
# ============================================================

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    dictionary = load_dictionary()
    dev_df = load_leak_free_dev_set()
    print(f"Dev set (leak-free): {len(dev_df)} products")

    print(f"Loading {MODEL_NAME} ...")
    model = SentenceTransformer(MODEL_NAME)

    dict_terms, dict_allergens, dict_embeddings = build_dictionary_embedding_index(model, dictionary)
    print(f"Dictionary embedding index: {len(dict_terms)} terms across {len(set(dict_allergens))} allergens")

    # --- Rule-only baseline on this exact set (reuse Phase 1's numbers if
    # available, else recompute fresh for self-containment) ---
    rule_declared_records = []
    rule_trace_records = []
    for _, row in dev_df.iterrows():
        text = row["ingredients_text"]
        true_declared = parse_tags(row.get("allergens_tags", ""))
        true_trace = parse_tags(row.get("traces_tags", ""))
        declared_text, trace_text = split_declared_and_trace_text(text)
        rule_declared_records.append({
            "reference_allergens": true_declared,
            "predicted_allergens": detect_allergen_matches(declared_text, dictionary)["detected"],
        })
        rule_trace_records.append({
            "reference_allergens": true_trace,
            "predicted_allergens": detect_allergen_matches(trace_text, dictionary)["detected"],
        })
    rule_baseline = {
        "declared": {
            **multilabel_metrics(rule_declared_records, "reference_allergens", "predicted_allergens"),
            "exact_match": exact_match_rate(rule_declared_records, "reference_allergens", "predicted_allergens"),
        },
        "trace": {
            **multilabel_metrics(rule_trace_records, "reference_allergens", "predicted_allergens"),
            "exact_match": exact_match_rate(rule_trace_records, "reference_allergens", "predicted_allergens"),
        },
    }

    print()
    print("=" * 70)
    print("RULE-ONLY BASELINE (963-product leak-free set)")
    print("=" * 70)
    print(json.dumps(rule_baseline, indent=2))

    # --- Embed everything once, then sweep thresholds cheaply ---
    print("\nEmbedding all dev-set ingredient phrases (one pass, reused across the threshold sweep)...")
    prepared_rows = precompute_dev_set(dev_df, dictionary, model, dict_terms, dict_allergens, dict_embeddings)

    sweep_results = {}
    for threshold in THRESHOLD_GRID:
        print(f"\nEvaluating threshold={threshold} ...")
        result = evaluate_at_threshold(prepared_rows, threshold)
        sweep_results[str(threshold)] = result
        print(f"  declared F1={result['declared']['f1']:.4f} (rule={rule_baseline['declared']['f1']:.4f})  "
              f"trace F1={result['trace']['f1']:.4f} (rule={rule_baseline['trace']['f1']:.4f})  "
              f"candidates confirmed={result['n_candidates_confirmed']}")

    # --- Pick the best threshold: must not hurt precision meaningfully,
    # judged by F1 not dropping below the rule baseline on EITHER
    # declared or trace, with the largest combined F1 gain ---
    def combined_gain(result):
        d_gain = result["declared"]["f1"] - rule_baseline["declared"]["f1"]
        t_gain = result["trace"]["f1"] - rule_baseline["trace"]["f1"]
        if d_gain < -0.005 or t_gain < -0.005:
            return -999  # disqualified: hurts either metric
        return d_gain + t_gain

    best_threshold = max(sweep_results, key=lambda t: combined_gain(sweep_results[t]))
    best_result = sweep_results[best_threshold]
    go_live = combined_gain(best_result) > 0

    print()
    print("=" * 70)
    print(f"BEST THRESHOLD: {best_threshold}  |  VERDICT: {'GO LIVE' if go_live else 'DO NOT GO LIVE'}")
    print("=" * 70)
    print(f"Declared F1: {rule_baseline['declared']['f1']:.4f} -> {best_result['declared']['f1']:.4f}")
    print(f"Trace F1:    {rule_baseline['trace']['f1']:.4f} -> {best_result['trace']['f1']:.4f}")

    # --- Save ---
    with (OUTPUT_DIR / "threshold_sweep.json").open("w", encoding="utf-8") as f:
        json.dump({
            "model": MODEL_NAME,
            "evaluation_set": "963-product leak-free dev set, same as ml_trace_classifier.py",
            "held_out_300_touched": False,
            "rule_only_baseline": rule_baseline,
            "sweep": sweep_results,
            "best_threshold": best_threshold,
            "verdict": {
                "go_live": go_live,
                "declared_f1_delta": round(best_result["declared"]["f1"] - rule_baseline["declared"]["f1"], 4),
                "trace_f1_delta": round(best_result["trace"]["f1"] - rule_baseline["trace"]["f1"], 4),
            },
        }, f, indent=2, default=str)

    np.save(OUTPUT_DIR / "dictionary_embeddings.npy", dict_embeddings)
    with (OUTPUT_DIR / "dictionary_terms.json").open("w", encoding="utf-8") as f:
        json.dump({"terms": dict_terms, "allergens": dict_allergens}, f, indent=2)

    print(f"\nResults saved to: {OUTPUT_DIR}")

    return go_live, best_threshold


if __name__ == "__main__":
    main()
