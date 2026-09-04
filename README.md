# Wait What's In This?

### AI-Powered Personalized Food Allergen Detection & Risk Assessment

```{=html}
<p align="center">
```
**Scan it. Understand it. Know your risk.**

```{=html}
</p>
```
```{=html}
<p align="center">
```
![Python](https://img.shields.io/badge/Python-3.x-blue?logo=python)
![AI/ML](https://img.shields.io/badge/AI-Machine%20Learning-purple)
![OCR](https://img.shields.io/badge/OCR-Enabled-orange)
![NLP](https://img.shields.io/badge/NLP-Enabled-blueviolet)
![Dataset](https://img.shields.io/badge/Dataset-Open%20Food%20Facts-green)
![Status](https://img.shields.io/badge/Status-In%20Development-yellow)

```{=html}
</p>
```

------------------------------------------------------------------------

## Overview

**Wait What's In This?** is an AI-powered decision-support system
designed to help users identify potential allergens in packaged food
products.

The system combines **Optical Character Recognition (OCR), natural
language processing, ingredient analysis, allergen matching, and
personalized risk assessment** to transform complex food labels into
simple and understandable results.

Instead of manually reading long ingredient lists and trying to
recognize unfamiliar ingredient names, users can provide a food label
and receive an assessment based on their selected allergies.

> **The goal is simple: help users understand what's in their food and
> whether it may pose a risk to them.**

------------------------------------------------------------------------

## The Problem

Food ingredient labels can be difficult to interpret, especially for
individuals managing food allergies.

Potential allergens may:

-   Appear under different names or ingredient forms
-   Be hidden within long ingredient lists
-   Use scientific or unfamiliar terminology
-   Appear in precautionary statements such as "may contain" or "traces
    of"
-   Require users to manually compare ingredients against their personal
    allergy profile

Many existing solutions rely primarily on barcode lookup or basic
ingredient matching. These approaches may provide limited
personalization and may not clearly explain **why** a product could be
risky.

**Wait What's In This?** aims to address this problem through
personalized allergen detection and explainable risk assessment.

------------------------------------------------------------------------

## How It Works

``` text
                         FOOD LABEL
                             │
                             ▼
                  IMAGE PREPROCESSING
                             │
                             ▼
                            OCR
                             │
                             ▼
                  INGREDIENT EXTRACTION
                             │
                             ▼
                    TEXT NORMALIZATION
                             │
                             ▼
                     ALLERGEN MATCHING
                             │
                    ┌────────┴────────┐
                    │                 │
                    ▼                 ▼
              PRODUCT DATA       USER PROFILE
                    │                 │
                    └────────┬────────┘
                             ▼
                      RISK ASSESSMENT
                             │
                             ▼
                 ┌───────────┼───────────┐
                 ▼           ▼           ▼
               SAFE       CAUTION       AVOID
                             │
                             ▼
                       EXPLANATION
```

------------------------------------------------------------------------

## Key Features

### Personalized Allergen Detection

The system compares detected ingredient and allergen information against
the user's selected allergy profile instead of applying the same
assessment to every user.

### OCR-Based Ingredient Extraction

Food labels can be processed from images, reducing the need for users to
manually type long ingredient lists.

### Ingredient Analysis

Extracted ingredient information is cleaned, normalized, and analyzed to
identify potential allergen-related information.

### Allergen Matching

Detected ingredients and allergen information are compared against known
allergen categories to identify potential risks.

### Precautionary Allergen Detection

The system considers precautionary information such as:

``` text
Contains milk
May contain nuts
Traces of soy
```

This allows direct allergen information to be distinguished from
potential cross-contact warnings.

### Explainable Results

The system is designed to provide a reason for a risk classification
rather than returning only a generic result.

### Simple Risk Classification

The intended output uses three straightforward categories:

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

The project uses product information from **Open Food Facts**.

The dataset contains information including:

-   Product name
-   Product code
-   Ingredient text
-   Ingredient tags
-   Allergen tags
-   Trace allergen information
-   Language

Product records are identified using their **product codes** to help
prevent duplicate entries.

### Current Dataset

The current cleaned dataset contains:

**1,618 unique product records**

The dataset was created by combining collected Open Food Facts product
data and removing duplicate product codes.

------------------------------------------------------------------------

## Project Structure

``` text
wait-whats-in-this/
│
├── data/
│   └── products.csv
│
├── scripts/
│   ├── get_openfoodfacts_data.py
│   └── analyze_allergens.py
│
├── README.md
├── requirements.txt
└── .gitignore
```

### `data/`

Contains the product dataset used for ingredient and allergen analysis.

### `scripts/get_openfoodfacts_data.py`

Handles collection and preparation of product information from Open Food
Facts.

### `scripts/analyze_allergens.py`

Analyzes product ingredient, allergen, and trace information from the
collected dataset.

### `requirements.txt`

Contains the Python dependencies required to run the project.

------------------------------------------------------------------------

## Current Development Status

### Completed

-   [x] Open Food Facts data collection
-   [x] Product dataset preparation
-   [x] Product code deduplication
-   [x] Ingredient information extraction
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
               │
               ▼
       Upload Food Label
               │
               ▼
             OCR
               │
               ▼
     Extract Ingredient Text
               │
               ▼
      Clean & Normalize Text
               │
               ▼
       Identify Allergens
               │
               ▼
     Compare With User Profile
               │
               ▼
       Calculate Risk Level
               │
       ┌───────┼───────┐
       ▼       ▼       ▼
     SAFE   CAUTION   AVOID
               │
               ▼
        Explain the Result
```

------------------------------------------------------------------------

## Example

A user with a **milk allergy** scans a product label.

The system may identify:

``` text
Ingredients:
wheat flour, sugar, milk powder,
vegetable oil, salt
```

The allergen analysis identifies:

``` text
Detected allergen:
Milk
```

The system can then provide:

``` text
AVOID

Reason:
Milk was detected in the ingredient information
and matches the user's selected allergy profile.
```

For precautionary information, the system can distinguish:

``` text
CAUTION

Reason:
The product contains a precautionary statement
indicating possible traces of nuts.
```

------------------------------------------------------------------------

## Why This Project?

The goal is not simply to answer:

> "Does this product contain an allergen?"

The more useful question is:

> **"Is this product potentially safe for me?"**

Different users may have different allergies. Therefore, allergen
detection should be connected to an individual's allergy profile rather
than producing a single generic result.

By combining food-label understanding with personalized risk assessment,
**Wait What's In This?** aims to make ingredient interpretation faster,
more accessible, and easier to understand.

------------------------------------------------------------------------

## Data Source

Product data is sourced from **Open Food Facts**, an open database
containing information about food products, ingredients, allergens,
nutrition, and related product information.

Project data is used for educational and research purposes.

------------------------------------------------------------------------

## Future Scope

Future versions of the project may include:

-   Multilingual ingredient recognition
-   Improved OCR for curved and low-quality packaging
-   Ingredient synonym detection
-   Hidden allergen identification
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
