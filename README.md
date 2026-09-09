# Wait What's In This?

## AI-Powered Personalized Food Allergen Detection and Risk Assessment

> **Scan it. Understand it. Know your risk.**

**Wait What's In This?** is a research-oriented decision-support system for personalized food allergen detection from packaged food labels.

The system combines **OCR, multilingual NLP, allergen ontology-based matching, contextual rule processing, and personalized risk assessment** to convert complex ingredient labels into an interpretable result.

The project is designed not only as an application, but also as an experimental framework for studying multilingual allergen detection, contextual ingredient matching, OCR-based label analysis, and personalized risk assessment.

---

## Problem Statement

Food ingredient labels can be difficult to interpret, particularly for users managing food allergies.

Potential allergens may:

- Appear under different names, synonyms, or ingredient forms
- Be embedded within long ingredient lists
- Use scientific or unfamiliar terminology
- Appear in different languages
- Appear inside precautionary statements such as "may contain" or "traces of"
- Be incorrectly identified by simple keyword matching
- Require users to manually compare ingredients against their individual allergy profiles

A simple keyword search is therefore insufficient for reliable allergen interpretation.

**Wait What's In This?** addresses this problem through a multilingual, ontology-driven and context-aware allergen matching pipeline combined with OCR-based ingredient extraction and personalized risk assessment.

---

## Research Objectives

The project aims to:

1. Build a curated food-product dataset from Open Food Facts.
2. Develop a multilingual allergen dictionary and ontology covering common allergen terminology and derivatives.
3. Detect allergens from ingredient text using contextual matching rather than simple keyword matching.
4. Distinguish directly declared allergens from precautionary or trace allergen statements.
5. Handle multilingual ingredient terminology, normalization, negation, and known false-positive contexts.
6. Compare the proposed matcher against keyword-based baselines.
7. Evaluate the matcher using both a large reference dataset and a held-out evaluation set.
8. Integrate OCR for ingredient extraction from food-label images.
9. Provide personalized risk assessment based on a user's selected allergy profile.
10. Provide interpretable evidence showing why a product was classified as `SAFE`, `CAUTION`, or `AVOID`.

---

# System Architecture

```text
                    FOOD LABEL IMAGE
                           |
                           v
                 IMAGE PREPROCESSING
                           |
                           v
                          OCR
                           |
                           v
              INGREDIENT SECTION EXTRACTION
                           |
                           v
                 TEXT NORMALIZATION
                           |
                           v
              MULTILINGUAL ALLERGEN
                    MATCHING ENGINE
                    /             \
                   /               \
          DECLARED ALLERGENS   TRACE ALLERGENS
                   \               /
                    \             /
                     v           v
                    USER ALLERGY PROFILE
                           |
                           v
                    RISK ASSESSMENT
                           |
              +------------+------------+
              |            |            |
              v            v            v
            SAFE        CAUTION       AVOID
              |            |            |
              +------------+------------+
                           |
                           v
                    EXPLAINABLE RESULT
```

The implemented application connects this research pipeline to a FastAPI backend and React frontend.

---

# Key Features

## 1. OCR-Based Ingredient Extraction

Food-label images can be uploaded to the system and processed using **EasyOCR** with OpenCV-based preprocessing.

The OCR pipeline includes:

- Image preprocessing
- Grayscale conversion
- Upscaling
- CLAHE enhancement
- Denoising
- Adaptive thresholding
- Multiple OCR passes
- Confidence-based pass selection
- Duplicate-line removal
- Ingredient-section detection
- Multilingual OCR configuration

Supported OCR languages currently include:

- English
- French
- German
- Spanish
- Dutch
- Italian
- Portuguese

If ingredient extraction fails, the system does not silently classify the product as safe. It returns an appropriate unknown/error state.

---

## 2. Multilingual Allergen Ontology

The allergen matching system covers nine allergen categories:

| Allergen ID | Allergen |
|---|---|
| `milk` | Milk / Dairy |
| `egg` | Egg |
| `peanut` | Peanut |
| `tree_nut` | Tree Nuts |
| `soy` | Soy |
| `wheat_gluten` | Wheat / Gluten |
| `fish` | Fish |
| `shellfish` | Shellfish |
| `sesame` | Sesame |

The dictionary contains multilingual terminology, synonyms, derivatives, spelling variations, and ingredient-specific expressions.

---

## 3. Context-Aware Allergen Matching

The system goes beyond exact keyword matching.

The matching engine includes:

- Unicode normalization using NFKC/NFKD
- Accent-insensitive matching
- Longest-match-first synonym matching
- Multilingual synonym handling
- Ingredient derivatives
- Negation detection
- Declared allergen detection
- Precautionary/trace statement detection
- Context-specific exclusion rules
- Evidence extraction

