"""
Quick integration tests for the reusable allergen matcher.

Run:
    python scripts/test_allergen_matcher.py
"""

from scripts.allergen_matcher import (
    analyze_ingredient_text,
    load_dictionary,
)


def assert_contains(result, allergen, field="declared_allergens"):
    assert allergen in result[field], (
        f"Expected {allergen} in {field}, got {result[field]}"
    )


def main():
    dictionary = load_dictionary()

    tests = [
        (
            "wheat flour, milk powder, soy lecithin",
            {"milk", "soy", "wheat_gluten"},
            set(),
        ),
        (
            "almond milk, oats",
            {"tree_nut"},
            set(),
        ),
        (
            "wheat flour. May contain nuts and sesame.",
            {"wheat_gluten"},
            {"tree_nut", "sesame"},
        ),
        (
            "gluten free oats",
            set(),
            set(),
        ),
        (
            "cocoa butter",
            set(),
            set(),
        ),
        (
            "peanut butter",
            {"peanut"},
            set(),
        ),
        (
            "no milk, oats",
            set(),
            set(),
        ),
    ]

    for text, expected_declared, expected_trace in tests:
        result = analyze_ingredient_text(
            text,
            dictionary,
        )

        declared = set(result["declared_allergens"])
        trace = set(result["trace_allergens"])

        assert declared == expected_declared, (
            f"\nInput: {text}\n"
            f"Expected declared: {expected_declared}\n"
            f"Got: {declared}"
        )

        assert trace == expected_trace, (
            f"\nInput: {text}\n"
            f"Expected trace: {expected_trace}\n"
            f"Got: {trace}"
        )

    print("All matcher integration tests passed.")


if __name__ == "__main__":
    main()
