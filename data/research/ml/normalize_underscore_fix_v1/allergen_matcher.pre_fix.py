"""
Reusable allergen matching engine.

This module contains the text-analysis layer used by both:
1. dataset evaluation
2. OCR -> allergen analysis

The allergen vocabulary is loaded from data/allergen_dictionary.json.
"""

import ast
import json
import re
import unicodedata
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
DICTIONARY_FILE = DATA_DIR / "allergen_dictionary.json"

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

TAG_TO_ALLERGEN = {
    "milk": "milk",
    "lait": "milk",
    "leche": "milk",
    "leite": "milk",
    "milch": "milk",
    "mlijeko": "milk",
    "latte": "milk",

    "egg": "egg",
    "eggs": "egg",
    "oeuf": "egg",
    "oeufs": "egg",
    "huevo": "egg",
    "huevos": "egg",
    "ovo": "egg",
    "ovos": "egg",
    "eier": "egg",
    "ei": "egg",

    "peanut": "peanut",
    "peanuts": "peanut",
    "arachide": "peanut",
    "arachides": "peanut",
    "cacahuete": "peanut",
    "cacahuetes": "peanut",
    "amendoim": "peanut",
    "amendoins": "peanut",

    "nuts": "tree_nut",
    "nut": "tree_nut",
    "tree-nuts": "tree_nut",
    "tree-nut": "tree_nut",
    "noix": "tree_nut",
    "fruits-a-coque": "tree_nut",
    "frutos-de-cascara": "tree_nut",
    "frutos-de-casca-rija": "tree_nut",
    "schalenfruchte": "tree_nut",
    "schalenfrüchte": "tree_nut",

    "soy": "soy",
    "soya": "soy",
    "soybean": "soy",
    "soybeans": "soy",
    "soja": "soy",

    "wheat": "wheat_gluten",
    "weizen": "wheat_gluten",
    "ble": "wheat_gluten",
    "blé": "wheat_gluten",
    "gluten": "wheat_gluten",
    "cereals-with-gluten": "wheat_gluten",
    "cereals with gluten": "wheat_gluten",
    "cereales-avec-gluten": "wheat_gluten",
    "cereales-con-gluten": "wheat_gluten",

    "fish": "fish",
    "poisson": "fish",
    "pescado": "fish",
    "peixe": "fish",
    "fisch": "fish",

    "crustaceans": "shellfish",
    "crustacean": "shellfish",
    "crustaces": "shellfish",
    "crustacés": "shellfish",
    "crustaceos": "shellfish",
    "crustáceos": "shellfish",
    "molluscs": "shellfish",
    "mollusks": "shellfish",
    "shellfish": "shellfish",

    "sesame": "sesame",
    "sesamo": "sesame",
    "sésame": "sesame",
    "sesam": "sesame",
    "sesame-seeds": "sesame",
}


PLANT_MILK_PATTERNS = [
    r"\balmond milk\b",
    r"\bsoy milk\b",
    r"\bsoya milk\b",
    r"\bcoconut milk\b",
    r"\boat milk\b",
    r"\bhazelnut milk\b",
    r"\blait d amande\b",
    r"\blait d amandes\b",
    r"\blait de soja\b",
    r"\blait de coco\b",
    r"\blait d avoine\b",
    r"\blait de noisette\b",
    r"\bleche de almendra\b",
    r"\bleche de almendras\b",
    r"\bleche de soja\b",
    r"\bleche de coco\b",
    r"\bleche de avena\b",
    r"\bleche de avellana\b",
    r"\bleite de amendoa\b",
    r"\bleite de amendoas\b",
    r"\bleite de soja\b",
    r"\bleite de coco\b",
    r"\bleite de aveia\b",
    r"\bleite de avela\b",
    r"\bmandelmilch\b",
    r"\bsojamilch\b",
    r"\bkokosmilch\b",
    r"\bhafermilch\b",
    r"\bhaselnussmilch\b",
]

