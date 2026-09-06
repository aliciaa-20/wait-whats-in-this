#!/usr/bin/env python3

import json
import time
from pathlib import Path

import pandas as pd
import requests


DATASET_PATH = Path("data/cleaned_products.csv")
OUTPUT_PATH = Path("data/benchmark/image_availability.csv")

API_URL = "https://world.openfoodfacts.org/api/v3/product"

USER_AGENT = (
    "WaitWhatsInThis/1.0 "
    "(educational research project; "
    "https://github.com/aliciaa-20/wait-whats-in-this)"
)

DELAY = 1.5
TIMEOUT = 30


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


session = requests.Session()

session.headers.update(
    {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }
)


def clean(value):
    if value is None:
        return ""

    if isinstance(value, float) and pd.isna(value):
        return ""

    return str(value).strip()


def parse_tags(value):
    text = clean(value)

    if not text:
        return []

    if text.startswith("[") and text.endswith("]"):
        try:
            parsed = json.loads(
                text.replace("'", '"')
            )

            if isinstance(parsed, list):
                return [
                    str(x).strip().lower()
                    for x in parsed
                    if str(x).strip()
                ]

        except Exception:
            pass

    for separator in [";", "|", ","]:
        if separator in text:
            return [
                x.strip().lower()
                for x in text.split(separator)
                if x.strip()
            ]

    return [text.lower()]


def allergen_ids(tags):
    result = []

    tag_set = set(tags)

    for allergen, off_tag in TARGET_ALLERGENS.items():

        if off_tag in tag_set:
            result.append(allergen)

    return sorted(result)


def get_product(code):

    url = f"{API_URL}/{code}"

    params = {
        "product_type": "all",
        "fields": (
            "code,product_name,lang,"
            "ingredients_text,allergens_tags,"
            "traces_tags,selected_images"
        ),
    }

    try:

        response = session.get(
            url,
            params=params,
            timeout=TIMEOUT,
        )

    except requests.RequestException as exc:

        return None, (
            "request_error:"
            f"{type(exc).__name__}"
        )

    if response.status_code != 200:

        return None, (
            f"http_{response.status_code}"
        )

    try:

        payload = response.json()

    except ValueError:

        return None, "invalid_json"

    product = payload.get("product")

    if not isinstance(product, dict):

        return None, "missing_product"

    return product, "success"


def get_image_languages(product):

    selected_images = product.get(
        "selected_images"
    )

    if not isinstance(
        selected_images,
        dict,
    ):
        return {}

    ingredients = selected_images.get(
        "ingredients"
    )

    if not isinstance(
        ingredients,
        dict,
    ):
        return {}

    display = ingredients.get(
        "display"
    )

    if not isinstance(
        display,
        dict,
    ):
        return {}

    return {
        str(language).lower(): clean(url)
        for language, url in display.items()
        if clean(url)
    }


def main():

    df = pd.read_csv(
        DATASET_PATH
    )

    df["code"] = (
        df["code"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    df["ingredients_text"] = (
        df["ingredients_text"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    df = df[
        (df["code"] != "")
        &
        (df["ingredients_text"] != "")
    ].copy()

    df = df.drop_duplicates(
        "code"
    ).reset_index(drop=True)

    print(
        f"Eligible products: {len(df)}"
    )

    results = []

    for i, row in df.iterrows():

        code = row["code"]

        print(
            f"[{i + 1}/{len(df)}] "
            f"{code}"
        )

        product, status = get_product(
            code
        )

        if product is None:

            results.append(
                {
                    "code": code,
                    "product_name": clean(
                        row["product_name"]
                    ),
                    "product_language": clean(
                        row["lang"]
                    ).lower(),
                    "api_status": status,
                    "has_ingredient_image": False,
                    "image_languages": "",
                    "declared_allergens": "",
                    "trace_allergens": "",
                }
            )

            time.sleep(DELAY)
            continue

        image_languages = (
            get_image_languages(
                product
            )
        )

        allergens = allergen_ids(
            parse_tags(
                row["allergens_tags"]
            )
        )

        traces = allergen_ids(
            parse_tags(
                row["traces_tags"]
            )
        )

        results.append(
            {
                "code": code,
                "product_name": clean(
                    row["product_name"]
                ),
                "product_language": clean(
                    row["lang"]
                ).lower(),
                "api_status": status,
                "has_ingredient_image": bool(
                    image_languages
                ),
                "image_languages": "|".join(
                    sorted(
                        image_languages.keys()
                    )
                ),
                "declared_allergens": "|".join(
                    allergens
                ),
                "trace_allergens": "|".join(
                    traces
                ),
            }
        )

        time.sleep(DELAY)

    result_df = pd.DataFrame(
        results
    )

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    result_df.to_csv(
        OUTPUT_PATH,
        index=False,
    )

    print()
    print("=" * 60)
    print("IMAGE AVAILABILITY SUMMARY")
    print("=" * 60)

    print(
        "Total checked:",
        len(result_df)
    )

    print(
        "API successful:",
        (
            result_df["api_status"]
            == "success"
        ).sum()
    )

    print(
        "Ingredient images:",
        result_df[
            "has_ingredient_image"
        ].sum()
    )

    print(
        "No ingredient image:",
        (
            ~result_df[
                "has_ingredient_image"
            ]
        ).sum()
    )

    available = result_df[
        result_df[
            "has_ingredient_image"
        ]
    ]

    print()
    print(
        "AVAILABLE IMAGE LANGUAGES"
    )

    language_counts = {}

    for languages in available[
        "image_languages"
    ].fillna(""):

        for language in languages.split("|"):

            if not language:
                continue

            language_counts[
                language
            ] = language_counts.get(
                language,
                0,
            ) + 1

    for language, count in sorted(
        language_counts.items(),
        key=lambda x: -x[1],
    ):

        print(
            f"{language:10s} {count}"
        )

    print()
    print(
        "DECLARED ALLERGEN AVAILABILITY"
    )

    for allergen in TARGET_ALLERGENS:

        count = (
            available[
                "declared_allergens"
            ]
            .fillna("")
            .str.split("|")
            .apply(
                lambda values,
                a=allergen:
                a in values
            )
            .sum()
        )

        print(
            f"{allergen:15s} {count}"
        )

    print()
    print(
        "TRACE ALLERGEN AVAILABILITY"
    )

    for allergen in TARGET_ALLERGENS:

        count = (
            available[
                "trace_allergens"
            ]
            .fillna("")
            .str.split("|")
            .apply(
                lambda values,
                a=allergen:
                a in values
            )
            .sum()
        )

        print(
            f"{allergen:15s} {count}"
        )

    print()
    print(
        f"Saved: {OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()