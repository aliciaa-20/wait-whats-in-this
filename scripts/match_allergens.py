import ast
import json
import re
import unicodedata
from pathlib import Path

import pandas as pd


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"

PRODUCT_FILE = DATA_DIR / "cleaned_products.csv"
DICTIONARY_FILE = DATA_DIR / "allergen_dictionary.json"


# ============================================================
# PROJECT ALLERGENS
# ============================================================

ALLERGENS = [
    "milk",
    "egg",
    "peanut",
    "tree_nut",
    "soy",
    "wheat_gluten",
    "fish",
    "shellfish",
    "sesame",
]


# ============================================================
# OPEN FOOD FACTS TAG -> PROJECT ALLERGEN
# ============================================================

TAG_TO_ALLERGEN = {
    # Milk
    "milk": "milk",
    "lait": "milk",
    "leche": "milk",
    "leite": "milk",
    "milch": "milk",
    "mlijeko": "milk",
    "latte": "milk",

    # Eggs
    "egg": "egg",
    "eggs": "egg",
    "oeuf": "egg",
    "oeufs": "egg",
    "huevo": "egg",
    "huevos": "egg",
    "ovo": "egg",
    "eier": "egg",

    # Peanut
    "peanut": "peanut",
    "peanuts": "peanut",
    "arachide": "peanut",
    "arachides": "peanut",
    "cacahuete": "peanut",
    "cacahuetes": "peanut",
    "amendoim": "peanut",
    "amendoins": "peanut",

    # Tree nuts
    "nuts": "tree_nut",
    "nut": "tree_nut",
    "tree-nuts": "tree_nut",
    "tree-nut": "tree_nut",
    "noix": "tree_nut",
    "fruits-a-coque": "tree_nut",
    "frutos-de-cascara": "tree_nut",
    "frutos-de-casca-rija": "tree_nut",
    "schalenfruchte": "tree_nut",
    "schalenfrüchte": "tree_nut",

    # Soy
    "soy": "soy",
    "soya": "soy",
    "soja": "soy",

    # Wheat / gluten
    "wheat": "wheat_gluten",
    "weizen": "wheat_gluten",
    "ble": "wheat_gluten",
    "blé": "wheat_gluten",
    "gluten": "wheat_gluten",
    "cereals-with-gluten": "wheat_gluten",
    "cereales-avec-gluten": "wheat_gluten",
    "cereales-con-gluten": "wheat_gluten",

    # Fish
    "fish": "fish",
    "poisson": "fish",
    "pescado": "fish",
    "peixe": "fish",
    "fisch": "fish",

    # Shellfish
    "crustaceans": "shellfish",
    "crustacean": "shellfish",
    "crustaces": "shellfish",
    "crustacés": "shellfish",
    "crustaceos": "shellfish",
    "crustáceos": "shellfish",
    "molluscs": "shellfish",
    "mollusks": "shellfish",

    # Sesame
    "sesame": "sesame",
    "sesamo": "sesame",
    "sésame": "sesame",
    "sesam": "sesame",
}


# ============================================================
# ADDITIONAL PROJECT SYNONYMS
# ============================================================

