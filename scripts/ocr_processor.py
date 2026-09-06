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

    text = re.sub(
        r"[^a-zA-ZÀ-ÿ\s]",
        " ",
        text,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


# =========================================================
# FUZZY INGREDIENT HEADING DETECTION
# =========================================================

def looks_like_ingredient_heading(text):
    """
    Determines whether an OCR line is probably an
    Ingredients heading, even if OCR made mistakes.
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
            "ingredients",
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
        cv2.COLOR_BGR2GRAY,
    )

    # Upscale
    height, width = gray.shape

    gray = cv2.resize(
        gray,
        (width * 2, height * 2),
        interpolation=cv2.INTER_CUBIC,
    )

    # Improve contrast
    clahe = cv2.createCLAHE(
        clipLimit=2.0,
        tileGridSize=(8, 8),
    )

    enhanced = clahe.apply(gray)

    # Light denoising
    denoised = cv2.fastNlMeansDenoising(
        enhanced,
        None,
        10,
        7,
        21,
    )

    # Threshold
    threshold = cv2.adaptiveThreshold(
        denoised,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        11,
    )

    return {
        "enhanced": enhanced,
        "threshold": threshold,
    }


# =========================================================
# OCR LANGUAGE SUPPORT
# =========================================================

EASYOCR_LANGUAGE_MAP = {
    "en": ["en"],
    "fr": ["fr"],
    "de": ["de"],
    "es": ["es"],
    "nl": ["nl"],
    "it": ["it"],
    "pt": ["pt"],
}

_READER_CACHE = {}


def get_ocr_reader(language="en"):
    """
    Return a cached EasyOCR reader for the requested language.

    Unsupported languages fall back to English.
    """

    language = str(
        language or "en"
    ).strip().lower()

    languages = EASYOCR_LANGUAGE_MAP.get(
        language,
        ["en"],
    )

    cache_key = tuple(languages)

    if cache_key not in _READER_CACHE:

        print(
            f"\nLoading EasyOCR "
            f"for language: {language}"
        )

        _READER_CACHE[cache_key] = easyocr.Reader(
            languages,
            gpu=False,
        )

    return _READER_CACHE[cache_key]


# =========================================================
# OCR
# =========================================================

def run_ocr(
    image_path,
    language="en",
):

    image = load_image(image_path)

    processed = preprocess_image(image)

    reader = get_ocr_reader(language)

    all_passes = []

    # -----------------------------------------------------
    # OCR PASS 1
    # -----------------------------------------------------

    print("\nRunning OCR pass 1...")

    results_1 = reader.readtext(
        processed["enhanced"],
        detail=1,
        paragraph=False,
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
        paragraph=False,
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
        p
        for p in all_passes
        if p
    ]

    if not valid_passes:
        return "", 0.0

    best_pass = max(
        valid_passes,
        key=lambda p: (
            sum(
                conf
                for _, conf in p
            ) / len(p)
        ),
    )

    # -----------------------------------------------------
    # Remove duplicate lines
    # -----------------------------------------------------

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
        text
        for text, _ in unique_results
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

    text = text.replace(
        "\r",
        "\n",
    )

    text = re.sub(
        r"[ \t]+",
        " ",
        text,
    )

    text = re.sub(
        r"\n+",
        "\n",
        text,
    )

    return text.strip()


# =========================================================
# INGREDIENT EXTRACTION
# =========================================================

def extract_ingredient_section(
    ocr_text: str,
) -> tuple[str, bool]:
    """
    Extract the ingredient section from OCR text.

    Returns:
        ingredient_text, extraction_found

    extraction_found is True only when an ingredient heading
    is actually detected.
    """

    if not ocr_text or not ocr_text.strip():
        return "", False

    lines = [
        line.strip()
        for line in ocr_text.splitlines()
        if line.strip()
    ]

    if not lines:
        return "", False

    ingredient_start = None

    # Multilingual ingredient headings.
    heading_patterns = [
        r"\bingredients?\b",
        r"\bingredienti\b",
        r"\bingrédients?\b",
        r"\bingredientes?\b",
        r"\bzutaten\b",
        r"\bingredienser\b",
        r"\bingredienserna\b",
        r"\bsastojci\b",
    ]

    heading_regex = re.compile(
        "|".join(heading_patterns),
        re.IGNORECASE,
    )

    # Find the first line containing an ingredient heading.
    for index, line in enumerate(lines):

        if heading_regex.search(line):
            ingredient_start = index
            break

        # OCR may distort the heading.
        normalized = normalize_for_matching(line)

        if (
            "ingredien" in normalized
            or "ingredienh" in normalized
            or "ingicaienti" in normalized
        ):
            ingredient_start = index
            break

    if ingredient_start is None:
        return "", False

    # Start with the heading line.
    collected = []

    first_line = lines[ingredient_start]

    # Remove the heading itself where possible.
    cleaned_first = heading_regex.sub(
        "",
        first_line,
        count=1,
    ).strip(
        " :-.;,"
    )

    if cleaned_first:
        collected.append(cleaned_first)

    # Stop markers indicating that the ingredient section ended.
    stop_patterns = [
        r"\bnutrition\b",
        r"\bnutritional\b",
        r"\bvaleurs? nutrition",
        r"\bvaleurs? nutrit",
        r"\bnutritionnelles?\b",
        r"\bserving size\b",
        r"\bportion\b",
        r"\bstorage\b",
        r"\bconservation\b",
        r"\bbest before\b",
        r"\bexpiry\b",
        r"\bdate\b",
        r"\benergy\b",
        r"\benergi\b",
        r"\bcalories\b",
        r"\bcalories?\b",
        r"\bbarcode\b",
    ]

    stop_regex = re.compile(
        "|".join(stop_patterns),
        re.IGNORECASE,
    )

    # Continue after the heading.
    for line in lines[ingredient_start + 1:]:

        if stop_regex.search(line):
            break

        normalized = normalize_for_matching(line)

        if not normalized:
            continue

        collected.append(line)

        # Prevent enormous sections from swallowing the entire label.
        if len(
            " ".join(collected)
        ) > 3000:
            break

    ingredient_text = " ".join(
        collected
    ).strip()

    if not ingredient_text:
        return "", False

    return ingredient_text, True


# =========================================================
# COMPLETE PIPELINE
# =========================================================

def process_image(
    image_path,
    language="en",
):

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
        image_path,
        language=language,
    )

    ingredient_text, extraction_found = (
        extract_ingredient_section(
            raw_text
        )
    )

    return {
        "image": str(image_path),
        "raw_ocr_text": raw_text,
        "ingredient_text": ingredient_text,
        "ingredient_section_found": extraction_found,
        "ocr_confidence": round(
            confidence,
            4,
        ),
        "ocr_language": language,
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

    # Optional language argument.
    language = (
        sys.argv[2]
        if len(sys.argv) >= 3
        else "en"
    )

    try:

        result = process_image(
            image_path,
            language=language,
        )

        print(
            "\n" + "=" * 60
        )

        print(
            "OCR LANGUAGE:"
        )

        print(
            result["ocr_language"]
        )

        print(
            "\nOCR CONFIDENCE:"
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