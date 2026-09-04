# Wait What's In This?

## AI-Powered Personalized Food Allergen Detection & Risk Assessment

> **Scan it. Understand it. Know your risk.**

Wait What's In This? is an AI-powered decision-support system designed
to help users identify potential allergens in packaged food products.

The project combines **OCR, natural language processing, ingredient
analysis, allergen matching, and personalized risk assessment** to turn
complex food labels into simple, understandable results.

------------------------------------------------------------------------

## Problem Statement

Food ingredient labels can be difficult to interpret, especially for
people managing food allergies.

Potential allergens may:

-   Appear under different names or ingredient forms
-   Be hidden inside long ingredient lists
-   Use scientific or unfamiliar terminology
-   Appear in precautionary statements such as "may contain" or "traces
    of"
-   Require users to manually compare ingredients with their personal
    allergy profile

**Wait What's In This?** aims to simplify this process by automatically
extracting ingredient information, identifying potential allergens, and
providing a personalized risk assessment.

------------------------------------------------------------------------

## Objectives

-   Extract ingredient information from food labels using OCR
-   Identify potential allergens from ingredient information
-   Normalize ingredient and allergen information
-   Personalize allergen detection according to the user's selected
    allergies
-   Distinguish direct allergens from precautionary statements
-   Provide a simple risk classification
-   Explain which ingredient or allergen caused the detected risk

------------------------------------------------------------------------

## System Workflow

``` text
                    FOOD LABEL IMAGE
                           |
                           v
                  IMAGE PREPROCESSING
                           |
                           v
                          OCR
                           |
                           v
                  INGREDIENT EXTRACTION
                           |
                           v
                  TEXT NORMALIZATION
                           |
                           v
                   ALLERGEN MATCHING
                           |
                    +------+------+
                    |             |
                    v             v
              PRODUCT DATA    USER PROFILE
                    |             |
                    +------+------+
                           |
                           v
                    RISK ASSESSMENT
                           |
                           v
                 +---------+---------+
                 |         |         |
                 v         v         v
               SAFE     CAUTION     AVOID
                           |
                           v
                     EXPLANATION
```

------------------------------------------------------------------------

## Key Features

### OCR-Based Ingredient Extraction

Extract ingredient information directly from a food label image,
reducing the need for manual entry.

### Ingredient Analysis

Clean and normalize extracted ingredient information so that different
ingredient names and representations can be analyzed consistently.

### Personalized Allergen Detection

Compare detected ingredients and allergen information against the user's
selected allergy profile.

### Direct and Precautionary Allergen Detection

The system is designed to distinguish between direct allergen
information and precautionary statements such as:

``` text
Contains milk
May contain nuts
Traces of soy
```

### Explainable Risk Assessment

Instead of only returning a risk level, the system is designed to
identify the ingredient or allergen responsible for the result.

### Simple Risk Classification

  -----------------------------------------------------------------------
  Result                              Meaning
  ----------------------------------- -----------------------------------
  **SAFE**                            No selected allergens detected

  **CAUTION**                         Potential or precautionary allergen
                                      information detected

  **AVOID**                           A selected allergen is directly
                                      detected
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## Technology Stack

  Component              Technology
  ---------------------- ---------------------------------------
  Programming Language   Python
  Data Processing        Pandas
  OCR                    OCR-based ingredient extraction
  NLP                    Ingredient normalization and matching
  Machine Learning       Risk assessment
  Dataset                Open Food Facts
  Data Formats           CSV / JSON
  Version Control        Git & GitHub

------------------------------------------------------------------------

## Dataset

The project uses product information from **Open Food Facts**,
including:

-   Product name
-   Product code
-   Ingredient text
-   Ingredient tags
-   Allergen tags
-   Trace allergen information
-   Language

Product records are identified using their product codes to help prevent
duplicate entries.

### Current Dataset

The current cleaned dataset contains:

**1,618 unique product records**