EXTRA_SYNONYMS = {

    # --------------------------------------------------------
    # MILK
    # --------------------------------------------------------
    "milk": [
        "milk",
        "whole milk",
        "skimmed milk",
        "semi skimmed milk",
        "milk powder",
        "skimmed milk powder",
        "milk solids",
        "milk protein",
        "milk proteins",
        "whey",
        "whey protein",
        "whey powder",
        "lactoserum",
        "lactose",
        "casein",
        "caseinate",
        "sodium caseinate",
        "calcium caseinate",
        "butter",
        "butterfat",
        "cream",
        "creme",
        "crème",
        "cream powder",
        "cheese",
        "fromage",
        "queso",
        "queijo",
        "käse",
        "kaese",
        "yogurt",
        "yoghurt",
        "yaourt",
        "yogur",
        "joghurt",
        "kefir",
        "kéfir",
        "curd",
        "buttermilk",
        "milk chocolate",

        # French
        "lait",
        "lait entier",
        "lait ecreme",
        "lait écrémé",
        "lait en poudre",
        "lait demi ecreme",
        "lait demi écrémé",
        "proteines de lait",
        "protéines de lait",
        "serum de lait",
        "sérum de lait",
        "beurre",
        "beurre de lait",

        # German
        "milch",
        "vollmilch",
        "vollmilchpulver",
        "magermilch",
        "magermilchpulver",
        "milchpulver",
        "milchprotein",
        "molkenpulver",
        "molke",
        "molkenprotein",
        "butter",
        "sahne",
        "rahm",
        "joghurt",
        "käse",
        "kaese",

        # Spanish
        "leche",
        "leche entera",
        "leche desnatada",
        "leche en polvo",
        "proteina de leche",
        "proteína de leche",
        "suero de leche",
        "mantequilla",
        "nata",
        "queso",
        "yogur",

        # Portuguese
        "leite",
        "leite integral",
        "leite em pó",
        "proteina do leite",
        "proteína do leite",
        "soro de leite",
        "manteiga",
        "natas",
        "queijo",
        "iogurte",

        # Arabic
        "حليب",
        "حليب بقري",
        "حليب كامل الدسم",
        "حليب بدون دسم",
        "مسحوق الحليب",
        "قشدة",
        "زبدة",
        "مصل اللبن",
        "مصل الحليب",
        "لاكتوز",
        "كازين",
        "كازينات",
        "خمائر حليبية",
    ],

    # --------------------------------------------------------
    # EGG
    # --------------------------------------------------------
    "egg": [
        "egg",
        "eggs",
        "egg white",
        "egg whites",
        "egg yolk",
        "egg yolks",
        "albumen",
        "albumin",
        "ovalbumin",
        "oeuf",
        "oeufs",
        "blanc d oeuf",
        "blancs d oeufs",
        "jaune d oeuf",
        "jaunes d oeufs",
        "huevo",
        "huevos",
        "clara de huevo",
        "yema de huevo",
        "ovo",
        "ovos",
        "clara de ovo",
        "gema de ovo",
        "eier",
        "ei",
        "eiweiss",
        "eiweiß",

        # Arabic
        "بيض",
        "بيضة",
        "بياض البيض",
        "صفار البيض",
    ],

    # --------------------------------------------------------
    # PEANUT
    # --------------------------------------------------------
    "peanut": [
        "peanut",
        "peanuts",
        "groundnut",
        "groundnuts",
        "arachis",
        "arachide",
        "arachides",
        "cacahuete",
        "cacahuetes",
        "cacahuete",
        "cacahuetes",
        "amendoim",
        "amendoins",
        "jordnød",
        "jordnødder",

        # Arabic
        "فول سوداني",
        "الفول السوداني",
        "الفول السودانى",
        "أراكيس",
    ],

    # --------------------------------------------------------
    # TREE NUTS
    # --------------------------------------------------------
    "tree_nut": [
        "tree nut",
        "tree nuts",
        "nuts",
        "almond",
        "almonds",
        "amande",
        "amandes",
        "almendra",
        "almendras",
        "mandel",
        "mandeln",
        "hazelnut",
        "hazelnuts",
        "noisette",
        "noisettes",
        "avellana",
        "avellanas",
        "hazel",
        "cashew",
        "cashews",
        "caju",
        "cajou",
        "noix de cajou",
        "anacardo",
        "anacardos",
        "pistachio",
        "pistachios",
        "pistache",
        "pistaches",
        "pistacho",
        "pistachos",
        "walnut",
        "walnuts",
        "noix",
        "noix de pecan",
        "noix de pécan",
        "pecan",
        "pecans",
        "macadamia",
        "macadamias",
        "brazil nut",
        "brazil nuts",
        "noix du brésil",
        "noix du bresil",
        "schalenfruchte",
        "schalenfrüchte",

        # Arabic
        "لوز",
        "جوز",
        "بندق",
        "فستق",
        "فستوه",
        "كاجو",
        "جوز البقان",
        "جوز البرازيل",
    ],

    # --------------------------------------------------------
    # SOY
    # --------------------------------------------------------
    "soy": [
        "soy",
        "soya",
        "soybean",
        "soybeans",
        "soy protein",
        "soy proteins",
        "soy flour",
        "soy lecithin",
        "soya lecithin",
        "lecithine de soja",
        "lécithine de soja",
        "soja",
        "sojabohne",
        "sojabohnen",
        "sojaprotein",
        "sojalecithin",
        "sojamehl",
        "soja protein",
        "proteina de soja",
        "proteína de soja",
        "lecitina de soja",
        "proteina de soia",
        "proteína de soja",
        "lecitina de soja",

        # Arabic
        "الصويا",
        "صويا",
        "ليسيثين الصويا",
        "فول الصويا",
        "بروتين الصويا",
    ],

    # --------------------------------------------------------
    # WHEAT / GLUTEN
    # --------------------------------------------------------
    "wheat_gluten": [
        "wheat",
        "wheat flour",
        "wheat starch",
        "wheat fibres",
        "wheat fiber",
        "whole wheat",
        "wholewheat",
        "durum",
        "durum wheat",
        "semolina",
        "bulgur",
        "boulgour",
        "couscous",
        "spelt",
        "rye",
        "barley",
        "malt",
        "barley malt",
        "gluten",
        "gluten protein",

        # French
        "ble",
        "blé",
        "blé complet",
        "farine de blé",
        "amidon de blé",
        "fibres de blé",
        "froment",
        "épeautre",
        "seigle",
        "orge",
        "malt d orge",
        "semoule",

        # German
        "weizen",
        "weizenmehl",
        "weizenstärke",
        "weizenstaerke",
        "weizenfasern",
        "vollkornweizen",
        "dinkel",
        "roggen",
        "gerste",
        "gerstenmalz",
        "gluten",

        # Spanish
        "trigo",
        "harina de trigo",
        "almidon de trigo",
        "almidón de trigo",
        "fibra de trigo",
        "trigo integral",
        "espelta",
        "centeno",
        "cebada",
        "malta de cebada",
        "gluten",

        # Portuguese
        "trigo",
        "farinha de trigo",
        "amido de trigo",
        "fibra de trigo",
        "trigo integral",
        "centeio",
        "cevada",
        "malte de cevada",
        "gluten",

        # Arabic
        "القمح",
        "دقيق القمح",
        "نشا القمح",
        "جلوتين",
        "الغلوتين",
        "شعير",
        "الشعير",
        "مالت",
    ],

    # --------------------------------------------------------
    # FISH
    # --------------------------------------------------------
    "fish": [
        "fish",
        "fish oil",
        "fish oils",
        "fish protein",
        "mackerel",
        "maquereau",
        "maquereaux",
        "salmon",
        "saumon",
        "tuna",
        "thon",
        "cod",
        "cabillaud",
        "sardine",
        "sardines",
        "anchovy",
        "anchovies",
        "anchois",
        "trout",
        "truite",
        "herring",
        "herring",
        "fisch",
        "poisson",
        "pescado",
        "peixe",

        # Arabic
        "سمك",
        "سمكة",
        "زيت السمك",
        "سمك الزيت",
        "تونة",
        "سلمون",
        "سردين",
    ],

    # --------------------------------------------------------
    # SHELLFISH
    # --------------------------------------------------------
    "shellfish": [
        "shellfish",
        "crustacean",
        "crustaceans",
        "shrimp",
        "prawn",
        "prawns",
        "crab",
        "lobster",
        "crayfish",
        "mollusc",
        "molluscs",
        "mollusk",
        "mollusks",
        "moule",
        "moules",
        "crustaces",
        "crustacés",
        "crustaceos",
        "crustáceos",
        "gamba",
        "gambas",
        "langoustine",
        "langoustines",
        "crevette",
        "crevettes",

        # Arabic
        "جمبري",
        "روبيان",
        "سلطعون",
        "كركند",
        "محار",
    ],

    # --------------------------------------------------------
    # SESAME
    # --------------------------------------------------------
    "sesame": [
        "sesame",
        "sesame seeds",
        "sesame-seeds",
        "sesam",
        "sesamo",
        "sésame",
        "graines de sesame",
        "graines de sésame",
        "semillas de sesamo",
        "semillas de sésamo",
        "sementes de sesamo",
        "sementes de sésamo",

        # Arabic
        "سمسم",
        "بذور السمسم",
    ],
}


