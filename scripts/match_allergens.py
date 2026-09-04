import json
import re
import ast
import unicodedata
from pathlib import Path

import pandas as pd


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_FILE = BASE_DIR / "data" / "cleaned_products.csv"
DICTIONARY_FILE = BASE_DIR / "data" / "allergen_dictionary.json"


# ============================================================
# LOAD DATA
# ============================================================

df = pd.read_csv(DATA_FILE)

with open(DICTIONARY_FILE, "r", encoding="utf-8") as f:
    allergen_dictionary = json.load(f)


# ============================================================
# OPEN FOOD FACTS TAG -> OUR ALLERGEN CATEGORY
# ============================================================

TAG_TO_ALLERGEN = {

    # English Open Food Facts tags
    "en:milk": "milk",
    "en:eggs": "egg",
    "en:peanuts": "peanut",
    "en:nuts": "tree_nut",
    "en:soybeans": "soy",
    "en:gluten": "wheat_gluten",
    "en:fish": "fish",
    "en:crustaceans": "shellfish",
    "en:sesame-seeds": "sesame",

    # Multilingual tags
    "fr:lait": "milk",
    "fr:oeufs": "egg",
    "fr:œufs": "egg",
    "fr:arachides": "peanut",
    "fr:fruits-a-coque": "tree_nut",
    "fr:gluten": "wheat_gluten",
    "fr:poissons": "fish",
    "fr:crustaces": "shellfish",
    "fr:sésame": "sesame",
    "fr:soja": "soy",

    "fr:soja": "soy",
    "fr:sesame-seeds": "sesame",

    "es:leche": "milk",
    "es:huevos": "egg",
    "es:cacahuetes": "peanut",
    "es:frutos-de-cascara": "tree_nut",
    "es:gluten": "wheat_gluten",
    "es:pescado": "fish",
    "es:crustaceos": "shellfish",
    "es:sesamo": "sesame",
    "es:soja": "soy",
}


# ============================================================
# TEXT NORMALIZATION
# ============================================================