COCOA_BUTTER_PATTERNS = [
    r"\bbeurre de cacao\b",
    r"\bcocoa butter\b",
    r"\bcacao butter\b",
    r"\bkakaobutter\b",
    r"\bcacaoboter\b",
]

COCONUT_PATTERNS = [
    r"\bcoconut\b",
    r"\bcoco\b",
    r"\bcocoanut\b",
    r"\bnoix de coco\b",
    r"\bnoix de coco sechee\b",
    r"\bkokus\b",
    r"\bkokos\b",
    r"\bkokosnuss\b",
    r"\bkokosnüsse\b",
    r"\bcoco rallado\b",
]

GLUTEN_FREE_PATTERNS = [
    r"\bgluten free\b",
    r"\bglutenfrei\b",
    r"\bsans gluten\b",
    r"\bsin gluten\b",
    r"\bsem gluten\b",
    r"\bsem glutén\b",
    r"\bsem glúten\b",
    r"\bglutenvrij\b",
    r"\bglutenfri\b",
    r"\bglutenfritt\b",
    r"\bbez glutenu\b",
    r"\bgluten y lactosa libre\b",
]

NEGATION_PATTERNS = {
    "peanut": [
        r"\bno peanuts?\b",
        r"\bwithout peanuts?\b",
        r"\bkeine erdnusse\b",
        r"\bsans arachides?\b",
        r"\bsin cacahuetes?\b",
        r"\bsem amendoim\b",
        r"\bبدون فول سوداني\b",
        r"\bلا يحتوي على فول سوداني\b",
    ],
    "milk": [
        r"\bno milk\b",
        r"\bwithout milk\b",
        r"\bohne milch\b",
        r"\bsans lait\b",
        r"\bsin leche\b",
        r"\bsem leite\b",
    ],
    "egg": [
        r"\bno eggs?\b",
        r"\bwithout eggs?\b",
        r"\bohne ei\b",
        r"\bohne eier\b",
        r"\bsans oeuf\b",
        r"\bsans oeufs\b",
        r"\bsin huevo\b",
        r"\bsin huevos\b",
    ],
}

TRACE_REGEXES = [
    r"\bmay contain\b",
    r"\bmay contain traces\b",
    r"\btraces of\b",
    r"\btraces may be present\b",
    r"\bmade in a facility\b",
    r"\bmade in a factory\b",
    r"\bmanufactured in a facility\b",
    r"\bmanufactured in a factory\b",
    r"\bprocessed in a facility\b",
    r"\bproduced in a facility\b",

    r"\bpeut contenir\b",
    r"\btraces de\b",
    r"\btraces possibles\b",
    r"\btraces eventuelles\b",
    r"\bfabrique dans un atelier\b",
    r"\bfabrique dans une usine\b",
    r"\bproduit dans un atelier\b",

    r"\bkann enthalten\b",
    r"\bkann spuren enthalten\b",
    r"\bkann spuren von\b",
    r"\bspuren von\b",
    # "kann Haselnüsse, Mandeln, Milch enthalten" - the allergen list sits
    # between "kann" and "enthalten" rather than the two words being
    # adjacent, which the patterns above require. Bounded to one clause
    # (no period) so this doesn't reach across unrelated sentences.
    r"\bkann\b[^.]{0,80}\benthalten\b",
    r"\bhergestellt in einem betrieb\b",
    r"\bhergestellt in einer anlage\b",

    r"\bpuede contener\b",
    r"\bpuede contener trazas\b",
    r"\btrazas de\b",
    r"\btrazas posibles\b",
    r"\belaborado en una fabrica\b",
    r"\bfabricado en una planta\b",

    r"\bpode conter\b",
    r"\bpode conter vestigios\b",
    r"\bvestigios de\b",
    r"\btracos de\b",
    r"\bfabricado numa instalacao\b",

    r"\bkan bevatten\b",
    r"\bkan sporen bevatten\b",
    r"\bsporen van\b",

    r"\bkan inneholde\b",
    r"\bkan inneholde spor av\b",
    r"\bkan indeholde\b",
    r"\bkan indeholde spor af\b",
    r"\bkan innehalla\b",
    r"\bkan innehalla spar av\b",

    r"\bقد يحتوي\b",
    r"\bقد يحتوي على\b",
    r"\bيمكن أن يحتوي\b",
    r"\bيمكن ان يحتوي\b",
    r"\bقد يحتوي على آثار\b",
    r"\bقد يحتوي آثار\b",
]