# ============================================================
# NORMALIZATION
# ============================================================

def normalize_text(text):
    """
    Normalize text for matching while preserving non-Latin scripts.
    """
    if text is None:
        return ""

    text = str(text)

    # Unicode compatibility normalization
    text = unicodedata.normalize("NFKC", text)

    # Lowercase
    text = text.lower()

    # Normalize apostrophes/dashes
    text = text.replace("’", "'")
    text = text.replace("‘", "'")
    text = text.replace("–", "-")
    text = text.replace("—", "-")

    # Remove accents for Latin characters
    decomposed = unicodedata.normalize("NFKD", text)
    text = "".join(
        char
        for char in decomposed
        if not unicodedata.combining(char)
    )

    # œ -> oe
    text = text.replace("œ", "oe")
    text = text.replace("æ", "ae")

    # Replace punctuation with spaces
    text = re.sub(r"[^\w\s\-]", " ", text, flags=re.UNICODE)

    # Normalize hyphens
    text = re.sub(r"[-]+", " ", text)

    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text


# ============================================================
# WORD / PHRASE MATCHING
# ============================================================

def phrase_in_text(phrase, text):
    """
    Safe phrase matching.

    Prevents short terms from matching inside unrelated words.
    """
    phrase = normalize_text(phrase)
    text = normalize_text(text)

    if not phrase or not text:
        return False

    pattern = r"(?<!\w)" + re.escape(phrase) + r"(?!\w)"
    return re.search(pattern, text, flags=re.UNICODE) is not None


# ============================================================
# SPECIAL EXCLUSIONS
# ============================================================

