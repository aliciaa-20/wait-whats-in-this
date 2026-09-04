import requests
import pandas as pd
import os

url = "https://world.openfoodfacts.net/api/v2/search"

params = {
    "categories_tags_en": "snacks",
    "page": 1,
    "page_size": 20,
    "fields": "code,product_name,ingredients_text,ingredients_tags,allergens_tags,traces_tags"
}

headers = {
    "User-Agent": "WaitWhatsInThis/1.0 (student project)"
}

response = requests.get(
    url,
    params=params,
    headers=headers,
    auth=("off", "off")
)

print("Status code:", response.status_code)

if response.status_code != 200:
    print("Error:", response.text[:500])
    exit()

data = response.json()
products = data.get("products", [])

os.makedirs("data", exist_ok=True)

df = pd.DataFrame(products)

df.to_csv("data/products.csv", index=False)

print("Products downloaded:", len(df))
print("Saved to data/products.csv")
print(df[["code", "product_name", "ingredients_text"]].head())