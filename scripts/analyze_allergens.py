import pandas as pd
import ast
from collections import Counter

# Load dataset
df = pd.read_csv("data/products.csv")


def parse_tags(value):
    """Convert a string representation of a list into a Python list."""
    if pd.isna(value) or value == "[]":
        return []

    try:
        return ast.literal_eval(value)
    except (ValueError, SyntaxError):
        return []


# Parse list columns
df["allergens_tags"] = df["allergens_tags"].apply(parse_tags)
df["ingredients_tags"] = df["ingredients_tags"].apply(parse_tags)
df["traces_tags"] = df["traces_tags"].apply(parse_tags)


print("\n========== DATASET SUMMARY ==========")
print("Total products:", len(df))

print("\n========== ALLERGENS ==========")

allergens = []

for tags in df["allergens_tags"]:
    allergens.extend(tags)

allergen_counts = Counter(allergens)

for allergen, count in allergen_counts.most_common():
    print(f"{allergen}: {count}")


print("\n========== TRACES / CROSS-CONTACT ==========")

traces = []

for tags in df["traces_tags"]:
    traces.extend(tags)

trace_counts = Counter(traces)

for trace, count in trace_counts.most_common():
    print(f"{trace}: {count}")


print("\n========== INGREDIENT TAGS ==========")

ingredients = []

for tags in df["ingredients_tags"]:
    ingredients.extend(tags)

ingredient_counts = Counter(ingredients)

for ingredient, count in ingredient_counts.most_common(30):
    print(f"{ingredient}: {count}")


print("\n========== PRODUCTS WITH ALLERGENS ==========")

for _, row in df.iterrows():

    if row["allergens_tags"]:
        print("\nProduct:", row["product_name"])
        print("Allergens:", row["allergens_tags"])
        print("Ingredients:", row["ingredients_text"])


print("\n========== PRODUCTS WITH TRACES ==========")

for _, row in df.iterrows():

    if row["traces_tags"]:
        print("\nProduct:", row["product_name"])
        print("Traces:", row["traces_tags"])