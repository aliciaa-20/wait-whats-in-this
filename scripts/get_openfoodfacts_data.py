import os
import time
import requests
import pandas as pd


API_URL = "https://world.openfoodfacts.org/api/v2/search"

PAGE_SIZE = 100
START_PAGE = 13
NEW_PRODUCTS = 1000

FIELDS = [
    "code",
    "product_name",
    "ingredients_text",
    "ingredients_tags",
    "allergens_tags",
    "traces_tags",
    "lang"
]

HEADERS = {
    "User-Agent": "WaitWhatsInThis/1.0 (educational project)"
}


def fetch_page(page):
    params = {
        "page": page,
        "page_size": PAGE_SIZE,
        "fields": ",".join(FIELDS)
    }

    return requests.get(
        API_URL,
        params=params,
        headers=HEADERS,
        timeout=30
    )


def main():

    csv_path = "data/products.csv"

    if not os.path.exists(csv_path):
        print("ERROR: data/products.csv not found.")
        return

    # ---------------------------------------------------------
    # LOAD EXISTING DATA
    # ---------------------------------------------------------

    existing_df = pd.read_csv(
        csv_path,
        dtype=str,
        keep_default_na=False
    )

    existing_df["code"] = (
        existing_df["code"]
        .astype(str)
        .str.strip()
    )

    existing_codes = set(existing_df["code"])

    print("Existing dataset found.")
    print(f"Existing products: {len(existing_df)}")

    print(f"Target NEW products: {NEW_PRODUCTS}")
    print(f"Starting from page: {START_PAGE}")

    # ---------------------------------------------------------
    # COLLECT NEW PRODUCTS
    # ---------------------------------------------------------

    new_products = []
    page = START_PAGE

    while len(new_products) < NEW_PRODUCTS:

        print(f"\nFetching page {page}...")

        try:

            response = fetch_page(page)

            if response.status_code == 200:

                data = response.json()

                page_products = data.get("products", [])

                if not page_products:
                    print("No more products available.")
                    break

                added = 0

                for product in page_products:

                    code = product.get("code")

                    if not code:
                        continue

                    code = str(code).strip()

                    # Skip existing products
                    if code in existing_codes:
                        continue

                    product["code"] = code

                    new_products.append(product)

                    existing_codes.add(code)

                    added += 1

                    if len(new_products) >= NEW_PRODUCTS:
                        break

                print(f"New products from page: {added}")
                print(
                    f"Progress: "
                    f"{len(new_products)}/{NEW_PRODUCTS}"
                )

                page += 1

                if len(new_products) < NEW_PRODUCTS:
                    time.sleep(7)

            elif response.status_code == 429:

                print("429: Rate limit reached.")
                print("Waiting 60 seconds...")
                time.sleep(60)

            elif response.status_code == 503:

                print("503: OpenFoodFacts temporarily unavailable.")
                print("Waiting 60 seconds...")
                time.sleep(60)

            elif response.status_code == 401:

                print("401: Request rejected by OpenFoodFacts.")
                print("Stopping without changing your CSV.")
                return

            else:

                print(
                    f"Unexpected HTTP status: "
                    f"{response.status_code}"
                )

                print("Stopping without changing your CSV.")
                return

        except requests.RequestException as error:

            print(f"Request error: {error}")
            print("Stopping without changing your CSV.")
            return

    # ---------------------------------------------------------
    # SAFETY CHECK
    # ---------------------------------------------------------

    if len(new_products) < NEW_PRODUCTS:

        print("\n========================================")
        print("NOT ENOUGH NEW PRODUCTS COLLECTED")
        print("CSV HAS NOT BEEN MODIFIED")
        print("========================================")

        print(
            f"Collected: {len(new_products)}"
        )

        print(
            f"Required: {NEW_PRODUCTS}"
        )

        return

    # ---------------------------------------------------------
    # CLEAN NEW DATA
    # ---------------------------------------------------------

    new_df = pd.DataFrame(new_products)

    for column in FIELDS:

        if column not in new_df.columns:
            new_df[column] = ""

    new_df = new_df[FIELDS]

    new_df["code"] = (
        new_df["code"]
        .astype(str)
        .str.strip()
    )

    new_df = new_df.drop_duplicates(
        subset="code"
    )

    # Take exactly 1,000
    new_df = new_df.head(NEW_PRODUCTS)

    # ---------------------------------------------------------
    # CREATE COMBINED DATASET
    # ---------------------------------------------------------

    combined_df = pd.concat(
        [existing_df, new_df],
        ignore_index=True
    )

    combined_df = combined_df.drop_duplicates(
        subset="code",
        keep="first"
    )

    # ---------------------------------------------------------
    # FINAL SAFETY CHECK
    # ---------------------------------------------------------

    expected_total = len(existing_df) + NEW_PRODUCTS

    if len(combined_df) < expected_total:

        print("\nERROR: Duplicate products detected.")
        print("CSV HAS NOT BEEN MODIFIED.")
        return

    # ---------------------------------------------------------
    # SAVE ONLY AFTER EVERYTHING SUCCEEDS
    # ---------------------------------------------------------

    temp_path = "data/products_temp.csv"

    combined_df.to_csv(
        temp_path,
        index=False
    )

    os.replace(
        temp_path,
        csv_path
    )

    # ---------------------------------------------------------
    # COMPLETE
    # ---------------------------------------------------------

    print("\n========================================")
    print("DOWNLOAD COMPLETE")
    print("========================================")

    print(
        f"Previous products: {len(existing_df)}"
    )

    print(
        f"New products added: {len(new_df)}"
    )

    print(
        f"Total products: {len(combined_df)}"
    )

    print(
        f"File: {csv_path}"
    )


if __name__ == "__main__":
    main()