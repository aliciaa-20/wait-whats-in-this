import ast
import json
import random
from pathlib import Path

import pandas as pd


# ============================================================
# Configuration
# ============================================================

INPUT_FILE = Path("data/cleaned_products.csv")
BENCHMARK_FILE = Path("data/benchmark/metadata.csv")

OUTPUT_DIR = Path("data/research")
GROUND_TRUTH_FILE = OUTPUT_DIR / "ground_truth.csv"
SUMMARY_FILE = OUTPUT_DIR / "sampling_summary.json"

SEED = 42
TOTAL_TARGET = 300


# Target composition
TARGET_NO_ALLERGEN = 50
TARGET_DECLARED = 150
TARGET_TRACE = 50
TARGET_MULTI = 25
TARGET_DIFFICULT = 25


# ============================================================
# Helpers
# ============================================================

def parse_list(value):
    """Safely parse list-like CSV fields."""
    if pd.isna(value):
        return []

    value = str(value).strip()

    if not value:
        return []

    try:
        parsed = ast.literal_eval(value)

        if isinstance(parsed, list):
            return [str(x).strip() for x in parsed if str(x).strip()]

    except (ValueError, SyntaxError):
        pass

    return []


def canonical_allergen(tag):
    """Map Open Food Facts allergen tags to project allergen IDs."""

    tag = tag.lower().strip()

    mapping = {
        "en:milk": "milk",
        "en:dairy": "milk",

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
        "en:shellfish": "shellfish",

        "en:sesame-seeds": "sesame",
        "en:sesame": "sesame",
    }

    return mapping.get(tag)


def get_allergens(row, column):
    """Return canonical allergen IDs from an OFF tag column."""

    tags = parse_list(row[column])

    allergens = set()

    for tag in tags:
        allergen = canonical_allergen(tag)

        if allergen:
            allergens.add(allergen)

    return sorted(allergens)


def has_trace(row):
    return len(get_allergens(row, "traces_tags")) > 0


def has_declared(row):
    return len(get_allergens(row, "allergens_tags")) > 0


def is_multi(row):
    declared = get_allergens(row, "allergens_tags")
    trace = get_allergens(row, "traces_tags")

    return len(set(declared + trace)) >= 2


def contains_context_terms(row):
    """
    Identify potentially difficult/context-heavy examples.

    These are candidates for manual review, not automatic ground truth.
    """

    text = str(row["ingredients_text"]).lower()

    context_terms = [
        "may contain",
        "may contain traces",
        "traces of",
        "contains",
        "peut contenir",
        "peut contenir des traces",
        "peut contenir des",
        "kann enthalten",
        "kann spuren enthalten",
        "puede contener",
        "puede contener trazas",
        "pode conter",
        "pode conter vestígios",
        "kan sporen bevatten",
        "kan bevatten",
        "può contenere",
        "può contenere tracce",
        "senza glutine",
        "glutenfrei",
        "sans gluten",
        "gluten free",
        "free from",
    ]

    return any(term in text for term in context_terms)


# ============================================================
# Load dataset
# ============================================================

print("Loading cleaned dataset...")

df = pd.read_csv(INPUT_FILE)

print(f"Total cleaned products: {len(df)}")


# ============================================================
# Basic eligibility filtering
# ============================================================

df["ingredients_text"] = df["ingredients_text"].fillna("").astype(str)

eligible = df[
    df["ingredients_text"].str.strip().ne("")
].copy()

print(f"Products with ingredient text: {len(eligible)}")


# ============================================================
# Exclude existing OCR benchmark
# ============================================================

excluded_codes = set()

if BENCHMARK_FILE.exists():
    benchmark = pd.read_csv(BENCHMARK_FILE)

    if "code" in benchmark.columns:
        excluded_codes = set(
            benchmark["code"]
            .astype(str)
            .str.strip()
        )

print(f"Existing benchmark products excluded: {len(excluded_codes)}")

eligible["code"] = eligible["code"].astype(str).str.strip()

