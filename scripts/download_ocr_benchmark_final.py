#!/usr/bin/env python3

"""
Download the final ~50-image OCR benchmark selected by
select_ocr_benchmark.py.

Unlike download_ocr_dataset.py (which picks an ingredient image by
priority: product language -> English -> any available language),
this script downloads EXACTLY the language recorded in the
"target_language" column of data/benchmark/ocr_candidates.csv for
each product. If that specific language image is no longer available
at download time, the product is skipped and logged as a failure -
it is never silently substituted with a different language, since
that would break the controlled language distribution.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd
import requests


CANDIDATES_PATH = Path("data/benchmark/ocr_candidates.csv")

OUTPUT_DIR = Path("data/benchmark")
IMAGE_DIR = OUTPUT_DIR / "final_images"

METADATA_PATH = OUTPUT_DIR / "final_benchmark_metadata.csv"
DOWNLOAD_LOG_PATH = OUTPUT_DIR / "final_download_log.csv"
SUMMARY_PATH = OUTPUT_DIR / "final_download_summary.json"

API_URL = "https://world.openfoodfacts.org/api/v3/product"

USER_AGENT = (
    "WaitWhatsInThis/1.0 "
    "(educational research project; "
    "https://github.com/aliciaa-20/wait-whats-in-this)"
)

DELAY = 2.5
TIMEOUT = 30

API_FIELDS = [
    "code",
    "product_name",
    "lang",
    "ingredients_text",
    "ingredients_text_en",
    "ingredients_text_fr",
    "ingredients_text_de",
    "ingredients_text_es",
    "ingredients_text_it",
    "ingredients_text_nl",
    "ingredients_text_pt",
    "allergens_tags",
    "traces_tags",
    "selected_images",
]

SESSION = requests.Session()
SESSION.headers.update(
    {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }
)


def clean_string(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    return str(value).strip()


def get_product(code: str) -> Tuple[Optional[dict], str]:

    url = f"{API_URL}/{code}"
    params = {
        "product_type": "all",
        "fields": ",".join(API_FIELDS),
    }

    try:
        response = SESSION.get(url, params=params, timeout=TIMEOUT)
    except requests.RequestException as exc:
        return None, f"request_error:{type(exc).__name__}"

    if response.status_code != 200:
        return None, f"http_{response.status_code}"

    try:
        payload = response.json()
    except ValueError:
        return None, "invalid_json"

    product = payload.get("product")

    if not isinstance(product, dict):
        return None, "missing_product"

    return product, "success"


def get_target_language_image_url(
    product: dict,
    target_language: str,
) -> Optional[str]:
    """
    Return the ingredients image URL for EXACTLY target_language,
    or None if that specific language is not available.
    """

    selected_images = product.get("selected_images")
    if not isinstance(selected_images, dict):
        return None

    ingredients = selected_images.get("ingredients")
    if not isinstance(ingredients, dict):
        return None

    display = ingredients.get("display")
    if not isinstance(display, dict):
        return None

    url = display.get(target_language)
    return clean_string(url) or None


def get_reference_ingredients(
    product: dict,
    target_language: str,
) -> str:
    """Prefer the language-specific ingredient text field if present."""

    field = f"ingredients_text_{target_language}"
    value = clean_string(product.get(field))

    if value:
        return value

    return clean_string(product.get("ingredients_text"))


def validate_image_bytes(content: bytes) -> Optional[str]:
    if not content:
        return None
    if content.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "webp"
    return None


def stable_filename(
    code: str,
    target_language: str,
    extension: str,
) -> str:
    safe_code = "".join(
        c if c.isalnum() else "_" for c in code
    )
    digest = hashlib.sha1(
        f"{code}|{target_language}".encode("utf-8")
    ).hexdigest()[:8]
    return f"{safe_code}_{target_language}_{digest}.{extension}"


def download_image(
    url: str,
    output_path: Path,
) -> Tuple[bool, str, Optional[str]]:

    try:
        response = SESSION.get(url, timeout=TIMEOUT)
    except requests.RequestException as exc:
        return False, f"request_error:{type(exc).__name__}", None

    if response.status_code != 200:
        return False, f"http_{response.status_code}", None

    image_format = validate_image_bytes(response.content)
    if image_format is None:
        return False, "invalid_image", None

    try:
        output_path.write_bytes(response.content)
    except OSError as exc:
        return False, f"file_error:{type(exc).__name__}", None

    return True, f"downloaded_{image_format}", image_format


def main():

    if not CANDIDATES_PATH.exists():
        raise FileNotFoundError(
            f"Missing {CANDIDATES_PATH}. "
            "Run scripts/select_ocr_benchmark.py first."
        )

    IMAGE_DIR.mkdir(parents=True, exist_ok=True)

    candidates = pd.read_csv(CANDIDATES_PATH)

    required = {"code", "target_language"}
    missing = required - set(candidates.columns)
    if missing:
        raise ValueError(
            f"ocr_candidates.csv is missing columns: {missing}. "
            "Re-run scripts/select_ocr_benchmark.py."
        )

    metadata_rows = []
    download_logs = []

    total = len(candidates)

    for position, row in enumerate(
        candidates.itertuples(index=False), start=1
    ):

        code = clean_string(row.code)
        target_language = clean_string(
            row.target_language
        ).lower()

        print()
        print(f"[{position}/{total}] {code} -> {target_language}")

        product, api_status = get_product(code)

        if product is None:
            print(f"  Result: API failed ({api_status})")
            download_logs.append(
                {
                    "code": code,
                    "target_language": target_language,
                    "api_status": api_status,
                    "status": "api_failed",
                }
            )
            time.sleep(DELAY)
            continue

        image_url = get_target_language_image_url(
            product, target_language
        )

        if not image_url:
            print(
                f"  Result: target-language image no longer "
                f"available ({target_language})"
            )
            download_logs.append(
                {
                    "code": code,
                    "target_language": target_language,
                    "api_status": api_status,
                    "status": "target_language_unavailable",
                }
            )
            time.sleep(DELAY)
            continue

        temp_path = IMAGE_DIR / stable_filename(
            code, target_language, "tmp"
        )

        success, status, image_format = download_image(
            image_url, temp_path
        )

        if not success:
            print(f"  Result: download failed ({status})")
            if temp_path.exists():
                temp_path.unlink()
            download_logs.append(
                {
                    "code": code,
                    "target_language": target_language,
                    "api_status": api_status,
                    "status": status,
                    "image_url": image_url,
                }
            )
            time.sleep(DELAY)
            continue

        final_filename = stable_filename(
            code, target_language, image_format or "jpg"
        )
        final_path = IMAGE_DIR / final_filename
        temp_path.replace(final_path)

        print(f"  Result: downloaded -> {final_filename}")

        reference_ingredients = get_reference_ingredients(
            product, target_language
        )

        metadata_rows.append(
            {
                "code": code,
                "product_name": clean_string(row.product_name),
                "product_language": clean_string(
                    getattr(row, "product_language", "")
                ),
                "target_language": target_language,
                "image_path": str(
                    final_path.relative_to(OUTPUT_DIR)
                ),
                "image_url": image_url,
                "reference_ingredients": reference_ingredients,
                "declared_allergens": clean_string(
                    getattr(row, "declared_allergens", "")
                ),
                "trace_allergens": clean_string(
                    getattr(row, "trace_allergens", "")
                ),
                # Filled in during manual verification - do not
                # auto-populate from OFF metadata, since this file
                # exists specifically to hold the visible, manually
                # transcribed ingredient-section ground truth.
                "manual_transcription": "",
                "manual_transcription_notes": "",
            }
        )

        download_logs.append(
            {
                "code": code,
                "target_language": target_language,
                "api_status": api_status,
                "status": status,
                "image_url": image_url,
                "filename": final_filename,
            }
        )

        time.sleep(DELAY)

    metadata_df = pd.DataFrame(metadata_rows)
    metadata_df.to_csv(METADATA_PATH, index=False)
    pd.DataFrame(download_logs).to_csv(DOWNLOAD_LOG_PATH, index=False)

    summary = {
        "requested": total,
        "downloaded": len(metadata_df),
        "failed": total - len(metadata_df),
        "by_target_language": (
            metadata_df["target_language"]
            .value_counts()
            .to_dict()
            if not metadata_df.empty
            else {}
        ),
    }

    with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print()
    print("=" * 70)
    print("FINAL OCR BENCHMARK DOWNLOAD COMPLETE")
    print("=" * 70)
    print(f"Requested  : {total}")
    print(f"Downloaded : {len(metadata_df)}")
    print(f"Failed     : {total - len(metadata_df)}")
    print()
    print(f"Images   : {IMAGE_DIR}")
    print(f"Metadata : {METADATA_PATH}")
    print(f"Log      : {DOWNLOAD_LOG_PATH}")
    print()
    print(
        "NEXT STEP: manually verify/transcribe the visible "
        "ingredient section for each image and fill in the "
        "'manual_transcription' column in "
        f"{METADATA_PATH}. This is the OCR ground truth."
    )


if __name__ == "__main__":
    main()
