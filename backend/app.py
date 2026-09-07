from pathlib import Path
import shutil
import tempfile
import sys
import json

from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware


# ============================================================
# PROJECT PATH
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


# ============================================================
# EXISTING PROJECT PIPELINE
# ============================================================

from scripts.analyze_label import analyze_label
from scripts.allergen_matcher import ALLERGENS, load_dictionary


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="AI Food Allergen Detection API",
    description=(
        "AI-powered food label analysis using OCR, "
        "ingredient extraction, allergen matching, "
        "and personalized risk assessment."
    ),
    version="1.0.0",
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# LOAD ALLERGEN DICTIONARY
# ============================================================

DICTIONARY = load_dictionary()


# ============================================================
# ALLERGEN DISPLAY NAMES
# ============================================================

ALLERGEN_NAMES = {
    "milk": "Milk / Dairy",
    "egg": "Egg",
    "peanut": "Peanut",
    "tree_nut": "Tree Nuts",
    "soy": "Soy",
    "wheat_gluten": "Wheat / Gluten",
    "fish": "Fish",
    "shellfish": "Shellfish",
    "sesame": "Sesame",
}


# ============================================================
# ALLERGEN INPUT ALIASES
# ============================================================

ALLERGEN_ALIASES = {
    "milk": "milk",
    "dairy": "milk",
    "milk/dairy": "milk",

    "egg": "egg",
    "eggs": "egg",

    "peanut": "peanut",
    "peanuts": "peanut",

    "tree_nut": "tree_nut",
    "tree nuts": "tree_nut",
    "tree-nuts": "tree_nut",
    "nuts": "tree_nut",

    "soy": "soy",
    "soya": "soy",

    "wheat": "wheat_gluten",
    "gluten": "wheat_gluten",
    "wheat/gluten": "wheat_gluten",
    "wheat_gluten": "wheat_gluten",

    "fish": "fish",

    "shellfish": "shellfish",
    "shell fish": "shellfish",

    "sesame": "sesame",

    "other": "other",
}


# ============================================================
# SUPPORTED IMAGE FORMATS
# ============================================================

ALLOWED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".bmp",
}


# Maximum uploaded image size: 10 MB
MAX_FILE_SIZE = 10 * 1024 * 1024


# ============================================================
# HELPER: PARSE USER ALLERGIES
# ============================================================

def parse_allergies(value: str):

    if not value:
        return []

    value = value.strip()

    if not value:
        return []

    # --------------------------------------------------------
    # Accept JSON:
    #
    # ["milk", "peanut"]
    # --------------------------------------------------------

    try:

        parsed = json.loads(value)

        if isinstance(parsed, str):
            parsed = [parsed]

        if isinstance(parsed, list):

            raw_allergies = parsed

        else:

            raw_allergies = []

    except json.JSONDecodeError:

        # ----------------------------------------------------
        # Also accept:
        #
        # milk, peanut, egg
        # ----------------------------------------------------

        raw_allergies = value.split(",")

    normalized = []
    unsupported = []

    for allergy in raw_allergies:

        if not isinstance(allergy, str):
            continue

        allergy = allergy.strip().lower()

        if not allergy:
            continue

        mapped = ALLERGEN_ALIASES.get(allergy)

        if mapped is None:

            unsupported.append(allergy)

            continue

        if mapped not in normalized:
            normalized.append(mapped)

    return normalized, unsupported


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():

    return {
        "message": "AI Food Allergen Detection API is running",
        "status": "success",
    }


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
def health_check():

    return {
        "status": "healthy",
        "ocr": "EasyOCR",
        "pipeline": (
            "OCR -> ingredient extraction -> "
            "allergen matcher -> risk assessment"
        ),
    }


# ============================================================
# SUPPORTED ALLERGENS
# ============================================================