eligible = eligible[
    ~eligible["code"].isin(excluded_codes)
].copy()

print(f"Remaining eligible products: {len(eligible)}")


# ============================================================
# Remove duplicates
# ============================================================

eligible = eligible.drop_duplicates(
    subset=["code"],
    keep="first"
).copy()


# ============================================================
# Derived labels
# ============================================================

eligible["declared_allergens"] = eligible.apply(
    lambda row: get_allergens(row, "allergens_tags"),
    axis=1
)

eligible["trace_allergens"] = eligible.apply(
    lambda row: get_allergens(row, "traces_tags"),
    axis=1
)

eligible["has_declared"] = eligible["declared_allergens"].apply(
    lambda x: len(x) > 0
)

eligible["has_trace"] = eligible["trace_allergens"].apply(
    lambda x: len(x) > 0
)

eligible["is_multi"] = eligible.apply(
    is_multi,
    axis=1
)

eligible["is_context"] = eligible.apply(
    contains_context_terms,
    axis=1
)


# ============================================================
# Sampling
# ============================================================

rng = random.Random(SEED)


def random_sample(pool, target):
    """Sample up to target rows using a deterministic seed."""

    pool = pool.copy()

    if len(pool) <= target:
        return pool

    indices = list(pool.index)
    selected = rng.sample(indices, target)

    return pool.loc[selected]


selected_parts = []
selected_codes = set()


def add_sample(pool, target, category):
    """Add products while preventing overlap between categories."""

    global selected_parts

    pool = pool[
        ~pool["code"].isin(selected_codes)
    ].copy()

    sampled = random_sample(pool, target)

    if len(sampled) > 0:
        selected_parts.append(
            (category, sampled.copy())
        )

        selected_codes.update(
            sampled["code"].tolist()
        )

    print(
        f"{category}: requested={target}, "
        f"selected={len(sampled)}"
    )


# ------------------------------------------------------------
# Priority order
#
# Difficult/context and multi-allergen examples are selected
# first so they are not consumed by broader categories.
# ------------------------------------------------------------

add_sample(
    eligible[eligible["is_context"]],
    TARGET_DIFFICULT,
    "difficult_context"
)

add_sample(
    eligible[
        eligible["is_multi"] &
        ~eligible["is_context"]
    ],
    TARGET_MULTI,
    "multi_allergen"
)

# Declared allergen examples
add_sample(
    eligible[
        eligible["has_declared"] &
        ~eligible["is_multi"] &
        ~eligible["is_context"]
    ],
    TARGET_DECLARED,
    "declared_allergen"
)

# Trace-only examples
add_sample(
    eligible[
        ~eligible["has_declared"] &
        eligible["has_trace"] &
        ~eligible["is_context"]
    ],
    TARGET_TRACE,
    "trace_allergen"
)

# No allergen examples
add_sample(
    eligible[
        ~eligible["has_declared"] &
        ~eligible["has_trace"] &
        ~eligible["is_context"]
    ],
    TARGET_NO_ALLERGEN,
    "no_allergen"
)


# ============================================================
# Combine
# ============================================================

if selected_parts:
    research = pd.concat(
        [part[1] for part in selected_parts],
        ignore_index=True
    )
else:
    research = pd.DataFrame()


# ============================================================
# Top-up if fewer than 300 were selected
# ============================================================

remaining_target = TOTAL_TARGET - len(research)

if remaining_target > 0:

    remaining = eligible[
        ~eligible["code"].isin(selected_codes)
    ].copy()

    # Prefer examples with allergen information for the top-up.
    remaining["priority"] = (
        remaining["has_declared"].astype(int) * 2
        + remaining["has_trace"].astype(int)
    )

    remaining = remaining.sort_values(
        "priority",
        ascending=False
    )

    topup = random_sample(
        remaining,
        remaining_target
    )

    if len(topup) > 0:
        research = pd.concat(
            [research, topup],
            ignore_index=True
        )

        selected_codes.update(
            topup["code"].tolist()
        )

        print(
            f"Top-up: requested={remaining_target}, "
            f"selected={len(topup)}"
        )


