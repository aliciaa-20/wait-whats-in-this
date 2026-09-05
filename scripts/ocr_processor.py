import sys
import re
from pathlib import Path
from difflib import SequenceMatcher

import cv2
import easyocr


# =========================================================
# PATHS
# =========================================================

BASE_DIR = Path(__file__).resolve().parent.parent


# =========================================================
# INGREDIENT / STOP WORDS
# =========================================================

INGREDIENT_WORDS = [
    "ingredients",
    "ingredient",
    "ingrédients",
    "zutaten",
    "ingredientes",
    "ingrediënten",
    "ingredienser",
]

STOP_MARKERS = [
    "nutrition facts",
    "nutrition",
    "nutritional information",
    "nutritional values",
    "valeurs nutritionnelles",
    "nährwerte",
    "calories",
    "serving size",
    "storage",
    "store in",
    "conserver",
    "conservation",
    "best before",
    "expiry",
    "expiration",
]


# =========================================================
# NORMALIZATION
# =========================================================

def normalize_for_matching(text):
    """
    Normalize text for fuzzy matching.
    """

    text = text.lower()

    text = text.replace(":", " ")
    text = text.replace("-", " ")
    text = text.replace("_", " ")

    text = re.sub(r"[^a-zA-ZÀ-ÿ\s]", " ", text)

    text = re.sub(r"\s+", " ", text)

    return text.strip()


# =========================================================
# FUZZY INGREDIENT HEADING DETECTION
# =========================================================

def looks_like_ingredient_heading(text):
    """
    Determines whether an OCR line is probably an
    Ingredients heading, even if OCR made mistakes.

    Example:
        Ingredients
        Ingrediants
        Inseedius
        Ingrediens
    """

    normalized = normalize_for_matching(text)

    if not normalized:
        return False

    # Direct matching
    for word in INGREDIENT_WORDS:

        if word in normalized:
            return True

    # Fuzzy matching against English "ingredients"
    words = normalized.split()

    for word in words:

        if len(word) < 5:
            continue

        similarity = SequenceMatcher(
            None,
            word,
            "ingredients"
        ).ratio()

        if similarity >= 0.60:
            return True

    return False


# =========================================================
# IMAGE LOADING
# =========================================================

def load_image(image_path):

    image = cv2.imread(str(image_path))

    if image is None:
        raise FileNotFoundError(
            f"Could not read image: {image_path}"
        )

    return image


# =========================================================
# IMAGE PREPROCESSING
# =========================================================

def preprocess_image(image):
    """
    Creates a small number of high-quality OCR versions.

    We intentionally do NOT run four OCR passes and merge
    everything because that creates duplicated text.
    """

    gray = cv2.cvtColor(
        image,
        cv2.COLOR_BGR2GRAY
    )

    # Upscale
    height, width = gray.shape

    gray = cv2.resize(
        gray,
        (width * 2, height * 2),
        interpolation=cv2.INTER_CUBIC
    )

    # Improve contrast
    clahe = cv2.createCLAHE(
        clipLimit=2.0,
        tileGridSize=(8, 8)
    )

    enhanced = clahe.apply(gray)

    # Light denoising
    denoised = cv2.fastNlMeansDenoising(
        enhanced,
        None,
        10,
        7,
        21
    )

    # Threshold
    threshold = cv2.adaptiveThreshold(
        denoised,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        11
    )

    return {
        "enhanced": enhanced,
        "threshold": threshold
    }


# =========================================================
# OCR
# =========================================================

def run_ocr(image_path):

    image = load_image(image_path)

    processed = preprocess_image(image)

    print("\nLoading EasyOCR...")
    print("The first run may take a little longer.")

    reader = easyocr.Reader(
        ["en"],
        gpu=False
    )

    all_passes = []

    # -----------------------------------------------------
    # OCR PASS 1
    # -----------------------------------------------------

    print("\nRunning OCR pass 1...")

    results_1 = reader.readtext(
        processed["enhanced"],
        detail=1,
        paragraph=False
    )

    pass_1 = []

    for result in results_1:

        if len(result) != 3:
            continue

        _, text, confidence = result

        text = text.strip()

        if text:

            pass_1.append(
                (text, float(confidence))
            )

    all_passes.append(pass_1)

    # -----------------------------------------------------
    # OCR PASS 2
    # -----------------------------------------------------

    print("Running OCR pass 2...")

    results_2 = reader.readtext(
        processed["threshold"],
        detail=1,
        paragraph=False
    )

    pass_2 = []

    for result in results_2:

        if len(result) != 3:
            continue

        _, text, confidence = result

        text = text.strip()

        if text:

            pass_2.append(
                (text, float(confidence))
            )

    all_passes.append(pass_2)

    # -----------------------------------------------------
    # Choose the better OCR pass
    # -----------------------------------------------------

    valid_passes = [
        p for p in all_passes
        if p
    ]

    if not valid_passes:
        return "", 0.0

    best_pass = max(
        valid_passes,
        key=lambda p: (
            sum(conf for _, conf in p) / len(p)
        )
    )

    # Remove duplicate lines within selected pass
    unique_results = []

    seen = set()

    for text, confidence in best_pass:

        key = normalize_for_matching(text)

        if key in seen:
            continue

        seen.add(key)

        unique_results.append(
            (text, confidence)
        )

    raw_text = "\n".join(
        text for text, _ in unique_results
    )

    if unique_results:

        average_confidence = (
            sum(
                confidence
                for _, confidence in unique_results
            )
            / len(unique_results)
        )

    else:

        average_confidence = 0.0

    return raw_text, average_confidence