@app.get("/allergens")
def get_supported_allergens():

    return {
        "allergens": [
            {
                "id": allergen,
                "name": ALLERGEN_NAMES.get(
                    allergen,
                    allergen,
                ),
            }
            for allergen in ALLERGENS
        ]
    }


# ============================================================
# MAIN ANALYSIS ENDPOINT
# ============================================================

@app.post("/analyze")
async def analyze_food_label(
    file: UploadFile = File(...),
    allergies: str = Form("[]"),
):

    # --------------------------------------------------------
    # Validate filename
    # --------------------------------------------------------

    if not file.filename:

        raise HTTPException(
            status_code=400,
            detail="No image file was provided.",
        )


    # --------------------------------------------------------
    # Validate extension
    # --------------------------------------------------------

    extension = Path(
        file.filename
    ).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:

        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported image format. "
                "Use JPG, JPEG, PNG, WEBP, or BMP."
            ),
        )


    # --------------------------------------------------------
    # Parse user allergies
    # --------------------------------------------------------

    selected_allergies, unsupported_allergies = (
        parse_allergies(allergies)
    )


    # --------------------------------------------------------
    # Read uploaded file
    # --------------------------------------------------------

    file_contents = await file.read()

    if not file_contents:

        raise HTTPException(
            status_code=400,
            detail="Uploaded image is empty.",
        )


    # --------------------------------------------------------
    # Check file size
    # --------------------------------------------------------

    if len(file_contents) > MAX_FILE_SIZE:

        raise HTTPException(
            status_code=413,
            detail=(
                "Image is too large. "
                "Maximum allowed size is 10 MB."
            ),
        )


    temporary_path = None


    try:

        # ----------------------------------------------------
        # Save image temporarily
        # ----------------------------------------------------

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=extension,
        ) as temporary_file:

            temporary_file.write(
                file_contents
            )

            temporary_path = Path(
                temporary_file.name
            )


        # ----------------------------------------------------
        # RUN EXISTING STEP 9 PIPELINE
        # ----------------------------------------------------

        result = analyze_label(
            temporary_path,
            DICTIONARY,
        )


        # ----------------------------------------------------
        # Extract results
        # ----------------------------------------------------

        ocr_result = result.get(
            "ocr",
            {},
        )

        allergen_result = result.get(
            "allergens",
            {},
        )


        extraction_status = allergen_result.get(
            "extraction_status",
            "NOT_FOUND",
        )

        declared_allergens = allergen_result.get(
            "declared_allergens",
            [],
        )

        trace_allergens = allergen_result.get(
            "trace_allergens",
            [],
        )

        matches = allergen_result.get(
            "matches",
            [],
        )

        trace_matches = allergen_result.get(
            "trace_matches",
            [],
        )

        general_risk = allergen_result.get(
            "risk",
            "UNKNOWN",
        )


        # ----------------------------------------------------
        # If OCR / ingredient extraction failed
        # ----------------------------------------------------

        if extraction_status != "FOUND":

            return {
                "success": True,

                "filename": file.filename,

                "risk": {
                    "status": "UNKNOWN",
                    "message": (
                        "Ingredient information could not "
                        "be reliably extracted from the image."
                    ),
                },

                "user_profile": {
                    "selected_allergies": selected_allergies,
                    "unsupported_allergies": (
                        unsupported_allergies
                    ),
                },

                "ocr": ocr_result,

                "ingredients": {
                    "extraction_status": extraction_status,
                    "text": ocr_result.get(
                        "ingredient_text",
                        "",
                    ),
                },

                "allergens": {
                    "declared": declared_allergens,
                    "trace": trace_allergens,
                    "matches": matches,
                    "trace_matches": trace_matches,
                },

                "warning": (
                    "This system is a decision-support "
                    "prototype and should not replace "
                    "checking the original food label."
                ),
            }


        # ----------------------------------------------------
        # PERSONALIZED ALLERGEN MATCHING
        # ----------------------------------------------------

        selected_set = set(
            selected_allergies
        )

        declared_set = set(
            declared_allergens
        )

        trace_set = set(
            trace_allergens
        )


        relevant_declared = sorted(
            selected_set.intersection(
                declared_set
            )
        )

        relevant_trace = sorted(
            selected_set.intersection(
                trace_set
            )
        )


        # ----------------------------------------------------
        # Determine personalized risk
        # ----------------------------------------------------

        if not selected_set:

            personalized_risk = general_risk

            personalized_message = (
                "No personal allergy profile was "
                "provided, so the general detected "
                "allergen risk is shown."
            )

        elif relevant_declared:

            personalized_risk = "AVOID"

            names = [
                ALLERGEN_NAMES.get(
                    allergen,
                    allergen,
                )
                for allergen in relevant_declared
            ]

            personalized_message = (
                "A selected allergen was detected "
                "as a declared ingredient: "
                + ", ".join(names)
                + "."
            )

        elif relevant_trace:

            personalized_risk = "CAUTION"

            names = [
                ALLERGEN_NAMES.get(
                    allergen,
                    allergen,
                )
                for allergen in relevant_trace
            ]

            personalized_message = (
                "A selected allergen was detected "
                "only in a precautionary trace statement: "
                + ", ".join(names)
                + "."
            )

        else:

            personalized_risk = "SAFE"

            personalized_message = (
                "None of the selected allergens were "
                "detected in the declared or trace "
                "ingredient sections."
            )


        # ----------------------------------------------------
        # Build human-readable detected allergens
        # ----------------------------------------------------

        declared_names = [
            ALLERGEN_NAMES.get(
                allergen,
                allergen,
            )
            for allergen in declared_allergens
        ]

        trace_names = [
            ALLERGEN_NAMES.get(
                allergen,
                allergen,
            )
            for allergen in trace_allergens
        ]


        # ----------------------------------------------------
        # Return complete response
        # ----------------------------------------------------

        return {

            "success": True,

            "filename": file.filename,

            "user_profile": {
                "selected_allergies": selected_allergies,
                "selected_allergy_names": [
                    ALLERGEN_NAMES.get(
                        allergy,
                        allergy,
                    )
                    for allergy in selected_allergies
                ],
                "unsupported_allergies": (
                    unsupported_allergies
                ),
            },

            "ocr": {
                "confidence": ocr_result.get(
                    "confidence",
                    0.0,
                ),
                "raw_text": ocr_result.get(
                    "raw_text",
                    "",
                ),
            },

            "ingredients": {
                "extraction_status": extraction_status,
                "ingredient_text": ocr_result.get(
                    "ingredient_text",
                    "",
                ),
                "declared_text": allergen_result.get(
                    "declared_text",
                    "",
                ),
                "trace_text": allergen_result.get(
                    "trace_text",
                    "",
                ),
            },

            "allergens": {

                "declared": declared_allergens,

                "declared_names": declared_names,

                "trace": trace_allergens,

                "trace_names": trace_names,

                "matches": matches,

                "trace_matches": trace_matches,

            },

            "risk": {

                "general": general_risk,

                "personalized": personalized_risk,

                "message": personalized_message,

            },

            "relevant_allergens": {

                "declared": relevant_declared,

                "trace": relevant_trace,

            },

            "warning": (
                "This system is a decision-support "
                "prototype, not a medical diagnosis. "
                "Users with serious allergies should "
                "verify the original product label "
                "and follow appropriate medical advice."
            ),
        }


    except FileNotFoundError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


    except Exception as exc:

        print(
            f"ERROR while analyzing image: {exc}"
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "An error occurred while analyzing "
                "the food label. Check the server "
                "terminal for details."
            ),
        )


    finally:

        # ----------------------------------------------------
        # Delete temporary image
        # ----------------------------------------------------

        if temporary_path is not None:

            try:

                temporary_path.unlink(
                    missing_ok=True
                )

            except Exception:

                pass