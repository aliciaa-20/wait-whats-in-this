# Wait What's In This?

## AI-Powered Personalized Allergy Risk Assessment and Decision Support System

Wait What's In This? is an AI-powered food allergen detection and risk assessment system designed to help users identify potential allergens in packaged food products.

The system analyzes ingredient information from food labels and compares detected ingredients against the user's selected allergies. It provides a simple risk classification to help users understand whether a product may be safe, require caution, or should be avoided.

## Problem Statement

Food ingredient labels can be difficult to interpret, especially for individuals with food allergies. Allergens may appear under different names or ingredient forms, making manual identification challenging.

This project aims to simplify the process by automatically extracting ingredient information and identifying potential allergens using OCR, natural language processing, and personalized allergen matching.

## Objectives

- Extract ingredient information from food product labels using OCR.
- Identify potential allergens from the extracted ingredient text.
- Personalize allergen detection according to the user's selected allergies.
- Distinguish between direct allergens and precautionary statements such as "may contain" or "traces of".
- Provide an easy-to-understand risk classification.
- Explain which ingredient caused the detected risk.

## System Workflow

```text
Food Label Image
       ↓
Image Preprocessing
       ↓
OCR
       ↓
Ingredient Extraction
       ↓
Text Normalization
       ↓
Allergen Matching
       ↓
User Allergy Profile
       ↓
Risk Assessment
       ↓
SAFE / CAUTION / AVOID