def normalize_text(text):
    """Normalize multilingual text while preserving non-Latin scripts."""
    if text is None:
        return ""

    text = str(text)
    text = unicodedata.normalize("NFKC", text).lower()

    text = text.replace("’", "'")
    text = text.replace("‘", "'")
    text = text.replace("–", "-")
    text = text.replace("—", "-")
    text = text.replace("œ", "oe")
    text = text.replace("æ", "ae")

    decomposed = unicodedata.normalize("NFKD", text)
    text = "".join(
        char for char in decomposed
        if not unicodedata.combining(char)
    )

    text = re.sub(r"[^\w\s\-]", " ", text, flags=re.UNICODE)
    text = re.sub(r"[-]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text


def phrase_in_text(phrase, text):
    """Boundary-safe phrase matching."""
    phrase = normalize_text(phrase)
    text = normalize_text(text)

    if not phrase or not text:
        return False

    pattern = r"(?<!\w)" + re.escape(phrase) + r"(?!\w)"
    return re.search(pattern, text, flags=re.UNICODE) is not None


def matches_any_pattern(text, patterns):
    normalized = normalize_text(text)

    return any(
        re.search(
            pattern,
            normalized,
            flags=re.IGNORECASE | re.UNICODE,
        )
        for pattern in patterns
    )


def load_dictionary(path=None):
    """
    Load the JSON vocabulary as the single source of truth.

    Returns a dict of allergen -> set(normalized terms).
    """
    dictionary_path = Path(path) if path else DICTIONARY_FILE

    if not dictionary_path.exists():
        raise FileNotFoundError(
            f"Allergen dictionary not found: {dictionary_path}"
        )

    with open(dictionary_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    result = {
        allergen: set()
        for allergen in ALLERGENS
    }

    for allergen, values in data.items():
        if allergen not in result or not isinstance(values, list):
            continue

        for value in values:
            normalized = normalize_text(value)
            if normalized:
                result[allergen].add(normalized)

    return result


def is_negated(allergen, text):
    patterns = NEGATION_PATTERNS.get(allergen, [])
    normalized = normalize_text(text)

    return any(
        re.search(
            pattern,
            normalized,
            flags=re.IGNORECASE | re.UNICODE,
        )
        for pattern in patterns
    )


def trace_marker_match(text):
    """Return the earliest trace-marker match."""
    normalized = normalize_text(text)
    matches = []

    for pattern in TRACE_REGEXES:
        match = re.search(
            pattern,
            normalized,
            flags=re.IGNORECASE | re.UNICODE,
        )
        if match:
            matches.append(match)

    if not matches:
        return None

    return min(matches, key=lambda match: match.start())


def split_declared_and_trace_text(text):
    """
    Split ingredient text into declared and precautionary trace sections.

    This is a rule-based parser. It is not a regulatory interpretation.
    """
    if text is None:
        return "", ""

    try:
        if pd.isna(text):
            return "", ""
    except (TypeError, ValueError):
        pass

    original = str(text)
    marker = trace_marker_match(original)

    if marker is None:
        return original.strip(), ""

    normalized = normalize_text(original)
    start = marker.start()

    # Normalization removes accents and punctuation, so normalized and
    # original offsets are not guaranteed to be identical.
    estimated = min(start, len(original))
    search_start = max(0, estimated - 30)
    search_end = min(len(original), estimated + 60)
    fragment = original[search_start:search_end]

    marker_position = None

    marker_phrases = [
        "may contain",
        "peut contenir",
        "kann",
        "puede contener",
        "pode conter",
        "kan bevatten",
        "kan inneholde",
        "kan indeholde",
        "kan innehålla",
        "قد يحتوي",
        "يمكن أن يحتوي",
    ]

    fragment_normalized = normalize_text(fragment)

    for phrase in marker_phrases:
        position = fragment_normalized.find(normalize_text(phrase))
        if position >= 0:
            # Find the phrase in the original fragment where possible.
            original_position = fragment.lower().find(
                phrase.lower()
            )
            if original_position >= 0:
                marker_position = search_start + original_position
            break

    if marker_position is None:
        marker_position = estimated

    return (
        original[:marker_position].strip(),
        original[marker_position:].strip(),
    )


def _is_valid_match(allergen, synonym, normalized_text):
    """
    Apply context rules to one candidate synonym.

    Context checks are local where possible. This prevents generic
    terms such as "butter" from creating false positives when they
    are part of a non-dairy compound ingredient such as "peanut butter".
    """
    synonym = normalize_text(synonym)

    if allergen == "milk":

        # "butter" by itself is a valid dairy indicator.
        # However, some compound ingredients use "butter" without
        # being dairy products.
        if synonym == "butter":
            non_dairy_butter_patterns = [
                r"\bpeanut butter\b",
                r"\balmond butter\b",
                r"\bcashew butter\b",
                r"\bhazelnut butter\b",
                r"\bwalnut butter\b",
                r"\bpistachio butter\b",
                r"\bsunflower seed butter\b",
                r"\bseed butter\b",
            ]

            for pattern in non_dairy_butter_patterns:
                if re.search(
                    pattern,
                    normalized_text,
                    flags=re.IGNORECASE | re.UNICODE,
                ):
                    return False

        # Plant-based milks should not automatically create a
        # milk-protein match.
        if synonym in {
            "milk",
            "lait",
            "leche",
            "leite",
            "milch",
        }:
            for pattern in PLANT_MILK_PATTERNS:
                for match in re.finditer(
                    pattern,
                    normalized_text,
                    flags=re.IGNORECASE | re.UNICODE,
                ):
                    start = match.start()
                    end = match.end()

                    local = normalized_text[
                        max(0, start):end
                    ]

                    if phrase_in_text(synonym, local):
                        return False

        # Cocoa butter is not automatically a milk ingredient.
        if synonym in {
            "butter",
            "beurre",
            "mantequilla",
            "manteiga",
        }:
            if matches_any_pattern(
                normalized_text,
                COCOA_BUTTER_PATTERNS,
            ):
                return False

    if allergen == "tree_nut":

        # Coconut is intentionally not classified as a tree nut
        # in this project's current allergen scope.
        if synonym in {
            "nut",
            "nuts",
            "noix",
            "tree nut",
            "tree nuts",
        }:
            if matches_any_pattern(
                normalized_text,
                COCONUT_PATTERNS,
            ):
                return False

    if allergen == "wheat_gluten":

        # "gluten free" should not itself create a gluten-positive
        # detection.
        if synonym in {
            "gluten",
            "gluten protein",
        }:
            if matches_any_pattern(
                normalized_text,
                GLUTEN_FREE_PATTERNS,
            ):
                return False

    return True


def detect_allergen_matches(text, dictionary):
    """
    Detect allergens and return evidence.

    Output:
        {
            "detected": set(...),
            "matches": [
                {
                    "allergen": "...",
                    "matched_term": "...",
                    "match_type": "direct"
                }
            ]
        }
    """
    normalized = normalize_text(text)

    if not normalized:
        return {
            "detected": set(),
            "matches": [],
        }

    detected = set()
    matches = []

    for allergen in ALLERGENS:
        synonyms = dictionary.get(allergen, set())

        if is_negated(allergen, normalized):
            continue

        # Prefer longer phrases so that "milk powder" is considered
        # before the shorter "milk".
        ordered_synonyms = sorted(
            synonyms,
            key=lambda value: (-len(value), value),
        )

        for synonym in ordered_synonyms:
            if not phrase_in_text(synonym, normalized):
                continue

            if not _is_valid_match(
                allergen,
                synonym,
                normalized,
            ):
                continue

            detected.add(allergen)
            matches.append(
                {
                    "allergen": allergen,
                    "matched_term": synonym,
                    "match_type": "direct",
                }
            )
            break

    return {
        "detected": detected,
        "matches": matches,
    }


def analyze_ingredient_text(text, dictionary=None):
    """
    Public reusable API for arbitrary ingredient text.

    Separates declared ingredients from precautionary traces and
    analyzes each section independently.
    """
    if dictionary is None:
        dictionary = load_dictionary()

    declared_text, trace_text = split_declared_and_trace_text(text)

    declared_result = detect_allergen_matches(
        declared_text,
        dictionary,
    )

    trace_result = detect_allergen_matches(
        trace_text,
        dictionary,
    )

    declared = declared_result["detected"]
    trace = trace_result["detected"]

    if declared:
        risk = "AVOID"
    elif trace:
        risk = "CAUTION"
    else:
        risk = "SAFE"

    return {
        "declared_text": declared_text,
        "trace_text": trace_text,
        "declared_allergens": sorted(declared),
        "trace_allergens": sorted(trace),
        "matches": declared_result["matches"],
        "trace_matches": trace_result["matches"],
        "risk": risk,
    }


def parse_tag_value(value):
    """Convert Open Food Facts tag values into normalized tag strings."""
    if value is None:
        return []

    try:
        if pd.isna(value):
            return []
    except (TypeError, ValueError):
        pass

    if isinstance(value, list):
        raw_values = value
    else:
        text = str(value).strip()
        if not text:
            return []

        try:
            parsed = ast.literal_eval(text)
            raw_values = parsed if isinstance(parsed, list) else [text]
        except (ValueError, SyntaxError):
            raw_values = re.split(r"[,;|]", text)

    result = []

    for item in raw_values:
        if item is None:
            continue

        item = str(item).strip()
        if not item:
            continue

        if ":" in item:
            item = item.split(":", 1)[1]

        normalized = normalize_text(item)

        if normalized:
            result.append(normalized)

    return result


def tags_to_allergens(value):
    """Convert Open Food Facts allergen tags to project allergen IDs."""
    allergens = set()

    for tag in parse_tag_value(value):
        if tag in TAG_TO_ALLERGEN:
            allergens.add(TAG_TO_ALLERGEN[tag])
            continue

        singular = tag[:-1] if tag.endswith("s") else tag

        if singular in TAG_TO_ALLERGEN:
            allergens.add(TAG_TO_ALLERGEN[singular])

    return allergens


def analyze_product(row, dictionary=None):
    """
    Backward-compatible product-level API.

    This preserves the result fields expected by the existing
    dataset evaluation script while using the reusable engine.
    """
    if dictionary is None:
        dictionary = load_dictionary()

    ingredient_text = row.get("ingredients_text", "")

    if ingredient_text is None:
        ingredient_text = ""

    try:
        if pd.isna(ingredient_text):
            ingredient_text = ""
    except (TypeError, ValueError):
        pass

    result = analyze_ingredient_text(
        str(ingredient_text),
        dictionary,
    )

    return {
        "declared_detected": set(result["declared_allergens"]),
        "trace_detected": set(result["trace_allergens"]),
        "metadata_declared": tags_to_allergens(
            row.get("allergens_tags", "")
        ),
        "metadata_trace": tags_to_allergens(
            row.get("traces_tags", "")
        ),
        "risk": result["risk"],
        "declared_text": result["declared_text"],
        "trace_text": result["trace_text"],
        "matches": result["matches"],
        "trace_matches": result["trace_matches"],
    }
