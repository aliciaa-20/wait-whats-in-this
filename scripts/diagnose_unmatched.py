import pandas as pd
import json
import re
import ast
from collections import Counter


# ============================================
# FILE PATHS
# ============================================

DATA_FILE = "data/cleaned_products.csv"
DICTIONARY_FILE = "data/allergen_dictionary.json"


# ============================================
# LOAD DATA
# ============================================

df = pd.read_csv(DATA_FILE)

with open(DICTIONARY_FILE, "r", encoding="utf-8") as f:
    allergen_dictionary = json.load(f)


# ============================================
# NORMALIZATION
# ============================================

def normalize(text):
    if pd.isna(text):
        return ""

    text = str(text).lower()

    # Remove language prefixes such as:
    # en:, fr:, nl:, de:
    text = re.sub(r"\b[a-z]{2}:", " ", text)

    # Replace punctuation with spaces
    text = re.sub(r"[^a-z0-9À-ÿ]+", " ", text)

    # Remove extra spaces
    text = re.sub(r"\s+", " ", text).strip()

    return text


# ============================================
# PARSE OPEN FOOD FACTS TAGS
# ============================================

def extract_tags(value):
    """
    Handles different formats found in the CSV.

    Examples:

    []
    ['en:milk']
    ['en:milk', 'en:soybeans']
    "['en:milk']"
    "['en:milk', 'en:soybeans']"
    """

    if pd.isna(value):
        return []

    value = str(value).strip()

    if value in ("", "[]", "nan"):
        return []

    # Try to interpret Python-list-style strings
    try:
        parsed = ast.literal_eval(value)

        if isinstance(parsed, list):
            return [
                str(item).strip()
                for item in parsed
                if str(item).strip()
            ]

    except (ValueError, SyntaxError):
        pass

    # Fallback
    value = value.strip("[]")

    tags = []

    for item in value.split(","):
        item = item.strip().strip("'").strip('"')

        if item:
            tags.append(item)

    return tags


# ============================================
# FIND ALLERGENS IN INGREDIENT TEXT
# ============================================

def find_allergens(text):

    normalized_text = normalize(text)

    found = set()

    for allergen, keywords in allergen_dictionary.items():

        for keyword in keywords:

            keyword_normalized = normalize(keyword)

            if not keyword_normalized:
                continue

            pattern = r"\b" + re.escape(keyword_normalized) + r"\b"

            if re.search(pattern, normalized_text):
                found.add(allergen)
                break

    return found


# ============================================
# MAP OFF TAGS TO PROJECT ALLERGENS
# ============================================

def normalize_tag(tag):

    tag = normalize(tag)

    mappings = {

        # Milk
        "milk": "milk",
        "lait": "milk",
        "creme": "milk",
        "cream": "milk",

        # Egg
        "eggs": "egg",
        "egg": "egg",
        "oeufs": "egg",

        # Peanut
        "peanuts": "peanut",
        "peanut": "peanut",
        "cacahuetes": "peanut",
        "cacahuetes": "peanut",
        "amendoim": "peanut",

        # Tree nuts
        "nuts": "tree_nut",
        "cashew nuts": "tree_nut",
        "cashew": "tree_nut",
        "almonds": "tree_nut",
        "almond": "tree_nut",
        "hazelnuts": "tree_nut",
        "hazelnut": "tree_nut",
        "walnuts": "tree_nut",
        "walnut": "tree_nut",

        # Soy
        "soybeans": "soy",
        "soy": "soy",

        # Wheat / gluten
        "gluten": "wheat_gluten",
        "cereals with gluten": "wheat_gluten",

        # Fish
        "fish": "fish",

        # Shellfish
        "crustaceans": "shellfish",
        "crustacean": "shellfish",

        # Sesame
        "sesame seeds": "sesame",
        "sesame-seeds": "sesame",
        "sesame": "sesame",
    }

    if tag in mappings:
        return mappings[tag]

    # Try dictionary keywords
    for allergen, keywords in allergen_dictionary.items():

        for keyword in keywords:

            if normalize(keyword) == tag:
                return allergen

    return None