PLANT_MILK_PATTERNS = [
    # English
    r"\balmond milk\b",
    r"\bsoy milk\b",
    r"\bsoya milk\b",
    r"\bcoconut milk\b",
    r"\boat milk\b",
    r"\bhazelnut milk\b",

    # French
    r"\blait d amande\b",
    r"\blait d amandes\b",
    r"\blait de soja\b",
    r"\blait de coco\b",
    r"\blait d avoine\b",
    r"\blait de noisette\b",

    # Spanish
    r"\bleche de almendra\b",
    r"\bleche de almendras\b",
    r"\bleche de soja\b",
    r"\bleche de coco\b",
    r"\bleche de avena\b",
    r"\bleche de avellana\b",

    # Portuguese
    r"\bleite de amendoa\b",
    r"\bleite de amendoas\b",
    r"\bleite de soja\b",
    r"\bleite de coco\b",
    r"\bleite de aveia\b",
    r"\bleite de avela\b",

    # German
    r"\bmandelmilch\b",
    r"\bsojamilch\b",
    r"\bkokosmilch\b",
    r"\bhafermilch\b",
    r"\bhaselnussmilch\b",
]


COCOA_BUTTER_PATTERNS = [
    r"\bbeurre de cacao\b",
    r"\bcocoa butter\b",
    r"\bcacao butter\b",
    r"\bkakaobutter\b",
    r"\bcacaoboter\b",
]


COCONUT_PATTERNS = [
    r"\bcoconut\b",
    r"\bcoco\b",
    r"\bcocoanut\b",
    r"\bnoix de coco\b",
    r"\bnoix de coco sechee\b",
    r"\bnoix de coco séchée\b",
    r"\bkokus\b",
    r"\bkokos\b",
    r"\bkokosnuss\b",
    r"\bkokosnüsse\b",
    r"\bcoco rallado\b",
]


GLUTEN_FREE_PATTERNS = [
    r"\bgluten free\b",
    r"\bglutenfrei\b",
    r"\bsans gluten\b",
    r"\bsin gluten\b",
    r"\bsem gluten\b",
    r"\bsem glutén\b",
    r"\bsem glúten\b",
    r"\bglutenvrij\b",
    r"\bglutenfri\b",
    r"\bglutenfritt\b",
    r"\bbez glutenu\b",
    r"\bgluten y lactosa libre\b",
]


def matches_any_pattern(text, patterns):
    normalized = normalize_text(text)

    for pattern in patterns:
        if re.search(pattern, normalized, flags=re.IGNORECASE | re.UNICODE):
            return True

    return False


# ============================================================
# NEGATION HANDLING
# ============================================================

NEGATION_PATTERNS = {
    "peanut": [
        r"\bno peanuts?\b",
        r"\bwithout peanuts?\b",
        r"\bkeine erdnüsse\b",
        r"\bkeine erdnuesse\b",
        r"\bkeine erdnuss\b",
        r"\bsans arachides?\b",
        r"\bsin cacahuetes?\b",
        r"\bsin cacahuetes?\b",
        r"\bsem amendoim\b",
        r"\bبدون فول سوداني\b",
        r"\bلا يحتوي على فول سوداني\b",
    ],

    "milk": [
        r"\bno milk\b",
        r"\bwithout milk\b",
        r"\bohne milch\b",
        r"\bsans lait\b",
        r"\bsin leche\b",
        r"\bsem leite\b",
    ],

    "egg": [
        r"\bno eggs?\b",
        r"\bwithout eggs?\b",
        r"\bohne ei\b",
        r"\bohne eier\b",
        r"\bsans oeuf\b",
        r"\bsans oeufs\b",
        r"\bsin huevo\b",
        r"\bsin huevos\b",
    ],
}


def is_negated(allergen, text):
    """
    Detect common explicit negation phrases.

    This is intentionally conservative.
    """
    patterns = NEGATION_PATTERNS.get(allergen, [])

    if not patterns:
        return False

    normalized = normalize_text(text)

    return any(
        re.search(pattern, normalized, flags=re.IGNORECASE | re.UNICODE)
        for pattern in patterns
    )


# ============================================================
# TRACE / MAY-CONTAIN DETECTION
# ============================================================

