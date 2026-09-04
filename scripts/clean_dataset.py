import pandas as pd

INPUT_FILE = "data/new_products.csv"
OUTPUT_FILE = "data/cleaned_products.csv"

# Load the raw dataset
df = pd.read_csv(
    INPUT_FILE,
    encoding="utf-8",
    encoding_errors="replace"
)

print("========== DATASET CLEANING ==========\n")

print("Original products:", len(df))

# Remove duplicate product codes
before_duplicates = len(df)

df = df.drop_duplicates(
    subset=["code"],
    keep="first"
)

duplicates_removed = before_duplicates - len(df)

print("Duplicate products removed:", duplicates_removed)

# Identify completely unusable rows
missing_everything = (
    df["product_name"].isna()
    & df["ingredients_text"].isna()
    & df["ingredients_tags"].isna()
    & df["allergens_tags"].isna()
    & df["traces_tags"].isna()
)

unusable_removed = missing_everything.sum()

# Remove only completely unusable rows
df = df[~missing_everything]

print("Completely unusable products removed:", unusable_removed)

# Reset row numbers
df = df.reset_index(drop=True)

# Save cleaned dataset
df.to_csv(
    OUTPUT_FILE,
    index=False,
    encoding="utf-8"
)

print("\n========== CLEANING COMPLETE ==========\n")

print("Final products:", len(df))
print("Saved to:", OUTPUT_FILE)

# Final quality report
print("\nMissing values after cleaning:")

print(
    df[
        [
            "product_name",
            "ingredients_text",
            "ingredients_tags",
            "allergens_tags",
            "traces_tags"
        ]
    ].isna().sum()
)