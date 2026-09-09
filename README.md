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

The controlled OCR research benchmark is now **complete and frozen**.

## Benchmark Composition

- **50** candidate images were selected across 7 controlled languages (French, English, German, Spanish, Dutch, Italian, Portuguese).
- **11** images were excluded after manual review (blurry, cropped, or otherwise not legitimately transcribable) and were never treated as ground truth.
- **39** images form the final evaluated benchmark.

A manually verified transcription set was produced specifically for this evaluation, so OCR quality is measured against genuine human-verified ground truth rather than solely against Open Food Facts metadata.

## OCR Text Quality

| Metric | Value |
|---|---:|
| Mean OCR Confidence | 0.5531 |
| Mean Character Error Rate (CER) | 0.6568 |
| Mean Word Error Rate (WER) | 0.9368 |
| Ingredient-Section Extraction Rate | 74.36% |

## Declared and Trace Allergen Detection: OCR Text vs. Clean Text

Results are reported for two conditions: the actual OCR pipeline output ("OCR pipeline"), and the same matcher run directly on the manually verified transcription ("clean-text upper bound"). The gap between them isolates how much OCR noise costs the system, separately from the matcher's own limitations.

### Declared Allergens

| Metric | OCR Pipeline | Clean-Text Upper Bound |
|---|---:|---:|
| Precision | 0.8214 | 0.8857 |
| Recall | 0.5111 | 0.6889 |
| F1 Score | 0.6301 | 0.7750 |
| Exact Agreement | 0.4615 | 0.6667 |

### Trace Allergens

| Metric | OCR Pipeline | Clean-Text Upper Bound |
|---|---:|---:|
| Precision | 0.6667 | 0.8182 |
| Recall | 0.1500 | 0.2250 |
| F1 Score | 0.2449 | 0.3529 |
| Exact Agreement | 0.5128 | 0.5641 |

### Risk Classification Accuracy

| Condition | Accuracy |
|---|---:|
| OCR Pipeline | 51.28% (20/39) |
| Clean-Text Upper Bound | 82.05% (32/39) |

## Error Analysis

- **10 of 39** images failed ingredient-section extraction entirely.
- Of the declared-allergen false negatives measured on OCR text, **9** are directly attributable to OCR text loss (the matcher would have caught them on the clean transcription), while **13** remain missed even on clean text — a matcher-side limitation independent of OCR.
- Of the trace-allergen false negatives measured on OCR text, **6** are attributable to OCR text loss, while **28** remain missed even on clean text, reinforcing that trace/precautionary recall is the system's dominant weakness independent of OCR quality.

## Per-Language OCR Performance

| Language | Samples | Mean CER | Mean WER | Extraction Rate |
|---|---:|---:|---:|---:|
| German | 4 | 0.5472 | 0.7753 | 75.00% |
| English | 5 | 0.5908 | 0.8483 | 80.00% |
| Spanish | 5 | 0.2660 | 0.5505 | 100.00% |
| French | 15 | 0.7927 | 1.0081 | 60.00% |
| Italian | 3 | 1.2549 | 2.0000 | 66.67% |
| Dutch | 4 | 0.4932 | 0.8226 | 100.00% |
| Portuguese | 3 | 0.5053 | 0.6762 | 66.67% |

## Interpretation

The gap between OCR-pipeline and clean-text-upper-bound results shows that OCR and ingredient-section extraction quality are significant, measurable sources of end-to-end error, independent of the allergen matcher itself. Declared-allergen detection degrades substantially under OCR noise (F1 0.7750 → 0.6301), and trace-allergen detection — already the weaker of the two on clean text — degrades further still (F1 0.3529 → 0.2449).

As with the text-only evaluation, the `declared_allergens`/`trace_allergens` reference labels used here are Open Food Facts metadata, treated as reference annotation rather than ground truth. The manually transcribed ingredient text, by contrast, is genuine human-verified OCR ground truth, transcribed directly from each image.

---

# ML Extension and Research Evaluation

Beyond the deterministic matcher described above, the project includes a separate research investigation into whether statistical and machine-learning methods could improve on the ontology-driven matching approach. This was carried out as an additional experimental track, not as a redesign of the live system.

**The existing rule-based matcher remains the final live matching architecture.** None of the ML components described below are part of the deployed allergen-matching path.

Full experimental records, before/after benchmarks, and decision logs for every phase are documented in `ML_EXTENSION_PLAN.md` and `data/research/ml/`.

## Phase 1: Weak-Supervised Trace/Declared Classifier

A classifier (TF-IDF word and character n-gram features with Logistic Regression) was trained on weak labels derived from the existing rule-based declared/trace splitter, and evaluated on a leak-free development subset of the main dataset (excluding all products present in the 300-product held-out set).

The classifier did not outperform the deterministic baseline on either declared or trace detection. It was **not integrated into the live pipeline**.

## Phase 2: Multilingual Embedding Candidate Generation

Frozen, pretrained multilingual sentence embeddings were evaluated as a candidate-generation layer intended to propose allergen mentions the exact/fuzzy dictionary matcher might miss, with candidates verified through the existing negation and context-exclusion rules before being counted.