TRACE_REGEXES = [

    # English
    r"\bmay contain\b",
    r"\bmay contain traces\b",
    r"\btraces of\b",
    r"\btraces may be present\b",
    r"\bmade in a facility\b",
    r"\bmade in a factory\b",
    r"\bmanufactured in a facility\b",
    r"\bmanufactured in a factory\b",
    r"\bprocessed in a facility\b",
    r"\bproduced in a facility\b",

    # French
    r"\bpeut contenir\b",
    r"\bpeut contenir des traces\b",
    r"\btraces de\b",
    r"\btraces possibles\b",
    r"\btraces eventuelles\b",
    r"\btraces éventuelles\b",
    r"\bfabrique dans un atelier\b",
    r"\bfabriqué dans un atelier\b",
    r"\bfabrique dans une usine\b",
    r"\bfabriqué dans une usine\b",
    r"\bproduit dans un atelier\b",

    # German
    r"\bkann enthalten\b",
    r"\bkann spuren enthalten\b",
    r"\bkann spuren von\b",
    r"\bkann(?:\s+\w+){0,8}\s+enthalten\b",
    r"\bspuren von\b",
    r"\bhergestellt in einem betrieb\b",
    r"\bhergestellt in einer anlage\b",

    # Spanish
    r"\bpuede contener\b",
    r"\bpuede contener trazas\b",
    r"\btrazas de\b",
    r"\btrazas posibles\b",
    r"\belaborado en una fabrica\b",
    r"\belaborado en una fábrica\b",
    r"\bfabricado en una planta\b",

    # Portuguese
    r"\bpode conter\b",
    r"\bpode conter vestigios\b",
    r"\bvestigios de\b",
    r"\btracos de\b",
    r"\btraços de\b",
    r"\bfabricado numa instalacao\b",
    r"\bfabricado numa instalação\b",

    # Dutch
    r"\bkan bevatten\b",
    r"\bkan sporen bevatten\b",
    r"\bsporen van\b",

    # Norwegian / Danish / Swedish
    r"\bkan inneholde\b",
    r"\bkan inneholde spor av\b",
    r"\bkan indeholde\b",
    r"\bkan indeholde spor af\b",
    r"\bkan innehalla\b",
    r"\bkan innehålla\b",
    r"\bkan innehålla spår av\b",

    # Arabic
    r"\bقد يحتوي\b",
    r"\bقد يحتوي على\b",
    r"\bيمكن أن يحتوي\b",
    r"\bيمكن ان يحتوي\b",
    r"\bيمكن أن يحتوي على\b",
    r"\bيمكن ان يحتوي على\b",
    r"\bقد يحتوي على آثار\b",
    r"\bقد يحتوي آثار\b",
]


def trace_marker_match(text):
    """
    Return the earliest trace marker match.
    """
    normalized = normalize_text(text)

    matches = []

    for pattern in TRACE_REGEXES:
        match = re.search(
            pattern,
            normalized,
            flags=re.IGNORECASE | re.UNICODE,
        )

        if match:
            matches.append(match)

    if not matches:
        return None

    return min(matches, key=lambda m: m.start())


def split_declared_and_trace_text(text):
    """
    Split ingredient text into:

    declared_text
    trace_text

    Everything before the first trace marker is considered declared.
    Everything after it is considered trace-related.
    """
    if text is None or pd.isna(text):
        return "", ""

    original = str(text)

    marker = trace_marker_match(original)

    if marker is None:
        return original, ""

    normalized = normalize_text(original)

    start = marker.start()

    # Map normalized character position approximately back to original.
    # Most labels preserve one logical character after normalization.
    # We additionally search a small range around the estimated location.
    estimated_original_start = min(start, len(original))

    search_start = max(0, estimated_original_start - 20)
    search_end = min(len(original), estimated_original_start + 40)

    original_fragment = original[search_start:search_end]

    # Try to locate a recognizable marker inside original fragment.
    marker_position = None

    for phrase in [
        "may contain",
        "peut contenir",
        "kann",
        "puede contener",
        "pode conter",
        "kan bevatten",
        "kan inneholde",
        "kan indeholde",
        "kan innehålla",
        "قد يحتوي",
        "يمكن أن يحتوي",
    ]:
        pos = original_fragment.lower().find(phrase.lower())

        if pos >= 0:
            marker_position = search_start + pos
            break

    if marker_position is None:
        marker_position = estimated_original_start

    declared = original[:marker_position].strip()
    trace = original[marker_position:].strip()

    return declared, trace


# ============================================================
# DICTIONARY LOADING
# ============================================================