Examples of contextual exclusions include:

- Plant-based milk should not automatically be classified as dairy.
- Coconut should not automatically be classified as a tree nut.
- Cocoa butter should not automatically be classified as dairy.
- Peanut or almond butter should not automatically be classified as dairy.
- "Gluten-free" should not be interpreted as the presence of gluten.

---

# Risk Classification

The system separates direct allergen detection from precautionary allergen information.

| Result | Meaning |
|---|---|
| **SAFE** | No selected allergen was detected |
| **CAUTION** | A selected allergen appears in a precautionary/trace context |
| **AVOID** | A selected allergen was directly detected |

The system also returns the allergen and ingredient evidence responsible for the classification.

For example:

```text
Detected allergen: Milk
Evidence: milk powder
Risk: AVOID
```

For a precautionary statement:

```text
Detected trace allergen: Tree Nuts
Evidence: may contain nuts
Risk: CAUTION
```

---

# Personalized Risk Assessment

Users can select the allergens they need to avoid.

The backend compares detected allergens against the selected allergy profile.

For example:

```text
User allergies:
    milk, peanut

Detected direct allergens:
    milk

Detected trace allergens:
    tree_nut
```

The system prioritizes the user's selected allergens when generating the personalized result.

This allows two users to receive different risk assessments for the same product depending on their allergy profiles.

---

# Technology Stack

| Component | Technology |
|---|---|
| Programming Language | Python |
| Data Processing | Pandas, NumPy |
| Image Processing | OpenCV, Pillow |
| OCR | EasyOCR |
| NLP | Custom multilingual normalization and contextual matching |
| Allergen Detection | Ontology/rule-based matching engine |
| Backend | FastAPI |
| Frontend | React + Vite |
| Frontend Styling | Tailwind CSS |
| Data Source | Open Food Facts |
| Data Formats | CSV, JSON |
| Version Control | Git, GitHub |

---

# Dataset

The project uses product information from **Open Food Facts**, including:

- Product code
- Product name
- Ingredient text
- Ingredient tags
- Allergen tags
- Trace allergen information
- Product language

Products are identified using their product codes to remove duplicate records.

## Current Research Dataset

The cleaned dataset contains:

- **1,612 unique product records**
- **1,263 products with ingredient text**

The research pipeline also contains a separate:

- **300-product held-out evaluation set**

The held-out set was selected to include diverse cases such as:

- Declared allergens
- Trace allergens
- Multiple allergens
- Difficult contextual cases
- Products without allergen metadata

The 300-product evaluation set uses **Open Food Facts allergen metadata as the reference annotation**. It is not presented as manually verified clinical ground truth.

---

# Research Evaluation

The project includes a dedicated experimental evaluation pipeline rather than relying only on application-level testing.

## Main Text-Based Evaluation

The proposed matcher was evaluated on 1,263 products containing ingredient text.

### Proposed Matcher

| Metric | Score |
|---|---:|
| Precision | **0.9369** |
| Recall | **0.7940** |
| F1 Score | **0.8595** |
| Exact Allergen-Set Agreement | **0.7997** |

These results indicate strong precision and overall allergen-set agreement while also highlighting remaining recall limitations.

---

## Held-Out Evaluation

A frozen 300-product held-out reference set was evaluated without tuning the matcher against it.

### Declared Allergens

| Metric | Score |
|---|---:|
| Precision | **0.9257** |
| Recall | **0.8202** |
| F1 Score | **0.8698** |
| Exact Agreement | **0.8300** |

### Trace Allergens

| Metric | Score |
|---|---:|
| Precision | **0.9625** |
| Recall | **0.3105** |
| F1 Score | **0.4695** |
| Exact Agreement | **0.7200** |

The trace results reveal an important limitation: the current system is conservative when identifying precautionary allergen statements.

---

# Baseline Comparison

The proposed matcher was compared with two keyword-based baselines on the same held-out products.

| Method | Precision | Recall | F1 | Exact |
|---|---:|---:|---:|---:|
| Exact Keyword | 0.5189 | 0.8421 | 0.6421 | 0.5333 |
| Normalized Keyword | 0.4875 | 0.8553 | 0.6210 | 0.4933 |
| **Proposed Matcher** | **0.9257** | **0.8202** | **0.8698** | **0.8300** |

The proposed contextual matcher substantially improves precision, F1 score, and exact allergen-set agreement compared with both keyword baselines, while maintaining competitive recall.

---

# Ablation Study

The matcher was also evaluated under different configurations to study the contribution of contextual processing.