The dataset was created by combining collected Open Food Facts data and
removing duplicate product codes.

------------------------------------------------------------------------

## Project Structure

``` text
wait-whats-in-this/
|
+-- data/
|   +-- products.csv
|
+-- scripts/
|   +-- get_openfoodfacts_data.py
|   +-- analyze_allergens.py
|
+-- README.md
+-- requirements.txt
+-- .gitignore
```

### `data/products.csv`

Contains the product information used for ingredient and allergen
analysis.

### `scripts/get_openfoodfacts_data.py`

Collects and prepares product information from Open Food Facts.

### `scripts/analyze_allergens.py`

Analyzes ingredient, allergen, and trace information from the product
dataset.

### `requirements.txt`

Contains the Python dependencies required by the project.

------------------------------------------------------------------------

## Current Development Status

### Completed

-   [x] Open Food Facts data collection
-   [x] Product dataset preparation
-   [x] Product code deduplication
-   [x] Ingredient information extraction from dataset
-   [x] Allergen information extraction
-   [x] Allergen tag analysis
-   [x] Trace allergen analysis
-   [x] Initial risk classification design

### In Progress

-   [ ] OCR-based ingredient extraction
-   [ ] Ingredient normalization
-   [ ] Personalized allergy profiles
-   [ ] Machine learning risk assessment
-   [ ] Explainable AI layer
-   [ ] End-to-end application
-   [ ] User interface

------------------------------------------------------------------------

## Intended User Workflow

``` text
                    USER
                     |
                     v
             Upload Food Label
                     |
                     v
                    OCR
                     |
                     v
          Extract Ingredient Text
                     |
                     v
            Clean & Normalize
                     |
                     v
             Identify Allergens
                     |
                     v
          Compare With User Profile
                     |
                     v
             Calculate Risk
                     |
              +------+------+
              |      |      |
              v      v      v
            SAFE   CAUTION  AVOID
                     |
                     v
              Explain Result
```

------------------------------------------------------------------------

## Example

For a user with a **milk allergy**, a scanned label may contain:

``` text
Ingredients:
wheat flour, sugar, milk powder,
vegetable oil, salt
```

The system can identify:

``` text
Detected allergen:
Milk
```

and return:

``` text
AVOID

Reason:
Milk was detected in the ingredient information
and matches the user's selected allergy profile.
```

For a precautionary statement:

``` text
CAUTION

Reason:
The product contains a precautionary statement
indicating possible traces of nuts.
```

------------------------------------------------------------------------

## Why This Project?

The goal is not simply to answer:

> **"Does this product contain an allergen?"**

The more useful question is:

> **"Is this product potentially safe for me?"**

Different users may have different allergies. Connecting ingredient
analysis with an individual allergy profile allows the system to provide
a more personalized assessment instead of a single generic result.

------------------------------------------------------------------------

## Data Source

Product data is sourced from **Open Food Facts**, an open database
containing information about food products, ingredients, allergens,
nutrition, and related product information.

The dataset is used for educational and research purposes.

------------------------------------------------------------------------

## Future Scope

-   Multilingual ingredient recognition
-   Improved OCR for curved, damaged, or low-quality packaging
-   Ingredient synonym and hidden-allergen detection
-   Ingredient knowledge graphs
-   Machine learning-based risk scoring
-   Explainable AI recommendations
-   Barcode-based product lookup
-   Real-time product scanning
-   Mobile application support
-   Expanded product coverage
-   User-specific allergy profiles
-   Confidence scores for detected allergens

------------------------------------------------------------------------

## Disclaimer

**Wait What's In This?** is an educational and research project intended
to assist with ingredient and allergen interpretation.

It is **not a medical diagnostic tool** and should not replace
professional medical advice, a physician's guidance, or official product
labeling.

Users with severe or life-threatening allergies should always verify
product information independently before consuming a product.

------------------------------------------------------------------------

## License

This project is developed for educational and research purposes.