# ============================================================
# Add research annotation fields
# ============================================================

research["image_path"] = ""
research["image_language"] = ""

research["reference_ingredients"] = (
    research["ingredients_text"]
)

research["evidence"] = ""
research["negated_terms"] = ""
research["annotator"] = ""
research["annotation_date"] = ""
research["notes"] = ""


# Store OFF-derived information separately for annotation support.
# These are NOT considered manually verified ground truth yet.

research["off_declared_allergens"] = research[
    "declared_allergens"
].apply(
    lambda x: ", ".join(x)
)

research["off_trace_allergens"] = research[
    "trace_allergens"
].apply(
    lambda x: ", ".join(x)
)


# ============================================================
# Keep only useful columns
# ============================================================

output_columns = [
    "code",
    "product_name",
    "lang",
    "image_path",
    "image_language",
    "reference_ingredients",

    # Fields to be manually verified
    "declared_allergens",
    "trace_allergens",
    "evidence",
    "negated_terms",
    "annotator",
    "annotation_date",
    "notes",

    # Original OFF metadata retained for comparison
    "off_declared_allergens",
    "off_trace_allergens",
]

research = research[output_columns].copy()


# Convert lists to readable strings
research["declared_allergens"] = research[
    "declared_allergens"
].apply(lambda x: ", ".join(x))

research["trace_allergens"] = research[
    "trace_allergens"
].apply(lambda x: ", ".join(x))


# ============================================================
# Shuffle final dataset
# ============================================================

research = research.sample(
    frac=1,
    random_state=SEED
).reset_index(drop=True)


# ============================================================
# Save
# ============================================================

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)

research.to_csv(
    GROUND_TRUTH_FILE,
    index=False
)


# ============================================================
# Summary statistics
# ============================================================

summary = {
    "random_seed": SEED,
    "total_cleaned_products": int(len(df)),
    "products_with_ingredient_text": int(
        df["ingredients_text"].str.strip().ne("").sum()
    ),
    "benchmark_products_excluded": int(
        len(excluded_codes)
    ),
    "eligible_after_exclusion": int(
        len(eligible)
    ),
    "research_set_size": int(
        len(research)
    ),
    "target_size": TOTAL_TARGET,
    "targets": {
        "no_allergen": TARGET_NO_ALLERGEN,
        "declared_allergen": TARGET_DECLARED,
        "trace_allergen": TARGET_TRACE,
        "multi_allergen": TARGET_MULTI,
        "difficult_context": TARGET_DIFFICULT,
    },
    "languages": (
        research["lang"]
        .fillna("unknown")
        .value_counts()
        .to_dict()
    ),
    "notes": [
        "This is a held-out research set.",
        "Products from the existing OCR benchmark were excluded.",
        "OFF allergen tags are retained as reference metadata.",
        "Declared and trace allergen fields must be manually verified.",
        "Matcher predictions must not be consulted during annotation.",
    ],
}


with open(
    SUMMARY_FILE,
    "w",
    encoding="utf-8"
) as f:
    json.dump(
        summary,
        f,
        indent=2,
        ensure_ascii=False
    )


# ============================================================
# Print final report
# ============================================================

print()
print("=" * 60)
print("RESEARCH SET CREATED")
print("=" * 60)

print(f"Final size: {len(research)}")
print(f"CSV: {GROUND_TRUTH_FILE}")
print(f"Summary: {SUMMARY_FILE}")

print()
print("Language distribution:")
print(
    research["lang"]
    .fillna("unknown")
    .value_counts()
)

print()
print("Products with declared allergens:")
print(
    (
        research["declared_allergens"]
        .fillna("")
        .str.strip()
        .ne("")
    ).sum()
)

print("Products with trace allergens:")
print(
    (
        research["trace_allergens"]
        .fillna("")
        .str.strip()
        .ne("")
    ).sum()
)

print()
print("IMPORTANT:")
print(
    "Manually verify declared_allergens and trace_allergens "
    "before using this set as ground truth."
)