"""
Phase 3 of the approved ML extension: semi-automatic synonym/ontology
expansion.

Reuses the same frozen embedding index built in
scripts/ml_embedding_candidates.py. Phase 2 showed this signal is too
false-positive-prone to decide risk autonomously - but that's exactly
why this phase is safe: every proposal here is a SHORTLIST for human
review, never an automatic dictionary edit. A human can reject
"graines de tournesol -> sesame" on sight; the risk that made Phase 2
fail live decisioning doesn't apply when a person is the final gate.

This script:
1. Collects distinct multi-word ingredient phrases from the 963-product
   leak-free dev set that the EXISTING exact/fuzzy matcher did not
   already resolve to any allergen.
2. Ranks them by embedding similarity to the dictionary's own terms.
3. Writes a human-reviewable shortlist (phrase, candidate allergen,
   matched dictionary term, similarity, example source product) -
   nothing is added to the dictionary by this script.

allergen_matcher.py and data/allergen_dictionary.json are not modified.

Usage:
    ./venv/bin/python -m scripts.ml_synonym_discovery
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

import pandas as pd
from sentence_transformers import SentenceTransformer

from scripts.allergen_matcher import (
    ALLERGENS,
    load_dictionary,
    normalize_text,
    split_declared_and_trace_text,
    detect_allergen_matches,
)
from scripts.ml_embedding_candidates import (
    MODEL_NAME,
    build_dictionary_embedding_index,
    split_ingredient_phrases,
    best_candidate_per_allergen,
)


BASE_DIR = Path(__file__).resolve().parent.parent
DATASET_FILE = BASE_DIR / "data" / "cleaned_products.csv"
HELDOUT_FILE = BASE_DIR / "data" / "research" / "ground_truth.csv"
OUTPUT_DIR = BASE_DIR / "data" / "research" / "ml" / "synonym_proposals_v1"

# Stricter than Phase 2's own best result, deliberately: this shortlist
# is meant to be short and mostly-good for a human reviewer, not
# exhaustive. Below this, the false-positive rate observed in Phase 2
# makes review not worth the reviewer's time.
SIMILARITY_THRESHOLD = 0.82
MAX_PROPOSALS_PER_ALLERGEN = 15


def load_leak_free_dev_set() -> pd.DataFrame:
    df = pd.read_csv(DATASET_FILE, dtype={"code": str})
    heldout = pd.read_csv(HELDOUT_FILE, dtype={"code": str})
    heldout_codes = set(heldout["code"])
    df["ingredients_text"] = df["ingredients_text"].fillna("").astype(str)
    df = df[df["ingredients_text"].str.strip() != ""].copy()
    df = df[~df["code"].isin(heldout_codes)].copy()
    return df.reset_index(drop=True)


def already_in_dictionary(phrase_normalized, dictionary):
    """Skip phrases that already contain an existing exact synonym term
    verbatim - not novel, nothing to propose."""
    for allergen in ALLERGENS:
        for term in dictionary.get(allergen, set()):
            if term and term in phrase_normalized:
                return True
    return False


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    dictionary = load_dictionary()
    dev_df = load_leak_free_dev_set()
    print(f"Dev set (leak-free): {len(dev_df)} products")

    print(f"Loading {MODEL_NAME} ...")
    model = SentenceTransformer(MODEL_NAME)

    dict_terms, dict_allergens, dict_embeddings = build_dictionary_embedding_index(model, dictionary)
    print(f"Dictionary embedding index: {len(dict_terms)} terms")

    # --- Collect distinct unresolved multi-word phrases ---
    unresolved_phrases = {}  # normalized_phrase -> {"display": str, "example_codes": set, "example_names": set}

    for _, row in dev_df.iterrows():
        text = row["ingredients_text"]
        declared_text, trace_text = split_declared_and_trace_text(text)

        for section_text in (declared_text, trace_text):
            for phrase in split_ingredient_phrases(section_text):
                normalized = normalize_text(phrase)
                if not normalized or already_in_dictionary(normalized, dictionary):
                    continue
                # Skip phrases the exact/fuzzy matcher already resolves
                # on their own (nothing novel to propose).
                if detect_allergen_matches(phrase, dictionary)["detected"]:
                    continue

                entry = unresolved_phrases.setdefault(normalized, {
                    "display": phrase.strip(),
                    "example_codes": set(),
                })
                entry["example_codes"].add(row["code"])

    print(f"Distinct unresolved multi-word phrases: {len(unresolved_phrases)}")

    normalized_list = list(unresolved_phrases.keys())
    display_list = [unresolved_phrases[n]["display"] for n in normalized_list]

    print("Embedding unresolved phrases...")
    phrase_embeddings = model.encode(normalized_list, normalize_embeddings=True, show_progress_bar=False)

    # --- Score against dictionary, group proposals by allergen ---
    proposals_by_allergen = defaultdict(list)

    for normalized, display, emb in zip(normalized_list, display_list, phrase_embeddings):
        best = best_candidate_per_allergen(emb, dict_terms, dict_allergens, dict_embeddings)
        for allergen, (term, similarity) in best.items():
            if similarity < SIMILARITY_THRESHOLD:
                continue
            proposals_by_allergen[allergen].append({
                "candidate_term": display,
                "normalized": normalized,
                "matched_dictionary_term": term,
                "similarity": round(float(similarity), 4),
                "example_product_codes": sorted(unresolved_phrases[normalized]["example_codes"])[:5],
                "n_products_seen_in": len(unresolved_phrases[normalized]["example_codes"]),
            })

    # --- Rank + cap per allergen ---
    final_shortlist = {}
    total = 0
    for allergen, proposals in proposals_by_allergen.items():
        ranked = sorted(proposals, key=lambda p: -p["similarity"])[:MAX_PROPOSALS_PER_ALLERGEN]
        for p in ranked:
            p["approved"] = None  # human fills in: true / false / null=undecided
            p["reviewer_notes"] = ""
        final_shortlist[allergen] = ranked
        total += len(ranked)

    print(f"\nShortlist: {total} proposals across {len(final_shortlist)} allergens "
          f"(threshold={SIMILARITY_THRESHOLD}, max {MAX_PROPOSALS_PER_ALLERGEN}/allergen)")

    output = {
        "note": (
            "Human-review shortlist. NOTHING here has been added to "
            "data/allergen_dictionary.json. Set 'approved': true/false "
            "per entry and provide this back for terms to actually be "
            "added - see ML_EXTENSION_PLAN.md Phase 3."
        ),
        "model": MODEL_NAME,
        "similarity_threshold": SIMILARITY_THRESHOLD,
        "dev_set_size": len(dev_df),
        "held_out_300_touched": False,
        "proposals_by_allergen": final_shortlist,
    }

    with (OUTPUT_DIR / "shortlist.json").open("w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nShortlist saved to: {OUTPUT_DIR / 'shortlist.json'}")
    print("No dictionary changes made. Awaiting review.")


if __name__ == "__main__":
    main()
