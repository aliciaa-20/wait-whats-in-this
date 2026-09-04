import pandas as pd
import ast
from collections import Counter

# ---------------------------------------------------------
# Load cleaned dataset
# ---------------------------------------------------------
df = pd.read_csv(
    "data/cleaned_products.csv",
    encoding="utf-8",
    encoding_errors="replace"
)


def parse_tags(value):
    """Convert a string representation of a list into a Python list."""
    if pd.isna(value) or value == "[]":
        return []

    try:
        return ast.literal_eval(value)
    except (ValueError, SyntaxError):
        return []


# ---------------------------------------------------------
# Parse list columns
# ---------------------------------------------------------
df["allergens_tags"] = df["allergens_tags"].apply(parse_tags)
df["ingredients_tags"] = df["ingredients_tags"].apply(parse_tags)
df["traces_tags"] = df["traces_tags"].apply(parse_tags)


# ---------------------------------------------------------
# DATASET SUMMARY
# ---------------------------------------------------------
print("\n========== DATASET SUMMARY ==========")

print("Total products:", len(df))


# ---------------------------------------------------------
# ALLERGEN ANALYSIS
# ---------------------------------------------------------
print("\n========== ALLERGENS ==========")

allergens = []

for tags in df["allergens_tags"]:
    allergens.extend(tags)

allergen_counts = Counter(allergens)

print("Unique allergen tags:", len(allergen_counts))
print()

for allergen, count in allergen_counts.most_common():
    print(f"{allergen}: {count}")


# ---------------------------------------------------------
# TRACE / CROSS-CONTACT ANALYSIS
# ---------------------------------------------------------
print("\n========== TRACES / CROSS-CONTACT ==========")

traces = []

for tags in df["traces_tags"]:
    traces.extend(tags)

trace_counts = Counter(traces)

print("Unique trace tags:", len(trace_counts))
print()

for trace, count in trace_counts.most_common():
    print(f"{trace}: {count}")


# ---------------------------------------------------------
# INGREDIENT TAG ANALYSIS
# ---------------------------------------------------------
print("\n========== INGREDIENT TAGS ==========")

ingredients = []

for tags in df["ingredients_tags"]:
    ingredients.extend(tags)

ingredient_counts = Counter(ingredients)

print("Unique ingredient tags:", len(ingredient_counts))
print()

for ingredient, count in ingredient_counts.most_common(30):
    print(f"{ingredient}: {count}")


# ---------------------------------------------------------
# PRODUCTS WITH ALLERGENS
# ---------------------------------------------------------
print("\n========== PRODUCTS WITH ALLERGENS ==========")

allergen_product_count = 0

for _, row in df.iterrows():

    if row["allergens_tags"]:

        allergen_product_count += 1

        print("\nProduct:", row["product_name"])
        print("Allergens:", row["allergens_tags"])
        print("Ingredients:", row["ingredients_text"])

print("\nProducts containing allergens:", allergen_product_count)


# ---------------------------------------------------------
# PRODUCTS WITH TRACES
# ---------------------------------------------------------
print("\n========== PRODUCTS WITH TRACES ==========")

trace_product_count = 0

for _, row in df.iterrows():

    if row["traces_tags"]:

        trace_product_count += 1

        print("\nProduct:", row["product_name"])
        print("Traces:", row["traces_tags"])

print("\nProducts containing traces:", trace_product_count)


# ---------------------------------------------------------
# SUMMARY
# ---------------------------------------------------------
print("\n========== ANALYSIS SUMMARY ==========")

print("Total products:", len(df))
print("Unique allergens:", len(allergen_counts))
print("Unique trace allergens:", len(trace_counts))
print("Unique ingredient tags:", len(ingredient_counts))
print("Products with allergens:", allergen_product_count)
print("Products with traces:", trace_product_count)