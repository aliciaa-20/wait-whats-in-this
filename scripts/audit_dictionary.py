"""
Phase 6 - ontology/dictionary consistency and coverage auditor.

Read-only diagnostic tool. It never modifies data/allergen_dictionary.json
and never auto-applies anything - every finding is a candidate for human
review, following the same propose -> human-approve -> apply pattern Phase
3's synonym expansion used, not an auto-fix. This automates checks that
were previously done by hand (the mantelrouge zero-occurrence cleanup, the
Schalenfrüchte/Erdnüsse inflection gaps, the missing-Spanish-egg-terms
gap) so they can be run as a standing check instead of found one at a time.

Checks:
    A. Zero-occurrence terms   - dictionary entries with no match anywhere
                                  in the dataset (same check that found
                                  'mantelrouge').
    B. Exact/near duplicates   - literal repeats and near-identical
                                  spellings within one allergen's term list.
    C. Cross-allergen conflicts - the same normalized term listed under
                                  more than one allergen.
    D. Morphological variant   - corpus words that look like an inflected
       candidates                form of an existing single-word term
                                  (the Schalenfrüchte/Schalenfrüchten
                                  pattern), not yet in any allergen's list.
    E. Language coverage gaps  - a language's common word for an allergen
                                  appears in the dataset but no dictionary
                                  term for that allergen covers it (the
                                  missing Spanish egg-terms pattern).

Usage:
    ./venv/bin/python -m scripts.audit_dictionary
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd

from scripts.allergen_matcher import (
    ALLERGENS,
    normalize_text,
    phrase_in_text,
)
from scripts.analyze_trace_false_negatives import RELATED_KEYWORDS

BASE_DIR = Path(__file__).resolve().parent.parent
DICTIONARY_FILE = BASE_DIR / "data" / "allergen_dictionary.json"
DATASET_FILE = BASE_DIR / "data" / "cleaned_products.csv"
OUTPUT_DIR = BASE_DIR / "data" / "research" / "ml" / "ontology_audit_v1"

NEAR_DUPLICATE_THRESHOLD = 0.85
MORPH_MIN_BASE_LEN = 4
MORPH_MAX_SUFFIX_LEN = 5
MORPH_MIN_CORPUS_FREQ = 1


def load_raw_dictionary():
    with DICTIONARY_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_corpus_text(df: pd.DataFrame) -> str:
    texts = df["ingredients_text"].fillna("").astype(str)
    return normalize_text(" \n ".join(texts))


def build_corpus_vocab(df: pd.DataFrame) -> Counter:
    vocab = Counter()
    for text in df["ingredients_text"].fillna("").astype(str):
        for word in normalize_text(text).split():
            if len(word) >= 3:
                vocab[word] += 1
    return vocab


def find_zero_occurrence_terms(raw_dict, corpus_text):
    results = {}
    for allergen, terms in raw_dict.items():
        zero = [t for t in terms if not phrase_in_text(t, corpus_text)]
        if zero:
            results[allergen] = sorted(set(zero))
    return results


def find_duplicates(raw_dict):
    exact_dupes = {}
    near_dupes = {}

    for allergen, terms in raw_dict.items():
        normed = [normalize_text(t) for t in terms]
        counts = Counter(normed)
        exact = sorted({t for t, c in counts.items() if c > 1})
        if exact:
            exact_dupes[allergen] = exact

        uniq = sorted(set(normed))
        pairs = []
        for i in range(len(uniq)):
            for j in range(i + 1, len(uniq)):
                a, b = uniq[i], uniq[j]
                ratio = SequenceMatcher(None, a, b).ratio()
                if ratio >= NEAR_DUPLICATE_THRESHOLD:
                    pairs.append({"a": a, "b": b, "similarity": round(ratio, 3)})
        if pairs:
            near_dupes[allergen] = sorted(pairs, key=lambda p: -p["similarity"])

    return exact_dupes, near_dupes


def find_cross_allergen_conflicts(raw_dict):
    term_to_allergens = defaultdict(set)
    for allergen, terms in raw_dict.items():
        for t in terms:
            term_to_allergens[normalize_text(t)].add(allergen)
    return {
        term: sorted(allergens)
        for term, allergens in term_to_allergens.items()
        if len(allergens) > 1
    }


def find_morphological_candidates(raw_dict, vocab):
    all_terms_flat = {
        normalize_text(t) for terms in raw_dict.values() for t in terms
    }

    candidates = defaultdict(list)
    for allergen, terms in raw_dict.items():
        for t in terms:
            nt = normalize_text(t)
            if not nt or " " in nt or len(nt) < MORPH_MIN_BASE_LEN:
                continue
            for word, freq in vocab.items():
                if word == nt or word in all_terms_flat:
                    continue
                if word.startswith(nt):
                    suffix_len = len(word) - len(nt)
                    if 1 <= suffix_len <= MORPH_MAX_SUFFIX_LEN and freq >= MORPH_MIN_CORPUS_FREQ:
                        candidates[allergen].append({
                            "base_term": t,
                            "candidate": word,
                            "corpus_frequency": freq,
                        })

    for allergen in candidates:
        candidates[allergen].sort(key=lambda c: -c["corpus_frequency"])

    return dict(candidates)


def find_language_coverage_gaps(raw_dict, corpus_text):
    gaps = {}
    for allergen, keywords in RELATED_KEYWORDS.items():
        dict_terms_norm = " ".join(normalize_text(t) for t in raw_dict.get(allergen, []))
        missing = []
        for kw in keywords:
            kw_norm = normalize_text(kw).strip()
            if not kw_norm:
                continue
            appears_in_corpus = kw_norm in corpus_text
            covered_in_dict = kw_norm in dict_terms_norm
            if appears_in_corpus and not covered_in_dict:
                missing.append(kw.strip())
        if missing:
            gaps[allergen] = sorted(set(missing))
    return gaps


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    raw_dict = load_raw_dictionary()
    df = pd.read_csv(DATASET_FILE, dtype={"code": str})
    df["ingredients_text"] = df["ingredients_text"].fillna("").astype(str)
    df = df[df["ingredients_text"].str.strip() != ""]

    print(f"Auditing {sum(len(v) for v in raw_dict.values())} dictionary terms "
          f"against {len(df)} products...")

    corpus_text = build_corpus_text(df)
    vocab = build_corpus_vocab(df)

    zero_occurrence = find_zero_occurrence_terms(raw_dict, corpus_text)
    exact_dupes, near_dupes = find_duplicates(raw_dict)
    conflicts = find_cross_allergen_conflicts(raw_dict)
    morph_candidates = find_morphological_candidates(raw_dict, vocab)
    language_gaps = find_language_coverage_gaps(raw_dict, corpus_text)

    result = {
        "audit_type": "ontology_dictionary_consistency_and_coverage",
        "read_only": True,
        "dictionary_modified": False,
        "products_scanned": len(df),
        "total_terms_audited": sum(len(v) for v in raw_dict.values()),
        "findings": {
            "zero_occurrence_terms": zero_occurrence,
            "exact_duplicate_terms": exact_dupes,
            "near_duplicate_terms": near_dupes,
            "cross_allergen_conflicts": conflicts,
            "morphological_variant_candidates": morph_candidates,
            "language_coverage_gaps": language_gaps,
        },
        "counts": {
            "zero_occurrence_terms": sum(len(v) for v in zero_occurrence.values()),
            "exact_duplicate_terms": sum(len(v) for v in exact_dupes.values()),
            "near_duplicate_pairs": sum(len(v) for v in near_dupes.values()),
            "cross_allergen_conflicts": len(conflicts),
            "morphological_variant_candidates": sum(len(v) for v in morph_candidates.values()),
            "language_coverage_gaps": sum(len(v) for v in language_gaps.values()),
        },
        "note": (
            "Every finding here is a candidate for human review, not an "
            "applied change. None of this modifies the live dictionary. "
            "IMPORTANT CAVEAT for zero_occurrence_terms specifically: "
            "absence from THIS dataset is a necessary but not sufficient "
            "condition for 'anomalous' - a real, correctly-spelled word "
            "(e.g. 'salmon', 'lobster') can legitimately have zero "
            "occurrences simply because this dataset's products don't "
            "happen to contain that ingredient. The mantelrouge removal "
            "earlier in this project was justified because it ALSO failed "
            "a second, independent check (not a recognizable word in any "
            "supported language) - this tool only automates the "
            "zero-occurrence half of that process, not the language-"
            "recognizability half, so treat this list as 'worth a human "
            "glance', not 'confirmed anomalies'."
        ),
    }

    out_file = OUTPUT_DIR / "dictionary_audit_report.json"
    with out_file.open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print("DICTIONARY AUDIT SUMMARY")
    print("=" * 60)
    for key, count in result["counts"].items():
        print(f"  {key:35s} {count}")

    print("\n--- Zero-occurrence terms (unused in THIS dataset - NOT necessarily wrong;")
    print("    see the JSON report's caveat before treating any of these as anomalies) ---")
    for allergen, terms in zero_occurrence.items():
        print(f"  {allergen}: {terms}")

    print("\n--- Exact duplicate terms (candidates for de-dup) ---")
    for allergen, terms in exact_dupes.items():
        print(f"  {allergen}: {terms}")

    print("\n--- Cross-allergen conflicts ---")
    for term, allergens in conflicts.items():
        print(f"  '{term}': {allergens}")

    print("\n--- Language coverage gaps (word appears in data, no matching dict term) ---")
    for allergen, terms in language_gaps.items():
        print(f"  {allergen}: {terms}")

    print("\n--- Top morphological variant candidates (by corpus frequency) ---")
    for allergen, candidates in morph_candidates.items():
        top = candidates[:5]
        if top:
            print(f"  {allergen}:")
            for c in top:
                print(f"    '{c['base_term']}' -> '{c['candidate']}' (seen {c['corpus_frequency']}x)")

    print(f"\nFull report: {out_file}")


if __name__ == "__main__":
    main()
