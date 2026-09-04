import requests
import pandas as pd
import os

url = "https://world.openfoodfacts.org/api/v2/search"

params = {
    "categories_tags": "en:snacks",
    "page": 1,
    "page_size": 100,
    "fields": "code,product_name,ingredients_text,ingredients_tags,allergens_tags,traces_tags"
}

headers = {
    "User-Agent": "WaitWhatsInThis/1.0 (student project)"
}

response = requests.get(url, params=params, headers=headers)

if response.status_code != 200:
    print("Error:", response.status_code)
    exit()

data = response.json()
products = data.get("products", [])

os.makedirs("data", exist_ok=True)

df = pd.DataFrame(products)

df.to_csv("data/products.csv", index=False)

print("Products downloaded:", len(df))
print("Saved to data/products.csv")
print(df.head())