import os
import time
import requests
import pandas as pd


API_URL = "https://world.openfoodfacts.org/api/v2/search"

PAGE_SIZE = 100
MAX_PRODUCTS = 1500

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

    response = requests.get(
        API_URL,
        params=params,
        headers=HEADERS,
        timeout=30
    )

    return response


def save_products(products):
    if not products:
        return

    df = pd.DataFrame(products)

    for column in FIELDS:
        if column not in df.columns:
            df[column] = ""

    df = df[FIELDS]

    df = df[df["code"].notna()]
    df = df[df["code"].astype(str).str.strip() != ""]
    df = df.drop_duplicates(subset="code")

    os.makedirs("data", exist_ok=True)

    df.to_csv("data/products.csv", index=False)

    print(f"Saved {len(df)} products to data/products.csv")


def main():
    products = []
    page = 1
    consecutive_failures = 0

    print("Starting Open Food Facts download...")
    print(f"Target products: {MAX_PRODUCTS}")
    print("Waiting 7 seconds between API requests.")

    while len(products) < MAX_PRODUCTS:

        print(f"\nFetching page {page}...")

        try:
            response = fetch_page(page)

            if response.status_code == 200:

                data = response.json()
                page_products = data.get("products", [])

                if not page_products:
                    print("No more products returned by the API.")
                    break

                products.extend(page_products)

                # Remove duplicates while downloading.
                unique_products = {}

                for product in products:
                    code = product.get("code")

                    if code:
                        unique_products[str(code)] = product

                products = list(unique_products.values())

                print(f"Products collected so far: {len(products)}")

                consecutive_failures = 0
                page += 1

                if len(products) >= MAX_PRODUCTS:
                    break

                # Respect API search rate limit.
                time.sleep(7)

            elif response.status_code in (429, 503):

                consecutive_failures += 1

                print(
                    f"Server returned {response.status_code}. "
                    f"Temporary rate/service issue."
                )

                if consecutive_failures >= 5:
                    print("Too many consecutive failures.")
                    print("Saving products collected so far.")
                    break

                wait_time = min(30 * consecutive_failures, 180)

                print(f"Waiting {wait_time} seconds before retrying...")
                time.sleep(wait_time)

            elif response.status_code == 401:

                print("Server returned 401 Unauthorized.")
                print("Stopping instead of retrying indefinitely.")
                print("Saving products collected so far.")
                break

            else:

                print(f"Unexpected HTTP status: {response.status_code}")
                print("Saving products collected so far.")
                break

        except requests.RequestException as error:

            consecutive_failures += 1

            print(f"Request error: {error}")

            if consecutive_failures >= 5:
                print("Too many consecutive failures.")
                print("Saving products collected so far.")
                break

            wait_time = min(30 * consecutive_failures, 180)

            print(f"Waiting {wait_time} seconds before retrying...")
            time.sleep(wait_time)

    # Limit final dataset to requested size.
    products = products[:MAX_PRODUCTS]

    save_products(products)

    print("\n========== DOWNLOAD COMPLETE ==========")
    print(f"Products saved: {len(products)}")
    print("File: data/products.csv")


if __name__ == "__main__":
    main()