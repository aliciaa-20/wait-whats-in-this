"""
End-to-end food-label analysis.

Pipeline:
Image -> OCR -> ingredient extraction -> allergen matcher -> result

This module intentionally contains orchestration only.
OCR logic remains in ocr_processor.py and allergen logic remains
in allergen_matcher.py.
"""

import argparse
import json
from pathlib import Path
import sys


BASE_DIR = Path(__file__).resolve().parents[1]

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from scripts.ocr_processor import process_image
from scripts.allergen_matcher import (
    analyze_ingredient_text,
    load_dictionary,
)


def analyze_label(image_path, language="en", dictionary=None):
    """
    Run the complete OCR -> allergen analysis pipeline.

    Parameters:
        image_path: Path to the food-label image.
        language: OCR language code, e.g. en, fr, de, es, nl, it, pt, ar.
        dictionary: Optional allergen dictionary.

    Returns:
        JSON-serializable dictionary.
    """
    image_path = Path(image_path)

    if not image_path.exists():
        raise FileNotFoundError(
            f"Image does not exist: {image_path}"
        )

    if dictionary is None:
        dictionary = load_dictionary()

    ocr_result = process_image(
        image_path,
        language=language,
    )

    ingredient_text = ocr_result.get(
        "ingredient_text",
        "",
    )

    # Do not treat an OCR/extraction failure as a safe result.
    # SAFE is only valid when ingredient text was successfully extracted.
    extraction_status = (
        "FOUND"
        if ingredient_text.strip()
        else "NOT_FOUND"
    )

    unknown_reason = None
    unknown_message = None

    if extraction_status == "NOT_FOUND":
        allergen_result = {
            "declared_text": "",
            "trace_text": "",
            "declared_allergens": [],
            "trace_allergens": [],
            "matches": [],
            "trace_matches": [],
            "risk": "UNKNOWN",
        }

        # Distinguish *why* nothing was extracted instead of collapsing
        # every failure into one generic "not found" state - each case
        # below points the user at a different, actionable fix.
        raw_text = (ocr_result.get("raw_ocr_text", "") or "").strip()

        if not raw_text:
            unknown_reason = "OCR_NO_TEXT_DETECTED"
            unknown_message = (
                "No text could be read from this image at all. Try a "
                "clearer, well-lit photo taken closer to the label."
            )
        elif not ocr_result.get("ingredient_section_found", False):
            unknown_reason = "INGREDIENT_SECTION_NOT_FOUND"
            unknown_message = (
                "Text was read from the image, but no ingredients "
                "list heading could be located. Make sure the "
                "ingredients section is visible and not cropped out "
                "of the photo."
            )
        else:
            unknown_reason = "INGREDIENT_TEXT_EMPTY"
            unknown_message = (
                "An ingredients heading was found, but no readable "
                "ingredient text followed it."
            )
    else:
        allergen_result = analyze_ingredient_text(
            ingredient_text,
            dictionary,
        )

    allergen_result["extraction_status"] = extraction_status
    allergen_result["unknown_reason"] = unknown_reason
    allergen_result["unknown_message"] = unknown_message

    return {
        "image": str(image_path),
        "ocr": {
            "language": ocr_result.get(
                "ocr_language",
                language,
            ),
            "raw_text": ocr_result.get(
                "raw_ocr_text",
                "",
            ),
            "ingredient_text": ingredient_text,
            "confidence": ocr_result.get(
                "ocr_confidence",
                0.0,
            ),
        },
        "allergens": allergen_result,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Analyze a food label image for allergens."
    )

    parser.add_argument(
        "image",
        help="Path to the food-label image",
    )

    parser.add_argument(
        "--language",
        default="en",
        choices=[
            "en",
            "fr",
            "de",
            "es",
            "nl",
            "it",
            "pt",
            "ar",
        ],
        help="OCR language code (default: en)",
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the complete result as JSON",
    )

    args = parser.parse_args()

    try:
        result = analyze_label(
            args.image,
            language=args.language,
        )

        if args.json:
            print(
                json.dumps(
                    result,
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return

        print()
        print("=" * 70)
        print("FOOD LABEL ALLERGEN ANALYSIS")
        print("=" * 70)

        print(f"\nImage: {result['image']}")
        print(f"OCR language: {result['ocr']['language']}")

        print(
            f"\nOCR confidence: "
            f"{result['ocr']['confidence']:.4f}"
        )

        print("\nIngredient extraction:")
        print("-" * 70)
        print(result["allergens"]["extraction_status"])

        print("\nDeclared allergens:")
        print("-" * 70)
        print(
            ", ".join(
                result["allergens"]["declared_allergens"]
            )
            or "None detected"
        )

        print("\nTrace allergens:")
        print("-" * 70)
        print(
            ", ".join(
                result["allergens"]["trace_allergens"]
            )
            or "None detected"
        )

        print("\nRisk:")
        print("-" * 70)
        print(result["allergens"]["risk"])

        print("\nEvidence:")
        print("-" * 70)

        for match in result["allergens"]["matches"]:
            print(
                f"{match['allergen']}: "
                f"{match['matched_term']}"
            )

        for match in result["allergens"]["trace_matches"]:
            print(
                f"{match['allergen']}: "
                f"{match['matched_term']} "
                f"(trace)"
            )

        print("\n" + "=" * 70)

    except Exception as exc:
        print(f"\nERROR: {exc}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()