def normalize_text(text):
    """
    Normalize ingredient text while preserving multilingual
    characters such as Arabic.

    Handles:
    - lowercase
    - accents
    - œ / æ / ß
    - language prefixes such as en:
    - punctuation
    - repeated spaces
    """

    if pd.isna(text):
        return ""

    text = str(text).lower()

    # Handle special characters / ligatures
    replacements = {
        "œ": "oe",
        "æ": "ae",
        "ß": "ss",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    # Remove accents
    text = unicodedata.normalize("NFKD", text)

    text = "".join(
        char
        for char in text
        if not unicodedata.combining(char)
    )

    # Remove language prefixes such as en:, fr:, es:
    text = re.sub(r"\b[a-z]{2}:", " ", text)

    # Keep:
    # - English letters
    # - numbers
    # - Arabic characters
    # - whitespace
    text = re.sub(
        r"[^a-z0-9\u0600-\u06ff\s]",
        " ",
        text
    )

    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text


# ============================================================
# NORMALIZE DICTIONARY
# ============================================================

normalized_dictionary = {}

for allergen, keywords in allergen_dictionary.items():

    normalized_dictionary[allergen] = []

    for keyword in keywords:

        normalized_keyword = normalize_text(keyword)

        if normalized_keyword:
            normalized_dictionary[allergen].append(
                normalized_keyword
            )


# ============================================================
# ADDITIONAL MULTILINGUAL SYNONYMS
# ============================================================

EXTRA_SYNONYMS = {

    # --------------------------------------------------------
    # MILK
    # --------------------------------------------------------

    "milk": [

        "leche",
        "leite",
        "milch",
        "latte",
        "buttermilk",

        "milk protein",
        "milk powder",
        "skimmed milk",
        "whole milk",

        "proteine del latte",
        "proteina del latte",
        "latte scremato",
        "leche desnatada",

        # Arabic
        "حليب",
        "الحليب",
        "حليب بقري",
        "مسحوق الحليب",
        "الحليب منزوع الدسم",
        "بروتين حليبي",
        "بروتين الحليب",
        "الكازين",
        "لاكتوسيروم",
        "لاكتوز",
        "بروتين مصل الحليب",
    ],


    # --------------------------------------------------------
    # EGG
    # --------------------------------------------------------

    "egg": [

        "oeuf",
        "œuf",
        "oeufs",

        "jaja",
        "jajas",

        "yumurta",

        "egg yolk",
        "egg white",

        "albumen",
    ],


    # --------------------------------------------------------
    # PEANUT
    # --------------------------------------------------------

    "peanut": [

        "cacahuete",
        "cacahuetes",

        "arachide",
        "arachides",
        "arachis",

        "groundnut",
        "groundnuts",

        "erdnuss",
        "erdnüsse",
    ],


    # --------------------------------------------------------
    # TREE NUT
    # --------------------------------------------------------

    "tree_nut": [

        "mandeln",

        "haselnuss",
        "haselnüsse",

        "walnoten",

        "pähkinä",
        "pähkinät",

        "schalenfrüchte",
        "schalenfruchten",
    ],


    # --------------------------------------------------------
    # SOY
    # --------------------------------------------------------

    "soy": [

        "soja",
        "soya",

        "soy lecithin",
        "soja lecithin",

        "lecithine de soja",
        "lecithin de soja",

        "soy protein",

        # Arabic
        "الصويا",
        "صويا",
        "ليسيثين الصويا",
        "بروتين الصويا",
    ],


    # --------------------------------------------------------
    # WHEAT / GLUTEN
    # --------------------------------------------------------

    "wheat_gluten": [

        "trigo",

        "farinha de trigo",
        "farine de ble",

        "mąka pszenna",
        "pszenna",
        "pszenica",

        "pšeničná",

        "vollkornweizenmehl",
        "weizenmehl",
        "weizen",

        "wheat flour",
        "wheat starch",
        "wheat fibres",
    ],


    # --------------------------------------------------------
    # FISH
    # --------------------------------------------------------

    "fish": [

        "thon",
        "caballa",
        "anchois",
        "saumon",
        "morue",

        "maquereau",
        "maquereaux",

        "sardine",
    ],


    # --------------------------------------------------------
    # SHELLFISH
    # --------------------------------------------------------

    "shellfish": [

        "crevette",
        "crevettes",

        "gambas",

        "camarones",

        "langostinos",

        "krill",
    ],


    # --------------------------------------------------------
    # SESAME
    # --------------------------------------------------------

    "sesame": [

        "sésame",
        "sesamo",
        "sesam",

        "sesame seeds",
    ],
}


# Add extra synonyms without duplicating existing ones
for allergen, keywords in EXTRA_SYNONYMS.items():

    if allergen not in normalized_dictionary:
        normalized_dictionary[allergen] = []

    for keyword in keywords:

        normalized_keyword = normalize_text(keyword)

        if (
            normalized_keyword
            and normalized_keyword
            not in normalized_dictionary[allergen]
        ):
            normalized_dictionary[allergen].append(
                normalized_keyword
            )


# ============================================================
# MATCH KEYWORDS
# ============================================================

def keyword_matches(text, keyword):

    if not text or not keyword:
        return False

    # Exact word / phrase match
    pattern = (
        r"(?<!\w)"
        + re.escape(keyword)
        + r"(?!\w)"
    )

    if re.search(pattern, text):
        return True

    # Handle compound words.
    #
    # Example:
    # vollkornweizenmehl
    #
    # can match:
    # weizen
    #
    # Only allow this for longer keywords to reduce
    # accidental false positives.

    if len(keyword) >= 5:

        pattern = (
            r"(?<!\w)"
            + re.escape(keyword)
        )

        if re.search(pattern, text):
            return True

    return False


# ============================================================
# FIND ALLERGENS
# ============================================================

def find_allergens(text):

    normalized_text = normalize_text(text)

    detected = []

    for allergen, keywords in normalized_dictionary.items():

        for keyword in keywords:

            if keyword_matches(
                normalized_text,
                keyword
            ):

                detected.append(allergen)
                break

    return sorted(set(detected))


# ============================================================
# TRACE / MAY-CONTAIN MARKERS
# ============================================================

TRACE_MARKERS = [

    "may contain",
    "may contain traces",
    "contains traces",

    "traces",
    "trace",
    "traces of",

    "possible traces",
    "possibly contains",

    "peut contenir",
    "traces eventuelles",
    "traces de",

    "kann spuren enthalten",
    "kann spuren von enthalten",

    "puede contener",
    "puede contener trazas",
]


# ============================================================
# SPLIT INGREDIENTS AND TRACE TEXT
# ============================================================

def split_declared_and_trace_text(text):

    if pd.isna(text):
        return "", ""

    original = str(text)

    normalized = normalize_text(original)

    positions = []

    for marker in TRACE_MARKERS:

        marker_normalized = normalize_text(marker)

        if not marker_normalized:
            continue

        pattern = (
            r"(?<!\w)"
            + re.escape(marker_normalized)
            + r"(?!\w)"
        )

        match = re.search(
            pattern,
            normalized
        )

        if match:
            positions.append(match.start())

    # No trace section
    if not positions:
        return normalized, ""

    # First trace marker
    first_position = min(positions)

    declared_text = normalized[:first_position]
    trace_text = normalized[first_position:]

    return declared_text, trace_text


# ============================================================
# OPEN FOOD FACTS TAG PARSER
# ============================================================

def convert_tags(tag_string):
    """
    Convert Open Food Facts tags into our allergen categories.

    Handles values stored as:

        ['en:milk', 'en:soybeans']

    OR:

        en:milk,en:soybeans

    OR:

        en:milk;en:soybeans
    """

    if pd.isna(tag_string):
        return []

    text = str(tag_string).strip()

    if not text:
        return []

    if text.lower() in [
        "nan",
        "none",
        "null",
        "[]",
    ]:
        return []

    tags = []

    # --------------------------------------------------------
    # Python-list format
    # --------------------------------------------------------

    if text.startswith("[") and text.endswith("]"):

        try:

            parsed = ast.literal_eval(text)

            if isinstance(parsed, list):

                tags = parsed

            else:

                tags = [text]

        except (
            ValueError,
            SyntaxError
        ):

            # Fallback
            tags = re.findall(
                r"['\"]([^'\"]+)['\"]",
                text
            )

    # --------------------------------------------------------
    # Semicolon-separated
    # --------------------------------------------------------

    elif ";" in text:

        tags = text.split(";")

    # --------------------------------------------------------
    # Comma-separated
    # --------------------------------------------------------

    elif "," in text:

        tags = text.split(",")

    else:

        tags = [text]


    result = []

    for tag in tags:

        tag = str(tag).strip()

        # Remove quotes
        tag = tag.strip("'\"")

        # Normalize tag itself
        tag = tag.lower()

        if not tag:
            continue

        # Direct mapping
        if tag in TAG_TO_ALLERGEN:

            result.append(
                TAG_TO_ALLERGEN[tag]
            )

            continue

        # ----------------------------------------------------
        # Handle case variations / multilingual prefixes
        # ----------------------------------------------------

        normalized_tag = normalize_text(tag)

        # Try exact normalized mapping
        for known_tag, allergen in TAG_TO_ALLERGEN.items():

            if normalize_text(known_tag) == normalized_tag:

                result.append(allergen)

                break


    return sorted(set(result))


# ============================================================
# ANALYSIS
# ============================================================

total_products = len(df)

declared_products = 0
detected_declared_products = 0

trace_products = 0
detected_trace_products = 0

unmatched_supported = []


# ============================================================
# PROCESS PRODUCTS
# ============================================================

for _, row in df.iterrows():

    ingredients = row.get(
        "ingredients_text",
        ""
    )

    declared_tags_raw = row.get(
        "allergens_tags",
        ""
    )

    trace_tags_raw = row.get(
        "traces_tags",
        ""
    )

    # Convert OFD tags
    declared_tags = convert_tags(
        declared_tags_raw
    )

    trace_tags = convert_tags(
        trace_tags_raw
    )

    # Split ingredient text
    declared_text, trace_text = (
        split_declared_and_trace_text(
            ingredients
        )
    )

    # Detect allergens separately
    detected_declared = find_allergens(
        declared_text
    )

    detected_trace = find_allergens(
        trace_text
    )


    # ========================================================
    # STATISTICS
    # ========================================================

    if declared_tags:
        declared_products += 1

    if detected_declared:
        detected_declared_products += 1

    if trace_tags:
        trace_products += 1

    if detected_trace:
        detected_trace_products += 1


    # ========================================================
    # FIND UNMATCHED DECLARED TAGS
    # ========================================================

    unmatched = [
        allergen
        for allergen in declared_tags
        if allergen not in detected_declared
    ]

    if unmatched:

        unmatched_supported.append({

            "product": row.get(
                "product_name",
                ""
            ),

            "code": row.get(
                "code",
                ""
            ),

            "declared_tags": declared_tags,

            "unmatched": unmatched,

            "detected": detected_declared,

            "ingredients": ingredients,
        })


# ============================================================
# PRINT RESULTS
# ============================================================

print()

print("=" * 70)
print("ALLERGEN MATCHING ANALYSIS")
print("=" * 70)

print(
    f"Total products: "
    f"{total_products}"
)

print(
    f"Products with declared allergens: "
    f"{declared_products}"
)

print(
    f"Products with detected declared allergens: "
    f"{detected_declared_products}"
)

print(
    f"Products with traces: "
    f"{trace_products}"
)

print(
    f"Products with detected traces: "
    f"{detected_trace_products}"
)


# ============================================================
# MATCHING RATES
# ============================================================

if declared_products > 0:

    declared_rate = (
        detected_declared_products
        / declared_products
        * 100
    )

    print(
        f"Declared allergen matching rate: "
        f"{declared_rate:.2f}%"
    )


if trace_products > 0:

    trace_rate = (
        detected_trace_products
        / trace_products
        * 100
    )

    print(
        f"Trace allergen matching rate: "
        f"{trace_rate:.2f}%"
    )


# ============================================================
# UNMATCHED DECLARED ALLERGENS
# ============================================================

print()

print("=" * 70)
print("UNMATCHED DECLARED ALLERGENS")
print("=" * 70)


if not unmatched_supported:

    print(
        "No unmatched declared allergen tags found."
    )

else:

    for item in unmatched_supported[:50]:

        print()

        print(
            f"Product: "
            f"{item['product']}"
        )

        print(
            f"Code: "
            f"{item['code']}"
        )

        print(
            f"Declared allergens: "
            f"{item['declared_tags']}"
        )

        print(
            f"Unmatched allergens: "
            f"{item['unmatched']}"
        )

        print(
            f"Detected allergens: "
            f"{item['detected']}"
        )

        print(
            f"Ingredients: "
            f"{item['ingredients']}"
        )

        print("-" * 70)


# ============================================================
# FINISHED
# ============================================================

print()

print("=" * 70)
print("DIAGNOSTIC COMPLETE")
print("=" * 70)