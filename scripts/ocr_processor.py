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
    "المكونات",
    "مكونات",
]

# Multilingual heading terms used for FUZZY matching in
# extract_ingredient_section(), scoped to this project's actually
# supported OCR languages only (en, fr, de, es, nl, it, pt, ar).
#
# Deliberately narrower than INGREDIENT_WORDS above: including an
# out-of-scope term (e.g. Scandinavian "ingredienser") in fuzzy
# matching caused a real false-positive collision during testing -
# German "intensiver" (a common marketing word) matched it at 0.64
# similarity, which would have anchored extraction on the wrong line
# entirely. Exact-match usage of INGREDIENT_WORDS is unaffected.
#
# Keyed by language so fuzzy matching only ever compares against
# terms for the language actually being OCR'd - checking every
# language's term against every image is itself a source of false
# positives, independent of the term-length issue below: French
# "graines" (seeds) matched Spanish/Portuguese "ingredientes" at
# 0.632 on a French-language image, which had nothing to do with
# either language's OCR quality - it was purely an artifact of
# comparing against an irrelevant language's vocabulary.
FUZZY_HEADING_TERMS_BY_LANGUAGE = {
    "en": ["ingredients", "ingredient"],
    "fr": ["ingrédients", "ingrédient"],
    "de": ["zutaten"],
    "es": ["ingredientes", "ingrediente"],
    "pt": ["ingredientes", "ingrediente"],
    "it": ["ingredienti"],
    "nl": ["ingrediënten", "ingrediënt"],
    "ar": ["المكونات", "مكونات"],
}

# Fuzzy word length is a real threshold-selection variable: short
# terms (e.g. "zutaten", 7 chars) have far less room for
# discriminative edit distance than long ones (e.g. "ingredients"/
# "ingrediënten", 11-12 chars). A fixed ratio let short, unrelated
# words collide - German "enthalten" (used in "kann ... enthalten"
# trace-allergen phrasing, i.e. actual label text, not noise)
# matched "zutaten" at 0.62. Scaling the bar by term length is a
# general rule, not a patch for that one collision.
_FUZZY_SHORT_TERM_THRESHOLD = 0.75
_FUZZY_LONG_TERM_THRESHOLD = 0.62
_FUZZY_SHORT_TERM_MAX_LEN = 8
_FUZZY_MIN_WORD_LEN = 5

# A genuine heading line is short - essentially just the heading
# word itself, maybe with a colon/qualifier. Without this, a fuzzy
# match buried in the middle of an unrelated, multi-word garbled
# line (e.g. a scrambled multi-language/multi-column label reading
# "Rrked plntenertracten, met zoetstollen Lreredinten: sprankelend")
# gets treated the same as a clean, isolated match (e.g. a line that
# is just "Ingredlento") - even though the former is far less
# trustworthy. This caps how many OTHER substantial words are
# allowed on a line for a fuzzy match on it to be trusted.
_FUZZY_MAX_OTHER_SIGNIFICANT_WORDS = 1


def _fuzzy_threshold_for_term(term):
    if len(term) <= _FUZZY_SHORT_TERM_MAX_LEN:
        return _FUZZY_SHORT_TERM_THRESHOLD
    return _FUZZY_LONG_TERM_THRESHOLD


def _line_has_fuzzy_heading(line_normalized, language):
    """
    Detect a heading word the exact patterns miss, tolerating OCR
    character corruption (e.g. "Ingredlento" for "Ingredients") and
    OCR spacing errors that fuse the heading to one adjacent word
    (e.g. a heading glued to the next word with no space between
    them), without scanning across unrelated marketing/nutrition
    text where coincidental letter overlap causes false positives.

    Two passes, both scoped to individual word tokens only:
    1. Whole-token fuzzy match against each heading term.
    2. A sliding window WITHIN a single (longer) token, to catch a
       heading fused to part of the next word.

    Both passes are scoped to the terms for `language` only, and
    both require the matched line to be mostly just the heading
    word (see _FUZZY_MAX_OTHER_SIGNIFICANT_WORDS) - a match deep
    inside an otherwise unrelated sentence is not trusted.
    """

    terms = FUZZY_HEADING_TERMS_BY_LANGUAGE.get(language, [])
    if not terms:
        return False

    words = line_normalized.split()
    significant_words = [w for w in words if len(w) >= _FUZZY_MIN_WORD_LEN]

    for word in words:
        if len(word) < _FUZZY_MIN_WORD_LEN:
            continue

        other_significant_words = len(significant_words) - 1

        for term in terms:
            ratio = SequenceMatcher(None, word, term).ratio()
            if (
                ratio >= _fuzzy_threshold_for_term(term)
                and other_significant_words
                <= _FUZZY_MAX_OTHER_SIGNIFICANT_WORDS
            ):
                return True

            term_len = len(term)
            if len(word) > term_len:
                # Substring matching is inherently riskier (many
                # windows tried per word), so it always uses at
                # least the stricter, length-scaled bar.
                bar = max(_fuzzy_threshold_for_term(term), 0.70)
                for start in range(0, len(word) - term_len + 1):
                    window = word[start:start + term_len]
                    if (
                        SequenceMatcher(None, window, term).ratio() >= bar
                        and other_significant_words
                        <= _FUZZY_MAX_OTHER_SIGNIFICANT_WORDS
                    ):
                        return True

    return False

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
    "ar": ["ar"],
}


