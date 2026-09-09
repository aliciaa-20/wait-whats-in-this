import json
from pathlib import Path

import pandas as pd


INPUT_FILE = Path(
    "data/benchmark/image_availability.csv"
)

OUTPUT_FILE = Path(
    "data/benchmark/ocr_candidates.csv"
)

SUMMARY_FILE = Path(
    "data/benchmark/ocr_candidates_summary.json"
)

SEED = 42
TARGET = 50

# Controlled final-benchmark language distribution.
# Each product is selected FOR one specific language, and that
# language is the one whose ingredient image will be downloaded -
# not "any language this product happens to have available."
LANGUAGE_TARGETS = [
    ("fr", 20),
    ("en", 10),
    ("de", 5),
    ("es", 5),
    ("nl", 4),
    ("it", 3),
    ("pt", 3),
]


def split_values(value):
    if pd.isna(value):
        return []

    value = str(value).strip()

    if not value:
        return []

    return [
        x.strip()
        for x in value.split("|")
        if x.strip()
    ]


def has_value(value):
    return bool(split_values(value))


def main():

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Missing {INPUT_FILE}"
        )

    df = pd.read_csv(INPUT_FILE)

    # Only products with ingredient images.
    df = df[
        df["has_ingredient_image"].astype(bool)
    ].copy()

    # Avoid the 18 images already used in the smoke benchmark.
    existing_metadata = Path(
        "data/benchmark/metadata.csv"
    )

    if existing_metadata.exists():

        existing = pd.read_csv(
            existing_metadata
        )

        existing_codes = set(
            existing["code"]
            .astype(str)
        )

        df = df[
            ~df["code"].astype(str).isin(
                existing_codes
            )
        ].copy()

    requested_total = sum(
        amount for _, amount in LANGUAGE_TARGETS
    )

    if requested_total != TARGET:
        raise ValueError(
            "LANGUAGE_TARGETS must sum to TARGET "
            f"({requested_total} != {TARGET})"
        )

    # --------------------------------------------------------
    # Add selection features
    # --------------------------------------------------------

    df["image_language_list"] = df[
        "image_languages"
    ].apply(split_values)

    df["declared_list"] = df[
        "declared_allergens"
    ].apply(split_values)

    df["trace_list"] = df[
        "trace_allergens"
    ].apply(split_values)

    df["has_declared"] = df[
        "declared_allergens"
    ].apply(has_value)

    df["has_trace"] = df[
        "trace_allergens"
    ].apply(has_value)

    df["has_both"] = (
        df["has_declared"]
        & df["has_trace"]
    )

    # Prefer research-relevant rows within each language bucket:
    # products that carry declared and/or trace allergen metadata
    # are more useful for the OCR -> allergen evaluation than
    # products with neither. This is a soft preference, not a
    # hard filter - "neither" products are still eligible so the
    # benchmark also covers true-negative cases.
    def relevance_rank(row):
        if row["has_both"]:
            return 0
        if row["has_declared"]:
            return 1
        if row["has_trace"]:
            return 2
        return 3

    df["relevance_rank"] = df.apply(
        relevance_rank,
        axis=1,
    )

    # --------------------------------------------------------
    # Controlled per-language sampling
    #
    # A product is selected FOR exactly one target language: the
    # language it will be downloaded in. This guarantees the final
    # benchmark's language distribution matches LANGUAGE_TARGETS
    # exactly (subject to availability), instead of being an
    # incidental byproduct of unrelated stratified sampling.
    # --------------------------------------------------------

    used_codes = set()
    selected_rows = []
    shortfalls = {}

    for language, amount in LANGUAGE_TARGETS:

        pool = df[
            df["image_language_list"].apply(
                lambda langs, lang=language: lang in langs
            )
            & ~df["code"].astype(str).isin(used_codes)
        ].copy()

        pool = pool.sort_values(
            by=["relevance_rank", "code"]
        )

        if len(pool) < amount:
            shortfalls[language] = {
                "requested": amount,
                "available": len(pool),
            }

        chosen = pool.sample(
            n=min(amount, len(pool)),
            random_state=SEED,
        ) if len(pool) else pool

        chosen = chosen.copy()
        chosen["target_language"] = language

        for code in chosen["code"].astype(str):
            used_codes.add(code)

        selected_rows.append(chosen)

    selected_df = pd.concat(
        selected_rows,
        ignore_index=True,
    )

    if shortfalls:
        print(
            "WARNING: not enough eligible products for "
            "some language targets:"
        )
        for language, info in shortfalls.items():
            print(
                f"  {language}: requested "
                f"{info['requested']}, only "
                f"{info['available']} available"
            )
        print(
            f"Selected {len(selected_df)}/{TARGET} "
            "total (shortfall not backfilled from other "
            "languages, to keep the distribution honest)."
        )

    # --------------------------------------------------------
    # Finalize
    # --------------------------------------------------------

    selected_df = selected_df.drop_duplicates(
        subset=["code"]
    )

    selected_df = selected_df.sort_values(
        by=["target_language", "code"]
    ).reset_index(drop=True)

    # Don't save helper columns.
    output_columns = [
        "code",
        "product_name",
        "product_language",
        "target_language",
        "image_languages",
        "has_ingredient_image",
        "declared_allergens",
        "trace_allergens",
    ]

    selected_df[
        output_columns
    ].to_csv(
        OUTPUT_FILE,
        index=False,
    )

    # Summary.
    target_language_counts = (
        selected_df["target_language"]
        .value_counts()
        .to_dict()
    )

    summary = {
        "seed": SEED,
        "target": TARGET,
        "selected": len(selected_df),
        "excluded_existing_smoke_benchmark": True,
        "language_targets": dict(LANGUAGE_TARGETS),
        "target_language_counts": {
            language: int(count)
            for language, count in sorted(
                target_language_counts.items(),
                key=lambda x: (-x[1], x[0]),
            )
        },
        "shortfalls": shortfalls,
        "declared_products": int(
            selected_df["has_declared"].sum()
            if "has_declared" in selected_df.columns
            else selected_df["declared_allergens"].notna().sum()
        ),
        "trace_products": int(
            selected_df[
                "trace_allergens"
            ].notna().sum()
        ),
        "both_products": int(
            (
                selected_df[
                    "declared_allergens"
                ].notna()
                &
                selected_df[
                    "trace_allergens"
                ].notna()
            ).sum()
        ),
        "neither_products": int(
            (
                selected_df[
                    "declared_allergens"
                ].isna()
                &
                selected_df[
                    "trace_allergens"
                ].isna()
            ).sum()
        ),
    }

    with open(
        SUMMARY_FILE,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            summary,
            f,
            indent=2,
            ensure_ascii=False,
        )

    print()
    print("=" * 70)
    print("OCR BENCHMARK CANDIDATE SELECTION")
    print("=" * 70)
    print(
        f"Eligible products: "
        f"{len(df)}"
    )
    print(
        f"Selected: "
        f"{len(selected_df)}"
    )

    print()
    print("Target language counts (image to be downloaded):")
    for language, count in sorted(
        target_language_counts.items(),
        key=lambda x: (-x[1], x[0]),
    ):
        print(
            f"  {language}: {count}"
        )

    print()
    print(
        f"Declared products: "
        f"{summary['declared_products']}"
    )
    print(
        f"Trace products: "
        f"{summary['trace_products']}"
    )
    print(
        f"Both: "
        f"{summary['both_products']}"
    )
    print(
        f"Neither: "
        f"{summary['neither_products']}"
    )

    print()
    print(
        f"Candidates saved to: "
        f"{OUTPUT_FILE}"
    )

    print(
        f"Summary saved to: "
        f"{SUMMARY_FILE}"
    )


if __name__ == "__main__":
    main()
