"""
Phase 8 data-expansion: builds the OCR-expansion evaluation set from the
47 new candidate images + manual transcriptions
(data/research/ml/ocr_expansion_v1/manual_annotations.py).

Does NOT touch the original frozen 39-image benchmark
(data/benchmark/final_images/, final_benchmark_metadata.csv,
final_ocr_results.csv) - everything here is self-contained under
data/research/ml/ocr_expansion_v1/, and gets combined with the frozen
set only in-memory for evaluation, never by overwriting it.

For each usable new image, runs the real EasyOCR pipeline
(scripts.ocr_processor.process_image) to get actual OCR text/confidence,
then runs the matcher (scripts.allergen_matcher.analyze_ingredient_text)
against both the OCR output and the manual (clean) transcription, mirroring
final_ocr_results.csv's structure exactly so the two sets can be combined.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd

from scripts.ocr_processor import process_image
from scripts.allergen_matcher import analyze_ingredient_text, load_dictionary

BASE_DIR = Path(__file__).resolve().parent.parent
SOURCE_IMAGE_DIR = BASE_DIR / "data" / "benchmark" / "images"
BENCHMARK_METADATA = BASE_DIR / "data" / "benchmark" / "metadata.csv"

OUTPUT_DIR = BASE_DIR / "data" / "research" / "ml" / "ocr_expansion_v1"
IMAGE_DIR = OUTPUT_DIR / "images"


def load_annotations():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "manual_annotations", OUTPUT_DIR / "manual_annotations.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.RECORDS


def split_set(value):
    return set(v for v in str(value or "").split("|") if v)


def main():
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)

    records = load_annotations()
    meta = pd.read_csv(BENCHMARK_METADATA, dtype={"code": str})
    meta = meta.set_index("code")

    dictionary = load_dictionary()

    rows = []
    excluded = []

    for rec in records:
        code = rec["code"]

        if rec["quality"] == "excluded":
            excluded.append({"code": code, "reason": rec["notes"]})
            continue

        meta_row = meta.loc[code]
        image_rel_path = meta_row["image_path"]
        image_language = str(meta_row.get("image_language", "fr") or "fr").lower()
        product_name = meta_row.get("product_name", "")

        src_image = SOURCE_IMAGE_DIR / Path(image_rel_path).name
        dst_image = IMAGE_DIR / Path(image_rel_path).name
        if not dst_image.exists():
            shutil.copy2(src_image, dst_image)

        # --- Real OCR pipeline ---
        ocr_result = process_image(dst_image, language=image_language)
        ocr_text = ocr_result.get("ingredient_text", "")
        ocr_confidence = ocr_result.get("ocr_confidence", 0.0)
        extraction_found = ocr_result.get("ingredient_section_found", False)

        ocr_match = analyze_ingredient_text(ocr_text, dictionary) if ocr_text.strip() else {
            "declared_allergens": [], "trace_allergens": [],
        }

        # --- Clean (manually transcribed) text, matcher upper bound ---
        clean_text = rec["transcription"]
        clean_match = analyze_ingredient_text(clean_text, dictionary)

        rows.append({
            "code": code,
            "product_name": product_name,
            "target_language": image_language,
            "image_path": f"images/{Path(image_rel_path).name}",
            "ocr_confidence": ocr_confidence,
            "extraction_found": extraction_found,
            "manual_transcription": clean_text,
            "manual_transcription_notes": rec["notes"],
            "reference_declared_allergens": rec["declared"],
            "reference_trace_allergens": rec["trace"],
            "ocr_declared_allergens": "|".join(sorted(ocr_match["declared_allergens"])),
            "ocr_trace_allergens": "|".join(sorted(ocr_match["trace_allergens"])),
            "clean_declared_allergens": "|".join(sorted(clean_match["declared_allergens"])),
            "clean_trace_allergens": "|".join(sorted(clean_match["trace_allergens"])),
            "annotation_status": "complete",
        })

        print(f"{code}: OCR conf={ocr_confidence:.3f} "
              f"ocr_declared={sorted(ocr_match['declared_allergens'])} "
              f"clean_declared={sorted(clean_match['declared_allergens'])} "
              f"ref_declared={rec['declared']}")

    df = pd.DataFrame(rows)
    out_file = OUTPUT_DIR / "expansion_ocr_results.csv"
    df.to_csv(out_file, index=False)

    summary = {
        "total_candidates": len(records),
        "usable": len(rows),
        "excluded": len(excluded),
        "excluded_detail": excluded,
    }
    with (OUTPUT_DIR / "expansion_summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(f"\nUsable: {len(rows)}, Excluded: {len(excluded)}")
    print(f"Saved: {out_file}")


if __name__ == "__main__":
    main()