def load_dictionary():
    """
    Load the project's allergen dictionary and combine it with
    the built-in project synonyms.
    """
    result = {
        allergen: set()
        for allergen in ALLERGENS
    }

    if DICTIONARY_FILE.exists():
        with open(DICTIONARY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        for allergen, values in data.items():

            if allergen not in result:
                continue

            if isinstance(values, list):
                for value in values:
                    result[allergen].add(normalize_text(value))

    # Add built-in synonyms
    for allergen, values in EXTRA_SYNONYMS.items():
        if allergen not in result:
            continue

        for value in values:
            result[allergen].add(normalize_text(value))

    # Remove empty values
    for allergen in result:
        result[allergen] = {
            value
            for value in result[allergen]
            if value
        }

    return result


# ============================================================
# OPEN FOOD FACTS TAG PARSING
# ============================================================

def parse_tag_value(value):
    """
    Convert OF tags into a list of normalized tag strings.

    Handles:
      ['en:milk', 'fr:soja']
      "['en:milk', 'fr:soja']"
      "en:milk, fr:soja"
      "en:milk"
    """
    if value is None or pd.isna(value):
        return []

    if isinstance(value, list):
        raw_values = value

    else:
        text = str(value).strip()

        if not text:
            return []

        # Try Python-list syntax
        try:
            parsed = ast.literal_eval(text)

            if isinstance(parsed, list):
                raw_values = parsed
            else:
                raw_values = [text]

        except Exception:
            # Fallback split
            raw_values = re.split(r"[,;|]", text)

    result = []

    for item in raw_values:

        if item is None:
            continue

        item = str(item).strip()

        if not item:
            continue

        # Remove language prefix, e.g. en:milk
        if ":" in item:
            item = item.split(":", 1)[1]

        item = normalize_text(item)

        if item:
            result.append(item)

    return result


def tags_to_allergens(value):
    """
    Convert Open Food Facts allergen tags to project allergen IDs.
    """
    tags = parse_tag_value(value)

    allergens = set()

    for tag in tags:

        if tag in TAG_TO_ALLERGEN:
            allergens.add(TAG_TO_ALLERGEN[tag])
            continue

        # Flexible matching
        tag_without_plural = tag.rstrip("s")

        if tag_without_plural in TAG_TO_ALLERGEN:
            allergens.add(TAG_TO_ALLERGEN[tag_without_plural])

    return allergens


# ============================================================
# ALLERGEN DETECTION
# ============================================================

def detect_allergens(text, dictionary):
    """
    Detect allergens in ingredient text.

    Returns:
        set(allergen_ids)
    """
    detected = set()

    if not text:
        return detected

    normalized = normalize_text(text)

    # --------------------------------------------------------
    # GLOBAL GLUTEN-FREE SUPPRESSION
    # --------------------------------------------------------

    gluten_free = matches_any_pattern(
        normalized,
        GLUTEN_FREE_PATTERNS,
    )

    # --------------------------------------------------------
    # CHECK EACH ALLERGEN
    # --------------------------------------------------------

    for allergen, synonyms in dictionary.items():

        # Explicit negation
        if is_negated(allergen, normalized):
            continue

        for synonym in synonyms:

            synonym = normalize_text(synonym)

            if not synonym:
                continue

            if not phrase_in_text(synonym, normalized):
                continue

            # ------------------------------------------------
            # MILK EXCLUSIONS
            # ------------------------------------------------

            if allergen == "milk":

                if matches_any_pattern(
                    normalized,
                    PLANT_MILK_PATTERNS,
                ):
                    # Plant milk itself does NOT mean dairy milk.
                    #
                    # Example:
                    # "almond milk"
                    #
                    # Tree nut detection happens separately.
                    if synonym in {
                        "milk",
                        "lait",
                        "leche",
                        "leite",
                        "milch",
                    }:
                        continue

                if matches_any_pattern(
                    normalized,
                    COCOA_BUTTER_PATTERNS,
                ):
                    # "cocoa butter" is not dairy butter.
                    #
                    # Only suppress generic butter/cocoa-butter
                    # matches. Actual milk ingredients elsewhere
                    # should still be detected.
                    if synonym in {
                        "butter",
                        "beurre",
                        "mantequilla",
                        "manteiga",
                        "kakaobutter",
                        "cacaoboter",
                    }:
                        continue

            # ------------------------------------------------
            # TREE-NUT EXCLUSIONS
            # ------------------------------------------------

            if allergen == "tree_nut":

                # Coconut is not automatically treated as a
                # tree nut in this project.
                if matches_any_pattern(
                    normalized,
                    COCONUT_PATTERNS,
                ):
                    coconut_context = any(
                        phrase_in_text(
                            coconut_phrase,
                            normalized,
                        )
                        for coconut_phrase in [
                            "coconut",
                            "coco",
                            "noix de coco",
                            "kokos",
                            "kokosnuss",
                        ]
                    )

                    # If the only nut-like match is generic
                    # "noix"/"nuts", suppress it.
                    if coconut_context and synonym in {
                        "nuts",
                        "nut",
                        "noix",
                        "tree nut",
                        "tree nuts",
                    }:
                        continue

            # ------------------------------------------------
            # WHEAT / GLUTEN EXCLUSION
            # ------------------------------------------------

            if allergen == "wheat_gluten" and gluten_free:

                # Do not trigger from the word "gluten" when
                # the product explicitly says gluten-free.
                if synonym in {
                    "gluten",
                    "gluten protein",
                }:
                    continue

            detected.add(allergen)
            break

    return detected


# ============================================================
# PRODUCT ANALYSIS
# ============================================================

def analyze_product(row, dictionary):
    """
    Analyze one product.

    Risk logic:

      Declared allergen -> AVOID
      Trace-only allergen -> CAUTION
      No detected allergen -> SAFE
    """

    ingredient_text = row.get("ingredients_text", "")

    if ingredient_text is None or pd.isna(ingredient_text):
        ingredient_text = ""

    ingredient_text = str(ingredient_text)

    declared_text, trace_text = split_declared_and_trace_text(
        ingredient_text
    )

    declared_detected = detect_allergens(
        declared_text,
        dictionary,
    )

    trace_detected = detect_allergens(
        trace_text,
        dictionary,
    )

    # --------------------------------------------------------
    # Remove trace allergens from declared set if they only
    # occur in trace section.
    # --------------------------------------------------------

    if trace_text:
        declared_detected = set(declared_detected)

    # --------------------------------------------------------
    # Risk
    # --------------------------------------------------------

    if declared_detected:
        risk = "AVOID"

    elif trace_detected:
        risk = "CAUTION"

    else:
        risk = "SAFE"

    # --------------------------------------------------------
    # Metadata
    # --------------------------------------------------------

    metadata_declared = tags_to_allergens(
        row.get("allergens_tags", "")
    )

    metadata_trace = tags_to_allergens(
        row.get("traces_tags", "")
    )

    return {
        "declared_detected": declared_detected,
        "trace_detected": trace_detected,
        "metadata_declared": metadata_declared,
        "metadata_trace": metadata_trace,
        "risk": risk,
        "declared_text": declared_text,
        "trace_text": trace_text,
    }


# ============================================================
# METRIC HELPERS
# ============================================================

def exact_set_agreement(predictions, actuals):
    """
    Percentage of products where the complete predicted allergen
    set exactly equals the metadata allergen set.

    IMPORTANT:
    Denominator is ALWAYS total products.
    """
    if not predictions:
        return 0.0

    matches = sum(
        1
        for predicted, actual in zip(predictions, actuals)
        if predicted == actual
    )

    return (matches / len(predictions)) * 100


def multilabel_metrics(predictions, actuals):
    """
    Label-level precision / recall / F1.

    Micro averaging across all allergen labels.
    """

    tp = 0
    fp = 0
    fn = 0

    for predicted, actual in zip(predictions, actuals):

        predicted = set(predicted)
        actual = set(actual)

        tp += len(predicted & actual)
        fp += len(predicted - actual)
        fn += len(actual - predicted)

    precision = (
        tp / (tp + fp)
        if (tp + fp)
        else 0.0
    )

    recall = (
        tp / (tp + fn)
        if (tp + fn)
        else 0.0
    )

    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall)
        else 0.0
    )

    return {
        "precision": precision * 100,
        "recall": recall * 100,
        "f1": f1 * 100,
        "tp": tp,
        "fp": fp,
        "fn": fn,
    }


