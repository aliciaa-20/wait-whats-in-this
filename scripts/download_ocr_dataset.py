#!/usr/bin/env python3

"""
Research-grade Open Food Facts OCR benchmark downloader.

Creates a reproducible held-out benchmark using:
- allergen stratification
- trace-allergen stratification
- language diversity
- control products
- ingredient-image availability
- deterministic random sampling

The benchmark metadata records:
- product language
- actual ingredient-image language
- OCR language
- reference ingredient text
- Open Food Facts allergen metadata
- trace metadata
- image URL
- image key
- sampling strata
- random seed

Important:
Open Food Facts metadata is reference metadata, not absolute ground truth.
Final benchmark samples should be manually verified before publication.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import pandas as pd
import requests


# ============================================================
# PATHS
# ============================================================

DATASET_PATH = Path("data/cleaned_products.csv")

OUTPUT_DIR = Path("data/benchmark")
IMAGE_DIR = OUTPUT_DIR / "images"

METADATA_PATH = OUTPUT_DIR / "metadata.csv"
DOWNLOAD_LOG_PATH = OUTPUT_DIR / "download_log.csv"
SUMMARY_PATH = OUTPUT_DIR / "sampling_summary.json"


# ============================================================
# OPEN FOOD FACTS API
# ============================================================

API_URL = "https://world.openfoodfacts.org/api/v3/product"

USER_AGENT = (
    "WaitWhatsInThis/1.0 "
    "(educational research project; "
    "https://github.com/aliciaa-20/wait-whats-in-this)"
)


# ============================================================
# DEFAULT SETTINGS
# ============================================================

DEFAULT_LIMIT = 20
DEFAULT_DELAY = 2.5
DEFAULT_TIMEOUT = 30
DEFAULT_SEED = 42


# ============================================================
# TARGET ALLERGENS
# ============================================================

TARGET_ALLERGENS = {
    "milk": "en:milk",
    "egg": "en:eggs",
    "peanut": "en:peanuts",
    "tree_nut": "en:nuts",
    "soy": "en:soybeans",
    "wheat_gluten": "en:gluten",
    "fish": "en:fish",
    "shellfish": "en:crustaceans",
    "sesame": "en:sesame",
}


# ============================================================
# DESIRED LANGUAGE COVERAGE
# ============================================================

LANGUAGE_TARGETS = [
    "fr",
    "en",
    "es",
    "de",
    "nl",
    "it",
    "ar",
    "pt",
]


# ============================================================
# DESIRED SAMPLING TARGETS
# ============================================================

ALLERGEN_TARGETS = {
    "milk": 25,
    "wheat_gluten": 25,
    "soy": 20,
    "tree_nut": 15,
    "egg": 10,
    "peanut": 7,
    "sesame": 7,
    "fish": 5,
    "shellfish": 4,
}

TRACE_TARGET = 10
CONTROL_TARGET = 15


# ============================================================
# API FIELDS
# ============================================================

API_FIELDS = [
    "code",
    "product_name",
    "lang",
    "languages_codes",
    "ingredients_text",
    "ingredients_text_en",
    "ingredients_text_fr",
    "ingredients_text_de",
    "ingredients_text_es",
    "ingredients_text_it",
    "ingredients_text_nl",
    "ingredients_text_pt",
    "ingredients_text_ar",
    "allergens_tags",
    "traces_tags",
    "selected_images",
]


# ============================================================
# HTTP SESSION
# ============================================================

SESSION = requests.Session()

SESSION.headers.update(
    {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }
)


# ============================================================
# STRING / LIST HELPERS
# ============================================================

def clean_string(value) -> str:
    """Convert a value into a clean string."""
    if value is None:
        return ""

    if isinstance(value, float) and pd.isna(value):
        return ""

    return str(value).strip()


def parse_tag_list(value) -> List[str]:
    """
    Parse Open Food Facts tag columns.

    Supports:
    - Python-style lists
    - JSON-like lists
    - semicolon-separated
    - comma-separated
    - pipe-separated
    """
    text = clean_string(value)

    if not text:
        return []

    if text.startswith("[") and text.endswith("]"):
        try:
            parsed = json.loads(text.replace("'", '"'))

            if isinstance(parsed, list):
                return [
                    str(item).strip().lower()
                    for item in parsed
                    if str(item).strip()
                ]

        except Exception:
            pass

    for separator in [";", "|", ","]:
        if separator in text:
            return [
                item.strip().lower()
                for item in text.split(separator)
                if item.strip()
            ]

    return [text.lower()]


def extract_allergen_ids(
    tags: List[str],
) -> Set[str]:
    """
    Convert Open Food Facts allergen tags
    into project allergen IDs.
    """
    tag_set = set(tags)

    detected = set()

    for allergen_id, off_tag in TARGET_ALLERGENS.items():

        if off_tag in tag_set:
            detected.add(allergen_id)

    return detected


# ============================================================
# DATASET
# ============================================================

def load_dataset() -> pd.DataFrame:
    """Load and clean the local dataset."""

    if not DATASET_PATH.exists():
        raise FileNotFoundError(
            f"Dataset not found: {DATASET_PATH}"
        )

    df = pd.read_csv(DATASET_PATH)

    required_columns = [
        "code",
        "product_name",
        "ingredients_text",
        "allergens_tags",
        "traces_tags",
        "lang",
    ]

    missing = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Missing columns: {missing}"
        )

    # Normalize product code.
    df["code"] = (
        df["code"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    # Remove empty codes.
    df = df[df["code"] != ""].copy()

    # Remove duplicate products.
    df = df.drop_duplicates(
        subset=["code"],
        keep="first",
    ).copy()

    # Require ingredient text.
    df["ingredients_text"] = (
        df["ingredients_text"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    df = df[
        df["ingredients_text"] != ""
    ].copy()

    # Normalize language.
    df["lang"] = (
        df["lang"]
        .fillna("")
        .astype(str)
        .str.lower()
        .str.strip()
    )

    # Parse allergen metadata.
    df["parsed_allergens"] = (
        df["allergens_tags"]
        .apply(parse_tag_list)
    )

    df["parsed_traces"] = (
        df["traces_tags"]
        .apply(parse_tag_list)
    )

    df["target_allergens"] = (
        df["parsed_allergens"]
        .apply(extract_allergen_ids)
    )

    df["target_trace_allergens"] = (
        df["parsed_traces"]
        .apply(extract_allergen_ids)
    )

    return df.reset_index(drop=True)


# ============================================================
# API
# ============================================================

def get_product(
    code: str,
) -> Tuple[Optional[dict], str]:
    """
    Retrieve one product.

    Returns:
        (product, status)

    Status examples:
        success
        http_404
        http_429
        http_500
        invalid_json
        missing_product
        request_error
    """

    url = f"{API_URL}/{code}"

    params = {
        "product_type": "all",
        "fields": ",".join(API_FIELDS),
    }

    try:

        response = SESSION.get(
            url,
            params=params,
            timeout=DEFAULT_TIMEOUT,
        )

    except requests.RequestException as exc:

        print(
            f"  Request error: "
            f"{type(exc).__name__}: {exc}"
        )

        return None, "request_error"

    status_code = response.status_code

    if status_code != 200:

        print(
            f"  API HTTP status: {status_code}"
        )

        return None, f"http_{status_code}"

    try:
        payload = response.json()

    except ValueError:

        print("  Invalid JSON response.")

        return None, "invalid_json"

    # IMPORTANT:
    # Open Food Facts returns a valid product object when
    # payload["status"] is not necessarily required here.
    #
    # We therefore check the actual "product" object directly.

    product = payload.get("product")

    if not isinstance(product, dict):

        return None, "missing_product"

    return product, "success"


# ============================================================
# IMAGE EXTRACTION
# ============================================================

def extract_language_images(
    ingredients_section: dict,
) -> Dict[str, str]:
    """
    Extract language -> URL from:

    selected_images
        ingredients
            display
                fr: URL
                en: URL
                ...
    """

    if not isinstance(
        ingredients_section,
        dict,
    ):
        return {}

    display = ingredients_section.get(
        "display"
    )

    if not isinstance(
        display,
        dict,
    ):
        return {}

    result = {}

    for language, url in display.items():

        language = clean_string(
            language
        ).lower()

        url = clean_string(url)

        if language and url:
            result[language] = url

    return result


def find_ingredients_image(
    product: dict,
    preferred_language: str,
) -> Optional[
    Tuple[str, str, str]
]:
    """
    Select the best ingredient image.

    Priority:
    1. Product language
    2. English
    3. Other available languages

    Returns:
        image_key,
        image_url,
        image_language
    """

    selected_images = product.get(
        "selected_images"
    )

    if not isinstance(
        selected_images,
        dict,
    ):
        return None

    ingredients = selected_images.get(
        "ingredients"
    )

    if not isinstance(
        ingredients,
        dict,
    ):
        return None

    language_images = extract_language_images(
        ingredients
    )

    if not language_images:
        return None

    preferred_language = clean_string(
        preferred_language
    ).lower()

    # --------------------------------------------------------
    # Product language
    # --------------------------------------------------------

    if preferred_language in language_images:

        return (
            f"ingredients_{preferred_language}",
            language_images[
                preferred_language
            ],
            preferred_language,
        )

    # --------------------------------------------------------
    # English
    # --------------------------------------------------------

    if "en" in language_images:

        return (
            "ingredients_en",
            language_images["en"],
            "en",
        )

    # --------------------------------------------------------
    # Other language
    # --------------------------------------------------------

    for language in sorted(
        language_images.keys()
    ):

        return (
            f"ingredients_{language}",
            language_images[language],
            language,
        )

    return None


# ============================================================
# IMAGE VALIDATION
# ============================================================

def validate_image_bytes(
    content: bytes,
) -> Optional[str]:
    """Detect common image formats."""

    if not content:
        return None

    if content.startswith(
        b"\xff\xd8\xff"
    ):
        return "jpg"

    if content.startswith(
        b"\x89PNG\r\n\x1a\n"
    ):
        return "png"

    if (
        content[:4] == b"RIFF"
        and content[8:12] == b"WEBP"
    ):
        return "webp"

    return None


def stable_filename(
    code: str,
    image_key: str,
    extension: str = "jpg",
) -> str:
    """Create deterministic image filename."""

    safe_code = "".join(
        character
        if character.isalnum()
        else "_"
        for character in code
    )

    digest = hashlib.sha1(
        f"{code}|{image_key}".encode(
            "utf-8"
        )
    ).hexdigest()[:8]

    return (
        f"{safe_code}_{digest}.{extension}"
    )


def download_image(
    url: str,
    output_path: Path,
) -> Tuple[
    bool,
    str,
    Optional[str],
]:
    """
    Download and validate image.

    Returns:
        success,
        status,
        detected_format
    """

    try:

        response = SESSION.get(
            url,
            timeout=DEFAULT_TIMEOUT,
        )

    except requests.RequestException as exc:

        return (
            False,
            f"request_error:{type(exc).__name__}",
            None,
        )

    if response.status_code != 200:

        return (
            False,
            f"http_{response.status_code}",
            None,
        )

    image_format = validate_image_bytes(
        response.content
    )

    if image_format is None:

        return (
            False,
            "invalid_image",
            None,
        )

    try:

        output_path.write_bytes(
            response.content
        )

    except OSError as exc:

        return (
            False,
            f"file_error:{type(exc).__name__}",
            None,
        )

    return (
        True,
        f"downloaded_{image_format}",
        image_format,
    )


# ============================================================
# SAMPLING
# ============================================================

def classify_product(
    row: pd.Series,
) -> List[str]:
    """Assign research sampling strata."""

    strata = []

    # Declared allergens.
    for allergen in sorted(
        row["target_allergens"]
    ):
        strata.append(
            f"allergen:{allergen}"
        )

    # Trace allergens.
    for allergen in sorted(
        row["target_trace_allergens"]
    ):
        strata.append(
            f"trace:{allergen}"
        )

    # Control.
    if not row["target_allergens"]:
        strata.append("control")

    # Language.
    language = clean_string(
        row["lang"]
    ).lower()

    if language in LANGUAGE_TARGETS:
        strata.append(
            f"language:{language}"
        )

    return strata


def build_candidate_pools(
    df: pd.DataFrame,
) -> Dict[str, List[int]]:
    """Build candidate pools."""

    pools: Dict[
        str,
        List[int]
    ] = {}

    for idx, row in df.iterrows():

        strata = classify_product(row)

        for stratum in strata:

            pools.setdefault(
                stratum,
                []
            ).append(idx)

    return pools


def sample_indices(
    df: pd.DataFrame,
    limit: int,
    seed: int,
) -> Tuple[
    List[int],
    dict,
]:
    """
    Stratified candidate selection.

    Allergen targets are automatically capped by
    actual dataset availability.
    """

    rng = random.Random(seed)

    pools = build_candidate_pools(df)

    selected = []
    selected_set = set()

    summary = {
        "requested_targets": {},
        "actual_targets": {},
        "selected_by_stratum": {},
    }

    # --------------------------------------------------------
    # Calculate actual attainable targets.
    # --------------------------------------------------------

    actual_targets = {}

    for allergen, requested in ALLERGEN_TARGETS.items():

        available = len(
            pools.get(
                f"allergen:{allergen}",
                []
            )
        )

        actual = min(
            requested,
            available,
        )

        actual_targets[allergen] = actual

        summary[
            "requested_targets"
        ][allergen] = requested

        summary[
            "actual_targets"
        ][allergen] = actual

    # --------------------------------------------------------
    # Helper
    # --------------------------------------------------------

    def take(
        pool_name: str,
        count: int,
    ) -> int:

        candidates = [
            idx
            for idx in pools.get(
                pool_name,
                []
            )
            if idx not in selected_set
        ]

        rng.shuffle(candidates)

        taken = 0

        for idx in candidates:

            if taken >= count:
                break

            if len(selected) >= limit:
                break

            selected.append(idx)
            selected_set.add(idx)
            taken += 1

        summary[
            "selected_by_stratum"
        ][pool_name] = taken

        return taken

    # --------------------------------------------------------
    # Rare allergens first.
    # --------------------------------------------------------

    allergen_order = sorted(
        actual_targets.keys(),
        key=lambda allergen: len(
            pools.get(
                f"allergen:{allergen}",
                []
            )
        ),
    )

    for allergen in allergen_order:

        take(
            f"allergen:{allergen}",
            actual_targets[allergen],
        )

    # --------------------------------------------------------
    # Trace samples.
    # --------------------------------------------------------

    trace_candidates = []

    for allergen in TARGET_ALLERGENS:

        trace_candidates.extend(
            pools.get(
                f"trace:{allergen}",
                []
            )
        )

    trace_candidates = list(
        dict.fromkeys(
            trace_candidates
        )
    )

    rng.shuffle(
        trace_candidates
    )

    trace_taken = 0

    for idx in trace_candidates:

        if len(selected) >= limit:
            break

        if trace_taken >= TRACE_TARGET:
            break

        if idx in selected_set:
            continue

        selected.append(idx)
        selected_set.add(idx)
        trace_taken += 1

    summary[
        "selected_by_stratum"
    ]["trace"] = trace_taken

    # --------------------------------------------------------
    # Controls.
    # --------------------------------------------------------

    take(
        "control",
        CONTROL_TARGET,
    )

    # --------------------------------------------------------
    # Language diversity.
    # --------------------------------------------------------

    language_order = sorted(
        LANGUAGE_TARGETS,
        key=lambda language: len(
            pools.get(
                f"language:{language}",
                []
            )
        ),
    )

    for language in language_order:

        if len(selected) >= limit:
            break

        candidates = [
            idx
            for idx in pools.get(
                f"language:{language}",
                []
            )
            if idx not in selected_set
        ]

        rng.shuffle(candidates)

        # At most 3 extra products per language
        # at this stage.
        for idx in candidates[:3]:

            if len(selected) >= limit:
                break

            if idx in selected_set:
                continue

            selected.append(idx)
            selected_set.add(idx)

            summary[
                "selected_by_stratum"
            ].setdefault(
                f"language:{language}",
                0,
            )

            summary[
                "selected_by_stratum"
            ][
                f"language:{language}"
            ] += 1

    # --------------------------------------------------------
    # Fill remaining capacity.
    # --------------------------------------------------------

    if len(selected) < limit:

        remaining = [
            idx
            for idx in df.index
            if idx not in selected_set
        ]

        rng.shuffle(remaining)

        for idx in remaining:

            if len(selected) >= limit:
                break

            selected.append(idx)
            selected_set.add(idx)

    # --------------------------------------------------------
    # Deterministic final shuffle.
    # --------------------------------------------------------

    rng.shuffle(selected)

    selected = selected[:limit]

    summary["total_selected"] = len(
        selected
    )

    return selected, summary


# ============================================================
# PROCESS PRODUCTS
# ============================================================

def process_selected_products(
    df: pd.DataFrame,
    selected_indices: List[int],
    delay: float,
) -> Tuple[
    List[dict],
    List[dict],
]:
    """Query and download selected products."""

    metadata_rows = []
    download_logs = []

    total = len(selected_indices)

    for position, idx in enumerate(
        selected_indices,
        start=1,
    ):

        row = df.loc[idx]

        code = clean_string(
            row["code"]
        )

        product_name = clean_string(
            row["product_name"]
        )

        product_language = clean_string(
            row["lang"]
        ).lower()

        reference_ingredients = clean_string(
            row["ingredients_text"]
        )

        allergen_tags = clean_string(
            row["allergens_tags"]
        )

        trace_tags = clean_string(
            row["traces_tags"]
        )

        declared_allergens = sorted(
            row["target_allergens"]
        )

        trace_allergens = sorted(
            row["target_trace_allergens"]
        )

        print()
        print(
            f"[{position}/{total}] "
            f"{code} | "
            f"{product_name[:70]}"
        )

        print(
            f"  Product language: "
            f"{product_language or 'unknown'}"
        )

        print(
            "  Declared allergens: "
            + (
                ", ".join(
                    declared_allergens
                )
                if declared_allergens
                else "none"
            )
        )

        print(
            "  Trace allergens: "
            + (
                ", ".join(
                    trace_allergens
                )
                if trace_allergens
                else "none"
            )
        )

        # ----------------------------------------------------
        # API
        # ----------------------------------------------------

        product, api_status = get_product(
            code
        )

        if product is None:

            print(
                f"  Result: API failed "
                f"({api_status})"
            )

            download_logs.append(
                {
                    "code": code,
                    "product_name": product_name,
                    "api_status": api_status,
                    "status": "api_failed",
                    "image_url": "",
                    "image_key": "",
                    "image_language": "",
                }
            )

            time.sleep(delay)
            continue

        print(
            "  API: success"
        )

        # ----------------------------------------------------
        # Ingredient image
        # ----------------------------------------------------

        image_info = find_ingredients_image(
            product,
            product_language,
        )

        if image_info is None:

            print(
                "  Result: "
                "no ingredient image"
            )

            download_logs.append(
                {
                    "code": code,
                    "product_name": product_name,
                    "api_status": api_status,
                    "status": "no_ingredient_image",
                    "image_url": "",
                    "image_key": "",
                    "image_language": "",
                }
            )

            time.sleep(delay)
            continue

        (
            image_key,
            image_url,
            image_language,
        ) = image_info

        print(
            f"  Image language: "
            f"{image_language or 'unknown'}"
        )

        print(
            f"  Image key: "
            f"{image_key}"
        )

        # ----------------------------------------------------
        # Download
        # ----------------------------------------------------

        # First download to memory through helper,
        # but use temporary deterministic jpg path.
        #
        # We do not know the final extension until validation.

        temp_path = (
            IMAGE_DIR
            / (
                stable_filename(
                    code,
                    image_key,
                    "tmp",
                )
            )
        )

        success, status, image_format = (
            download_image(
                image_url,
                temp_path,
            )
        )

        if not success:

            print(
                f"  Result: "
                f"download failed ({status})"
            )

            if temp_path.exists():
                temp_path.unlink()

            download_logs.append(
                {
                    "code": code,
                    "product_name": product_name,
                    "api_status": api_status,
                    "status": status,
                    "image_url": image_url,
                    "image_key": image_key,
                    "image_language": image_language,
                }
            )

            time.sleep(delay)
            continue

        # ----------------------------------------------------
        # Rename to actual extension.
        # ----------------------------------------------------

        final_filename = stable_filename(
            code,
            image_key,
            image_format or "jpg",
        )

        final_path = (
            IMAGE_DIR
            / final_filename
        )

        temp_path.replace(
            final_path
        )

        print(
            f"  Result: "
            f"downloaded -> "
            f"{final_filename}"
        )

        # ----------------------------------------------------
        # Metadata
        # ----------------------------------------------------

        sampling_strata = classify_product(
            row
        )

        metadata_rows.append(
            {
                "code": code,
                "product_name": product_name,
                "product_language": product_language,
                "image_language": image_language,
                "ocr_language": (
                    image_language
                    or product_language
                    or "en"
                ),
                "image_path": str(
                    final_path.relative_to(
                        OUTPUT_DIR
                    )
                ),
                "image_url": image_url,
                "image_key": image_key,
                "reference_ingredients": (
                    reference_ingredients
                ),
                "allergens_tags": (
                    allergen_tags
                ),
                "traces_tags": (
                    trace_tags
                ),
                "reference_declared_allergens": (
                    "|".join(
                        declared_allergens
                    )
                ),
                "reference_trace_allergens": (
                    "|".join(
                        trace_allergens
                    )
                ),
                "has_declared_allergen": bool(
                    declared_allergens
                ),
                "has_trace_allergen": bool(
                    trace_allergens
                ),
                "sampling_strata": (
                    "|".join(
                        sampling_strata
                    )
                ),
                "seed": DEFAULT_SEED,
            }
        )

        download_logs.append(
            {
                "code": code,
                "product_name": product_name,
                "api_status": api_status,
                "status": status,
                "image_url": image_url,
                "image_key": image_key,
                "image_language": image_language,
                "filename": final_filename,
            }
        )

        time.sleep(delay)

    return (
        metadata_rows,
        download_logs,
    )


# ============================================================
# SUMMARY
# ============================================================

def create_summary(
    df: pd.DataFrame,
    metadata_df: pd.DataFrame,
    download_logs: List[dict],
    selected_count: int,
    seed: int,
    sampling_summary: dict,
) -> dict:

    downloaded = len(
        metadata_df
    )

    status_counts = {}

    for row in download_logs:

        status = row.get(
            "status",
            "unknown",
        )

        status_counts[status] = (
            status_counts.get(
                status,
                0,
            )
            + 1
        )

    summary = {
        "dataset": {
            "source_file": str(
                DATASET_PATH
            ),
            "eligible_products": int(
                len(df)
            ),
            "unique_product_codes": int(
                df["code"].nunique()
            ),
        },
        "benchmark": {
            "requested_candidates": int(
                selected_count
            ),
            "downloaded_images": int(
                downloaded
            ),
            "success_rate": (
                round(
                    downloaded
                    / selected_count,
                    4,
                )
                if selected_count
                else 0.0
            ),
            "seed": int(seed),
        },
        "sampling": sampling_summary,
        "download_status": status_counts,
    }

    if not metadata_df.empty:

        summary[
            "image_languages"
        ] = (
            metadata_df[
                "image_language"
            ]
            .fillna("")
            .astype(str)
            .value_counts()
            .to_dict()
        )

        summary[
            "product_languages"
        ] = (
            metadata_df[
                "product_language"
            ]
            .fillna("")
            .astype(str)
            .value_counts()
            .to_dict()
        )

        declared_counts = {}
        trace_counts = {}

        for allergen in TARGET_ALLERGENS:

            declared_counts[
                allergen
            ] = int(
                metadata_df[
                    "reference_declared_allergens"
                ]
                .fillna("")
                .astype(str)
                .str.split("|")
                .apply(
                    lambda values,
                    a=allergen:
                    a in values
                )
                .sum()
            )

            trace_counts[
                allergen
            ] = int(
                metadata_df[
                    "reference_trace_allergens"
                ]
                .fillna("")
                .astype(str)
                .str.split("|")
                .apply(
                    lambda values,
                    a=allergen:
                    a in values
                )
                .sum()
            )

        summary[
            "declared_allergen_coverage"
        ] = declared_counts

        summary[
            "trace_allergen_coverage"
        ] = trace_counts

    return summary


# ============================================================
# MAIN
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Download a stratified "
            "Open Food Facts OCR benchmark."
        )
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=(
            "Number of candidate products "
            f"(default: {DEFAULT_LIMIT})"
        ),
    )

    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY,
        help=(
            "Delay between API calls "
            f"(default: {DEFAULT_DELAY})"
        ),
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help=(
            "Random seed "
            f"(default: {DEFAULT_SEED})"
        ),
    )

    args = parser.parse_args()

    if args.limit <= 0:
        raise ValueError(
            "--limit must be greater than 0"
        )

    if args.delay < 0:
        raise ValueError(
            "--delay cannot be negative"
        )

    # --------------------------------------------------------
    # Directories
    # --------------------------------------------------------

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    IMAGE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # --------------------------------------------------------
    # Header
    # --------------------------------------------------------

    print("=" * 70)
    print(
        "WAIT WHAT'S IN THIS?"
    )
    print(
        "STRATIFIED OCR BENCHMARK DOWNLOADER"
    )
    print("=" * 70)

    print()
    print(
        f"Dataset: {DATASET_PATH}"
    )

    print(
        f"Requested candidates: "
        f"{args.limit}"
    )

    print(
        f"Random seed: {args.seed}"
    )

    print(
        f"API delay: {args.delay}s"
    )

    # --------------------------------------------------------
    # Dataset
    # --------------------------------------------------------

    df = load_dataset()

    print()
    print(
        "Eligible products with "
        f"ingredient text: {len(df)}"
    )

    # --------------------------------------------------------
    # Language distribution
    # --------------------------------------------------------

    print()
    print(
        "SOURCE LANGUAGE DISTRIBUTION"
    )
    print("-" * 40)

    languages = (
        df["lang"]
        .fillna("")
        .astype(str)
        .str.lower()
        .value_counts()
    )

    for language, count in languages.head(20).items():

        print(
            f"{language or 'unknown':10s} "
            f"{count:5d}"
        )

    # --------------------------------------------------------
    # Allergen availability
    # --------------------------------------------------------

    print()
    print(
        "SOURCE ALLERGEN AVAILABILITY"
    )
    print("-" * 40)

    for allergen, tag in TARGET_ALLERGENS.items():

        available = int(
            df["target_allergens"]
            .apply(
                lambda values,
                a=allergen:
                a in values
            )
            .sum()
        )

        requested = ALLERGEN_TARGETS[
            allergen
        ]

        actual = min(
            available,
            requested,
        )

        print(
            f"{allergen:15s} "
            f"{available:5d} available, "
            f"target {requested:3d}, "
            f"using {actual:3d}"
        )

    # --------------------------------------------------------
    # Selection
    # --------------------------------------------------------

    print()
    print(
        "SELECTING STRATIFIED CANDIDATES..."
    )
    print("-" * 40)

    selected_indices, sampling_summary = (
        sample_indices(
            df,
            args.limit,
            args.seed,
        )
    )

    print(
        f"Selected {len(selected_indices)} "
        "unique candidates."
    )

    # --------------------------------------------------------
    # Download
    # --------------------------------------------------------

    print()
    print(
        "DOWNLOADING INGREDIENT IMAGES"
    )
    print("-" * 40)

    metadata_rows, download_logs = (
        process_selected_products(
            df,
            selected_indices,
            args.delay,
        )
    )

    metadata_df = pd.DataFrame(
        metadata_rows
    )

    # --------------------------------------------------------
    # Save metadata
    # --------------------------------------------------------

    metadata_df.to_csv(
        METADATA_PATH,
        index=False,
    )

    pd.DataFrame(
        download_logs
    ).to_csv(
        DOWNLOAD_LOG_PATH,
        index=False,
    )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    summary = create_summary(
        df=df,
        metadata_df=metadata_df,
        download_logs=download_logs,
        selected_count=len(
            selected_indices
        ),
        seed=args.seed,
        sampling_summary=sampling_summary,
    )

    with open(
        SUMMARY_PATH,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            summary,
            file,
            indent=2,
            ensure_ascii=False,
        )

    # --------------------------------------------------------
    # Final report
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print(
        "BENCHMARK DOWNLOAD COMPLETE"
    )
    print("=" * 70)

    print(
        f"Candidates selected : "
        f"{len(selected_indices)}"
    )

    print(
        f"Images downloaded   : "
        f"{len(metadata_df)}"
    )

    print(
        f"Images unavailable  : "
        f"{len(selected_indices) - len(metadata_df)}"
    )

    if selected_indices:

        print(
            f"Success rate        : "
            f"{len(metadata_df) / len(selected_indices):.2%}"
        )

    print()
    print("Output files:")

    print(
        f"  Images       : {IMAGE_DIR}"
    )

    print(
        f"  Metadata     : {METADATA_PATH}"
    )

    print(
        f"  Download log : {DOWNLOAD_LOG_PATH}"
    )

    print(
        f"  Summary      : {SUMMARY_PATH}"
    )

    # --------------------------------------------------------
    # Language distribution
    # --------------------------------------------------------

    if not metadata_df.empty:

        print()
        print(
            "ACTUAL INGREDIENT IMAGE LANGUAGES"
        )
        print("-" * 40)

        image_languages = (
            metadata_df[
                "image_language"
            ]
            .fillna("")
            .astype(str)
            .value_counts()
        )

        for language, count in (
            image_languages.items()
        ):

            print(
                f"{language or 'unknown':10s} "
                f"{count:5d}"
            )

        # ----------------------------------------------------
        # Allergen coverage
        # ----------------------------------------------------

        print()
        print(
            "DOWNLOADED DECLARED ALLERGEN COVERAGE"
        )
        print("-" * 40)

        for allergen in TARGET_ALLERGENS:

            count = int(
                metadata_df[
                    "reference_declared_allergens"
                ]
                .fillna("")
                .astype(str)
                .str.split("|")
                .apply(
                    lambda values,
                    a=allergen:
                    a in values
                )
                .sum()
            )

            print(
                f"{allergen:15s} "
                f"{count:5d}"
            )

    print()
    print(
        "IMPORTANT: "
        "Open Food Facts metadata is reference metadata. "
        "Manually verify the final benchmark before using "
        "it as definitive ground truth."
    )


if __name__ == "__main__":
    main()