# =========================================================
# CLEAN OCR TEXT
# =========================================================

def clean_ocr_text(text):

    text = text.replace("\r", "\n")

    text = re.sub(
        r"[ \t]+",
        " ",
        text
    )

    text = re.sub(
        r"\n+",
        "\n",
        text
    )

    return text.strip()


# =========================================================
# INGREDIENT EXTRACTION
# =========================================================

def extract_ingredient_section(text):

    text = clean_ocr_text(text)

    if not text:
        return ""

    lines = text.splitlines()

    ingredient_start = None

    # -----------------------------------------------------
    # Find Ingredients heading
    # -----------------------------------------------------

    for i, line in enumerate(lines):

        if looks_like_ingredient_heading(line):

            ingredient_start = i

            print(
                f"\nIngredient heading detected: {line}"
            )

            break

    # -----------------------------------------------------
    # If heading wasn't found
    # -----------------------------------------------------

    if ingredient_start is None:

        print(
            "\nWarning: Could not confidently identify "
            "the Ingredients heading."
        )

        print(
            "Using OCR text as fallback."
        )

        return text

    # -----------------------------------------------------
    # Extract following lines
    # -----------------------------------------------------

    extracted_lines = []

    # Sometimes the ingredients begin on the same line
    heading_line = lines[ingredient_start]

    normalized_heading = normalize_for_matching(
        heading_line
    )

    # Remove the heading itself
    remaining = re.sub(
        r"(?i)ingredients?|ingrédients?|zutaten|ingredientes?|ingrediënten",
        "",
        heading_line
    ).strip()

    remaining = re.sub(
        r"^[\s:\-]+",
        "",
        remaining
    )

    if remaining:
        extracted_lines.append(remaining)

    # Continue after heading
    for line in lines[ingredient_start + 1:]:

        clean_line = line.strip()

        if not clean_line:
            continue

        normalized_line = normalize_for_matching(
            clean_line
        )

        # Stop when nutrition information begins
        should_stop = False

        for marker in STOP_MARKERS:

            if marker in normalized_line:

                should_stop = True
                break

        if should_stop:
            break

        extracted_lines.append(clean_line)

    ingredient_text = " ".join(
        extracted_lines
    )

    ingredient_text = re.sub(
        r"\s+",
        " ",
        ingredient_text
    ).strip()

    return ingredient_text


# =========================================================
# COMPLETE PIPELINE
# =========================================================

def process_image(image_path):

    image_path = Path(image_path)

    if not image_path.exists():

        raise FileNotFoundError(
            f"Image does not exist: {image_path}"
        )

    print("\n" + "=" * 60)
    print("FOOD LABEL OCR PROCESSOR")
    print("=" * 60)

    print(
        f"\nImage: {image_path}"
    )

    raw_text, confidence = run_ocr(
        image_path
    )

    ingredient_text = extract_ingredient_section(
        raw_text
    )

    return {
        "image": str(image_path),
        "raw_ocr_text": raw_text,
        "ingredient_text": ingredient_text,
        "ocr_confidence": round(
            confidence,
            4
        )
    }


# =========================================================
# MAIN
# =========================================================

def main():

    if len(sys.argv) < 2:

        print(
            "\nUsage:"
        )

        print(
            'python scripts/ocr_processor.py '
            '"path/to/image.jpg"'
        )

        return

    image_path = sys.argv[1]

    try:

        result = process_image(
            image_path
        )

        print(
            "\n" + "=" * 60
        )

        print(
            "OCR CONFIDENCE:"
        )

        print(
            result["ocr_confidence"]
        )

        print(
            "\nRAW OCR TEXT:"
        )

        print(
            "-" * 60
        )

        print(
            result["raw_ocr_text"]
        )

        print(
            "\nEXTRACTED INGREDIENT TEXT:"
        )

        print(
            "-" * 60
        )

        print(
            result["ingredient_text"]
        )

        print(
            "\n" + "=" * 60
        )

    except Exception as e:

        print(
            f"\nERROR: {e}"
        )


if __name__ == "__main__":
    main()