# ============================================================
# DIAGNOSTICS
# ============================================================

def set_to_string(values):
    if not values:
        return "None"

    return ", ".join(sorted(values))


def print_diagnostic(
    row,
    result,
    index,
):
    """
    Print useful diagnostics for products where text and metadata
    disagree.
    """

    metadata_declared = result["metadata_declared"]
    detected_declared = result["declared_detected"]

    metadata_trace = result["metadata_trace"]
    detected_trace = result["trace_detected"]

    declared_metadata_only = (
        metadata_declared - detected_declared
    )

    declared_text_only = (
        detected_declared - metadata_declared
    )

    trace_metadata_only = (
        metadata_trace - detected_trace
    )

    trace_text_only = (
        detected_trace - metadata_trace
    )

    mismatch = any([
        declared_metadata_only,
        declared_text_only,
        trace_metadata_only,
        trace_text_only,
    ])

    if not mismatch:
        return False

    print()
    print("=" * 75)
    print(f"DIAGNOSTIC #{index}")
    print("=" * 75)

    print(
        "Product:",
        row.get("product_name", "Unknown"),
    )

    print(
        "Code:",
        row.get("code", "Unknown"),
    )

    print(
        "Risk:",
        result["risk"],
    )

    print()
    print(
        "Metadata declared:",
        set_to_string(metadata_declared),
    )

    print(
        "Text declared:",
        set_to_string(detected_declared),
    )

    print(
        "Metadata trace:",
        set_to_string(metadata_trace),
    )

    print(
        "Text trace:",
        set_to_string(detected_trace),
    )

    if declared_metadata_only:
        print(
            "Metadata-only declared:",
            set_to_string(declared_metadata_only),
        )

    if declared_text_only:
        print(
            "Text-only declared:",
            set_to_string(declared_text_only),
        )

    if trace_metadata_only:
        print(
            "Metadata-only trace:",
            set_to_string(trace_metadata_only),
        )

    if trace_text_only:
        print(
            "Text-only trace:",
            set_to_string(trace_text_only),
        )

    print()
    print(
        "Declared text:",
        result["declared_text"][:500],
    )

    if result["trace_text"]:
        print(
            "Trace text:",
            result["trace_text"][:500],
        )

    return True


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 75)
    print("AI FOOD ALLERGEN MATCHING EVALUATION")
    print("=" * 75)
    print()

    # --------------------------------------------------------
    # Check files
    # --------------------------------------------------------

    if not PRODUCT_FILE.exists():
        raise FileNotFoundError(
            f"Dataset not found:\n{PRODUCT_FILE}"
        )

    if not DICTIONARY_FILE.exists():
        raise FileNotFoundError(
            f"Allergen dictionary not found:\n{DICTIONARY_FILE}"
        )

    # --------------------------------------------------------
    # Load
    # --------------------------------------------------------

    print("Loading dataset...")

    df = pd.read_csv(
        PRODUCT_FILE,
        low_memory=False,
    )

    print(
        f"Loaded {len(df):,} products."
    )

    dictionary = load_dictionary()

    print(
        f"Loaded allergen dictionary with "
        f"{sum(len(v) for v in dictionary.values()):,} "
        f"matching terms."
    )

    print()

    # --------------------------------------------------------
    # Analyze
    # --------------------------------------------------------

    predictions_declared = []
    metadata_declared = []

    predictions_trace = []
    metadata_trace = []

    results = []

    mismatch_count = 0
    diagnostic_limit = 50

    print("Analyzing products...")
    print()

    for index, row in df.iterrows():

        result = analyze_product(
            row,
            dictionary,
        )

        results.append(result)

        predictions_declared.append(
            result["declared_detected"]
        )

        metadata_declared.append(
            result["metadata_declared"]
        )

        predictions_trace.append(
            result["trace_detected"]
        )

        metadata_trace.append(
            result["metadata_trace"]
        )

        # Diagnostics
        if mismatch_count < diagnostic_limit:

            shown = print_diagnostic(
                row,
                result,
                mismatch_count + 1,
            )

            if shown:
                mismatch_count += 1

    # --------------------------------------------------------
    # Metrics
    # --------------------------------------------------------

    declared_agreement = exact_set_agreement(
        predictions_declared,
        metadata_declared,
    )

    trace_agreement = exact_set_agreement(
        predictions_trace,
        metadata_trace,
    )

    declared_metrics = multilabel_metrics(
        predictions_declared,
        metadata_declared,
    )

    trace_metrics = multilabel_metrics(
        predictions_trace,
        metadata_trace,
    )

    # --------------------------------------------------------
    # Risk distribution
    # --------------------------------------------------------

    risk_counts = {}

    for result in results:

        risk = result["risk"]

        risk_counts[risk] = (
            risk_counts.get(risk, 0) + 1
        )

    # --------------------------------------------------------
    # Output
    # --------------------------------------------------------

    print()
    print()
    print("=" * 75)
    print("FINAL EVALUATION")
    print("=" * 75)

    print()
    print(f"Total products: {len(df):,}")

    print()
    print("DECLARED ALLERGENS")
    print("-" * 75)

    print(
        f"Exact agreement: "
        f"{declared_agreement:.2f}%"
    )

    print(
        f"Precision: "
        f"{declared_metrics['precision']:.2f}%"
    )

    print(
        f"Recall: "
        f"{declared_metrics['recall']:.2f}%"
    )

    print(
        f"F1-score: "
        f"{declared_metrics['f1']:.2f}%"
    )

    print()
    print("TRACE ALLERGENS")
    print("-" * 75)

    print(
        f"Exact agreement: "
        f"{trace_agreement:.2f}%"
    )

    print(
        f"Precision: "
        f"{trace_metrics['precision']:.2f}%"
    )

    print(
        f"Recall: "
        f"{trace_metrics['recall']:.2f}%"
    )

    print(
        f"F1-score: "
        f"{trace_metrics['f1']:.2f}%"
    )

    print()
    print("RISK DISTRIBUTION")
    print("-" * 75)

    for risk in [
        "SAFE",
        "CAUTION",
        "AVOID",
    ]:

        count = risk_counts.get(risk, 0)

        percentage = (
            count / len(df) * 100
            if len(df)
            else 0
        )

        print(
            f"{risk:8s}: "
            f"{count:5d} "
            f"({percentage:.2f}%)"
        )

    # --------------------------------------------------------
    # Evaluation explanation
    # --------------------------------------------------------

    print()
    print("IMPORTANT EVALUATION NOTE")
    print("-" * 75)

    print(
        "Open Food Facts allergen/traces metadata is treated "
        "as evaluation metadata, not absolute ground truth."
    )

    print(
        "Text-only detections may represent genuine allergens "
        "that are missing from product metadata."
    )

    print(
        "Metadata-only detections may reflect product metadata "
        "that is not explicitly visible in the ingredient text."
    )

    print()
    print(
        f"Diagnostic mismatches displayed: "
        f"{mismatch_count} "
        f"(maximum {diagnostic_limit})"
    )

    print()
    print("=" * 75)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 75)
    print()


if __name__ == "__main__":
    main()