| Configuration | Precision | Recall | F1 | Exact |
|---|---:|---:|---:|---:|
| Exact Keyword | 0.6679 | 0.8242 | 0.7379 | 0.6611 |
| Normalized Keyword | 0.6665 | 0.8358 | 0.7416 | 0.6635 |
| Normalized + Negation | 0.6673 | 0.8358 | 0.7421 | 0.6651 |
| Normalized + Context | 0.6826 | 0.8296 | 0.7490 | 0.6904 |
| **Full Proposed Matcher** | **0.9369** | **0.7940** | **0.8595** | **0.7997** |

The full system incorporates multilingual ontology terms, contextual matching, exclusions, direct/trace separation, and other processing components.

Because the full configuration changes multiple components simultaneously, the results should be interpreted as evidence for the overall pipeline rather than as an isolated causal measurement of one individual rule.

---

# Error Analysis

The text-based evaluation includes explicit error analysis.

On the 1,263-product evaluation set:

- Exact matches: **79.97%**
- Partial matches: **7.44%**
- False negatives: **9.98%**
- False positives: **2.45%**

The largest sources of missed allergen detections were:

1. Milk
2. Wheat / Gluten
3. Tree Nuts
4. Soy
5. Egg

The relatively high precision and lower trace recall indicate that the system currently favors conservative detection in ambiguous precautionary contexts.

This behavior is important for the research evaluation and is treated as a limitation rather than hidden from the results.

---

# OCR Evaluation

The OCR pipeline is implemented and integrated with the allergen matching engine.

The final research benchmark is being constructed using food-label ingredient images with controlled supported languages.

The planned evaluation measures include:

- Character Error Rate (CER)
- Word Error Rate (WER)
- Ingredient-section extraction accuracy
- Declared allergen precision, recall, and F1
- Trace allergen precision, recall, and F1
- Risk classification accuracy
- Clean-text vs. OCR-text performance comparison
- OCR error analysis

A manually verified transcription set is being used specifically for the OCR evaluation so that OCR quality is not evaluated solely against Open Food Facts metadata.

**Final OCR benchmark numbers will be added after the benchmark is frozen and evaluated.**

---

# Application Architecture

## Backend

The FastAPI backend exposes:

```text
GET  /
GET  /health
GET  /allergens
POST /analyze
```

The main `/analyze` endpoint accepts:

- Food-label image
- Selected allergy profile
- OCR language

The backend invokes the existing research pipeline rather than implementing a separate simplified detection algorithm.

---

## Frontend

The frontend is implemented using:

- React
- Vite
- Tailwind CSS

The frontend provides the user-facing workflow for:

1. Selecting an allergy profile
2. Uploading or capturing a food-label image
3. Selecting OCR language
4. Sending the image to the backend
5. Displaying OCR and ingredient extraction results
6. Displaying detected allergens
7. Displaying personalized risk
8. Showing supporting evidence and warnings

The frontend communicates with the FastAPI backend and does not independently reproduce the allergen matching or risk-classification logic.

---

# Project Structure

```text
wait-whats-in-this/
|
+-- backend/
|   +-- app.py
|
+-- frontend/
|   +-- src/
|   +-- package.json
|   +-- vite.config.js
|   +-- tailwind.config.js
|
+-- data/
|   +-- benchmark/
|   |   +-- images/
|   |   +-- metadata.csv
|   |   +-- image_availability.csv
|   |
|   +-- research/
|       +-- ground_truth.csv
|       +-- heldout_predictions.csv
|       +-- heldout_results.json
|       +-- heldout_baseline_comparison.json
|       +-- sampling_summary.json
|
+-- scripts/
|   +-- allergen_matcher.py
|   +-- match_allergens.py
|   +-- ocr_processor.py
|   +-- analyze_label.py
|   +-- benchmark_matcher.py
|   +-- benchmark_baselines.py
|   +-- benchmark_ablation.py
|   +-- benchmark_ocr.py
|   +-- analyze_matcher_errors.py
|   +-- check_ocr_image_availability.py
|   +-- download_ocr_dataset.py
|   +-- clean_dataset.py
|   +-- analyze_allergens.py
|   +-- diagnose_unmatched.py
|   +-- get_openfoodfacts_data.py
|   +-- test_allergen_matcher.py
|
+-- test_images/
|
+-- requirements.txt
+-- README.md
+-- .gitignore
```

---

# Installation

## Backend / Research Environment

Clone the repository:

```bash
git clone https://github.com/aliciaa-20/wait-whats-in-this.git
cd wait-whats-in-this
```

Create a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

If the environment's shell Python path is not resolving correctly, the virtual-environment interpreter can be invoked directly:

```bash
./venv/bin/python
```

---

# Running the Backend

From the project root:

```bash
./venv/bin/python -m uvicorn backend.app:app --reload
```

The FastAPI service will be available locally.

Interactive API documentation:

```text
/docs
```

The `/health` endpoint can be used to verify that the OCR and analysis pipeline is available.

---