# ============================================
# DIAGNOSIS
# ============================================

unmatched_tags = Counter()
matched_tags = Counter()

unsupported_tags = Counter()

products_with_unmatched = []


for _, row in df.iterrows():

    declared_tags = extract_tags(
        row.get("allergens_tags")
    )

    if not declared_tags:
        continue

    ingredients = row.get(
        "ingredients_text",
        ""
    )

    detected_allergens = find_allergens(
        ingredients
    )

    product_unmatched = []
    product_unsupported = []

    for tag in declared_tags:

        project_allergen = normalize_tag(tag)

        # ------------------------------------
        # Unsupported by our project
        # ------------------------------------

        if project_allergen is None:

            unsupported_tags[tag] += 1
            product_unsupported.append(tag)

            continue

        # ------------------------------------
        # Supported allergen
        # ------------------------------------

        if project_allergen in detected_allergens:

            matched_tags[tag] += 1

        else:

            unmatched_tags[tag] += 1
            product_unmatched.append(tag)

    # ----------------------------------------
    # Save only genuinely interesting cases
    # ----------------------------------------

    if product_unmatched:

        products_with_unmatched.append({

            "code": row.get("code"),

            "product_name": row.get(
                "product_name"
            ),

            "ingredients_text": ingredients,

            "declared_tags": declared_tags,

            "unmatched_tags": product_unmatched,

            "unsupported_tags": product_unsupported,

            "detected_allergens": sorted(
                detected_allergens
            )
        })


# ============================================
# PRINT SUMMARY
# ============================================

print("\n" + "=" * 70)
print("ALLERGEN MATCHING DIAGNOSTIC")
print("=" * 70)

print(
    f"\nTotal products: {len(df)}"
)

print(
    f"Products with declared allergen tags: "
    f"{sum(1 for _, row in df.iterrows() if extract_tags(row.get('allergens_tags')))}"
)

print(
    f"Products with genuinely unmatched supported allergens: "
    f"{len(products_with_unmatched)}"
)


# ============================================
# MATCHED TAGS
# ============================================

print("\n" + "=" * 70)
print("MATCHED TAGS")
print("=" * 70)

if matched_tags:

    for tag, count in matched_tags.most_common():

        print(
            f"{tag}: {count}"
        )

else:

    print("No matched tags found.")


# ============================================
# UNMATCHED SUPPORTED TAGS
# ============================================

print("\n" + "=" * 70)
print("UNMATCHED SUPPORTED ALLERGEN TAGS")
print("=" * 70)

if unmatched_tags:

    for tag, count in unmatched_tags.most_common():

        print(
            f"{tag}: {count}"
        )

else:

    print(
        "No unmatched supported allergens found."
    )


# ============================================
# UNSUPPORTED TAGS
# ============================================

print("\n" + "=" * 70)
print("UNSUPPORTED ALLERGEN TAGS")
print("=" * 70)

if unsupported_tags:

    for tag, count in unsupported_tags.most_common():

        print(
            f"{tag}: {count}"
        )

else:

    print(
        "No unsupported tags found."
    )


# ============================================
# PRODUCTS REQUIRING INVESTIGATION
# ============================================

print("\n" + "=" * 70)
print("PRODUCTS REQUIRING INVESTIGATION")
print("=" * 70)

for product in products_with_unmatched:

    print("\n----------------------------------------")

    print(
        "Product:",
        product["product_name"]
    )

    print(
        "Code:",
        product["code"]
    )

    print(
        "Declared tags:",
        product["declared_tags"]
    )

    print(
        "Unmatched supported tags:",
        product["unmatched_tags"]
    )

    print(
        "Unsupported tags:",
        product["unsupported_tags"]
    )

    print(
        "Detected allergens:",
        product["detected_allergens"]
    )

    print(
        "Ingredients:",
        product["ingredients_text"]
    )


print("\n" + "=" * 70)
print("DIAGNOSTIC COMPLETE")
print("=" * 70)