class OCRLanguageInitError(RuntimeError):
    """Raised when a recognized OCR language's EasyOCR model fails to
    initialize. Deliberately NOT caught and silently replaced with an
    English reader - the caller must surface this to the user instead of
    returning OCR results run against the wrong language's model."""


_READER_CACHE = {}


def get_ocr_reader(language="en"):
    """
    Return a cached EasyOCR reader for the requested language.

    Languages not in EASYOCR_LANGUAGE_MAP fall back to English (unchanged
    prior behavior). A RECOGNIZED language whose EasyOCR model fails to
    initialize (e.g. Arabic, if the model weights can't be downloaded)
    raises OCRLanguageInitError instead of silently substituting English -
    running Arabic-script text through an English OCR model would produce
    meaningless output rather than a visible failure.
    """

    language = str(
        language or "en"
    ).strip().lower()

    is_recognized = language in EASYOCR_LANGUAGE_MAP

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

        try:
            _READER_CACHE[cache_key] = easyocr.Reader(
                languages,
                gpu=False,
            )
        except Exception as exc:
            if is_recognized:
                raise OCRLanguageInitError(
                    f"Could not initialize OCR for language '{language}': {exc}"
                ) from exc
            raise

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
    language: str = "en",
) -> tuple[str, bool]:
    """
    Extract the ingredient section from OCR text.

    `language` scopes the fuzzy-matching fallback to that language's
    heading terms only (see FUZZY_HEADING_TERMS_BY_LANGUAGE) - the
    exact-regex fast path below still checks all supported languages
    unconditionally, since an exact whole-word match carries
    essentially no false-positive risk regardless of language.

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
        r"\bالمكونات\b",
        r"\bمكونات\b",
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

        normalized = normalize_for_matching(line)

        # Cheap, generic substring check for minor mid-word
        # corruption of "ingredien..." itself.
        if "ingredien" in normalized:
            ingredient_start = index
            break

        # Fuzzy fallback for heavier OCR corruption (garbled
        # characters, or the heading fused to an adjacent word with
        # no space) that the checks above miss. See
        # _line_has_fuzzy_heading() for what it does and does not
        # catch, and why.
        if _line_has_fuzzy_heading(normalized, language):
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
    found_stop_marker = False

    # Empirically justified, not arbitrary: the longest manually
    # verified ingredient section in this project's benchmark ground
    # truth is 1039 characters (max across 39 samples; median 211).
    # 1500 gives real lists headroom for OCR noise inflating length,
    # while still being far short of what a runaway capture produces
    # (a scrambled multi-language/multi-column label pulled in
    # several thousand characters of nutrition table, barcode, and
    # repeated-language text once heading detection got more
    # tolerant - see MAX_INGREDIENT_SECTION_CHARS below).
    MAX_INGREDIENT_SECTION_CHARS = 1500

    for line in lines[ingredient_start + 1:]:

        if stop_regex.search(line):
            found_stop_marker = True
            break

        normalized = normalize_for_matching(line)

        if not normalized:
            continue

        collected.append(line)

        if len(" ".join(collected)) > MAX_INGREDIENT_SECTION_CHARS:
            break

    ingredient_text = " ".join(
        collected
    ).strip()

    if not ingredient_text:
        return "", False

    # A genuine ingredient section on packaged food is reliably
    # followed by SOME recognizable stop marker (nutrition table,
    # storage/date info, barcode) - that combination is close to
    # universal on real labels. Running this long without ever
    # hitting one is a signal that the captured span isn't a bounded
    # ingredient section at all, most likely a heading match (often
    # a fuzzy one) on a label whose OCR reading order is scrambled
    # across languages/columns, dragging in unrelated content. In
    # that situation, reporting failure is more honest - and more
    # useful downstream - than returning a large, mostly-wrong blob.
    if not found_stop_marker and len(ingredient_text) > MAX_INGREDIENT_SECTION_CHARS:
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
            raw_text,
            language=str(language or "en").strip().lower(),
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