# Running the Frontend

From the frontend directory:

```bash
cd frontend
npm install
npm run dev
```

The frontend connects to the locally running FastAPI backend.

---

# Running Text-Based Evaluation

The repository contains scripts for reproducing the main matcher experiments.

Examples:

```bash
./venv/bin/python scripts/benchmark_matcher.py
```

```bash
./venv/bin/python scripts/benchmark_baselines.py
```

```bash
./venv/bin/python scripts/benchmark_ablation.py
```

```bash
./venv/bin/python scripts/analyze_matcher_errors.py
```

---

# Running OCR Analysis

A food-label image can be analyzed directly using:

```bash
./venv/bin/python -m scripts.analyze_label "path/to/image.jpg"
```

Specify an OCR language when required:

```bash
./venv/bin/python -m scripts.analyze_label \
    "path/to/image.jpg" \
    --language fr
```

JSON output is also supported:

```bash
./venv/bin/python -m scripts.analyze_label \
    "path/to/image.jpg" \
    --language fr \
    --json
```

---

# Reproducibility

Research experiments are separated from the application layer.

The repository stores:

- Dataset preparation scripts
- Allergen dictionary
- Benchmark scripts
- Held-out evaluation data
- Baseline comparison results
- Ablation results
- Error-analysis outputs
- OCR benchmark infrastructure

The held-out evaluation set is kept separate from development data to reduce the risk of tuning the matcher against the final evaluation.

---

# Research Limitations

Several limitations are explicitly considered.

### Open Food Facts reference quality

Open Food Facts is a crowdsourced database. Its allergen metadata may contain missing, inconsistent, or incorrect information.

Therefore, Open Food Facts metadata is treated as a **reference annotation source**, not absolute ground truth.

### Trace allergen detection

Trace allergen detection currently has substantially lower recall than declared allergen detection.

This is an important research limitation and an area for further improvement.

### OCR variability

OCR performance can vary significantly depending on:

- Image resolution
- Lighting
- Blur
- Perspective distortion
- Font size
- Packaging design
- Text orientation
- Language

The final OCR benchmark is therefore evaluated separately from the text-only matcher.

### Safety

The system is a research and decision-support prototype. It cannot guarantee the absence of allergens and must not be treated as a medical or clinical diagnostic system.

---

# Current Research Status

## Completed

- Open Food Facts dataset collection
- Dataset cleaning and product-code deduplication
- Allergen and trace analysis
- Multilingual allergen dictionary
- Allergen ontology/matching layer
- Text normalization
- Context-aware allergen matching
- Negation handling
- Direct vs trace detection
- Context-specific exclusions
- Text-only matcher evaluation
- Keyword baselines
- Ablation study
- Held-out 300-product evaluation
- Matcher error analysis
- OCR implementation
- OCR-to-matcher integration
- FastAPI backend
- Personalized risk assessment
- React/Vite frontend
- End-to-end application architecture

## Remaining Research Work

- Finalize the controlled OCR benchmark
- Manually verify ingredient-section transcriptions for the OCR benchmark
- Run final OCR evaluation
- Compare clean-text and OCR-text performance
- Complete OCR error analysis
- Update final research results
- Freeze the experimental version
- Prepare the final research paper

---

# Research Contribution

The primary research contribution is a **multilingual, ontology-driven and context-aware allergen matching framework** designed to improve upon simple ingredient keyword matching.

The system combines:

1. Multilingual allergen terminology
2. Ingredient normalization
3. Context-aware matching
4. Negation handling
5. Declared vs trace separation
6. Context-specific exclusion rules
7. Personalized allergy profiles
8. OCR-based ingredient extraction
9. Explainable evidence generation

The experimental results demonstrate that contextual allergen matching can substantially improve precision, F1 score, and exact allergen-set agreement over simple keyword baselines.

The remaining OCR evaluation will establish how much of this performance is retained when the system operates directly on real food-label images.

---

# Data Source

Product information and label images are sourced from **Open Food Facts**.

Open Food Facts provides open food-product data contributed by its community.

The project uses the data for educational and research purposes and follows the applicable Open Food Facts data and image licensing requirements.

---

# Disclaimer

**Wait What's In This? is an educational and research project and is not a medical diagnostic tool.**

The system should not replace:

- Official product labeling
- Manufacturer information
- Medical advice
- Advice from a qualified healthcare professional

Users with severe or life-threatening allergies should independently verify product information before consuming a product.

---

# License

This project is developed for educational and research purposes.

See the repository and Open Food Facts licensing information for the applicable software and dataset terms.

---

## Project Status

**Research prototype: Active development**

The text-based allergen detection and personalized application pipeline are implemented and experimentally evaluated. The remaining research milestone is the controlled OCR benchmark and final image-to-risk evaluation.