This did not outperform the deterministic approach for final allergen matching. Two specific failure modes were identified during evaluation:

- Unreliable embeddings for very short, single-word ingredient phrases.
- Structural false positives, where semantically unrelated ingredients sharing the same grammatical pattern (for example, different types of seeds) were incorrectly grouped together by embedding similarity.

This candidate-generation approach was **not integrated into live matching**. It was, however, useful as the underlying mechanism for semi-automatic synonym and ontology discovery (Phase 3).

## Phase 3: Human-Approved Synonym Expansion

Using the same frozen embeddings, 118 candidate synonym terms were generated from the dataset's ingredient vocabulary and reviewed individually, allergen group by allergen group.

- **118** candidate terms generated
- **9** terms approved after human review
- **109** terms rejected

The 9 approved terms were added to `data/allergen_dictionary.json`:

- 4 milk terms
- 3 tree_nut terms
- 2 wheat_gluten terms

No existing dictionary entries were removed or modified, and the matching logic in `scripts/allergen_matcher.py` was not changed. A backup of the dictionary from immediately before this change is preserved at `data/research/ml/synonym_proposals_v1/backup/allergen_dictionary.pre_synonym_v1.json`.

### Before/After Validation (963-Product Leak-Free Set)

This 963-product set excludes every product present in the 300-product held-out set, so the held-out set was not used to make this decision.

**Declared Allergens**

| Metric | Before | After |
|---|---:|---:|
| Precision | 0.9395 | 0.9381 |
| Recall | 0.7883 | 0.7977 |
| F1 Score | 0.8573 | 0.8622 |
| Exact Agreement | 0.7902 | 0.7975 |

**Trace Allergens**

| Metric | Before | After |
|---|---:|---:|
| Precision | 0.9474 | 0.9480 |
| Recall | 0.4016 | 0.4064 |
| F1 Score | 0.5640 | 0.5689 |
| Exact Agreement | 0.6978 | 0.6999 |

F1 score and exact-match agreement improved for both declared and trace allergen detection after the addition.

A small decrease in declared precision was also observed (0.9395 → 0.9381). This is disclosed rather than omitted: the products responsible for this decrease were investigated individually rather than treated as acceptable noise. In both cases, the product's ingredient text clearly indicated milk content, while the corresponding Open Food Facts reference tags were empty. These are treated as likely reference-label gaps in the Open Food Facts metadata rather than confirmed matcher errors, consistent with this project's existing position that Open Food Facts metadata is a reference annotation source and not verified ground truth.

Full diff and validation evidence: `data/research/ml/synonym_proposals_v1/dictionary_application_result.json`.

## Phase 4: Confidence-Aware Abstention

This phase was marked **not applicable**. No ML or embedding signal from Phases 1, 2, or 5 performed well enough to justify deployment as a gating or abstention mechanism, so no speculative confidence-abstention component was added to the system.

## Phase 5: OCR-Confidence Correlation

A pre-registered statistical test checked whether the OCR pipeline's existing confidence score correlates with OCR text quality (character error rate) on the 39-image OCR benchmark, as a precondition for using it in downstream confidence-aware flagging.

- Pre-registered Pearson correlation: r = -0.227, p = 0.165 (not significant)
- Exploratory Spearman correlation: r = -0.346, p = 0.031 (significant, but not the pre-registered test)

Because the pre-registered criterion was not met, OCR confidence was **not wired into the live pipeline**. The Spearman result is reported here explicitly as an exploratory finding, not a confirmatory one.

## Overall Conclusion

Across this evaluation, applying machine-learning methods directly to the live allergen-matching path (Phases 1, 2, and 5) did not improve on the existing deterministic, ontology-driven matcher under this project's current low-resource multilingual setting.

The only validated improvement came from a human-reviewed application of the same embedding technology to ontology and synonym expansion (Phase 3), where every addition was manually approved before being added to the dictionary.

The system's final deployed allergen-matching architecture therefore remains deterministic, ontology-driven, explainable, and personalized, exactly as described earlier in this document. The ML experiments in this section serve as a documented research evaluation and as tooling for ontology maintenance, not as a replacement for the verified rule-based matcher.

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
- Controlled OCR benchmark finalized and evaluated (39 images, 7 languages)
- OCR error analysis
- FastAPI backend
- Personalized risk assessment
- React/Vite frontend
- End-to-end application architecture
- Five-phase ML extension evaluation (weak-supervised classifier, embedding candidate generation, human-approved synonym expansion, confidence-abstention assessment, OCR-confidence correlation test)
- Human-approved synonym expansion validated and applied (9 terms added to the allergen dictionary)

## Remaining Research Work

The controlled OCR benchmark, manual transcription verification, final OCR evaluation, clean-text vs. OCR-text comparison, and OCR error analysis are now complete (see [OCR Evaluation](#ocr-evaluation) above). The five-phase ML extension evaluation is also complete (see [ML Extension and Research Evaluation](#ml-extension-and-research-evaluation) above).

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