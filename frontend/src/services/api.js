/**
 * Centralized API Client Service Layer for WAIT, WHAT'S IN THIS?
 * Sole source of truth: FastAPI Backend at http://127.0.0.1:8000
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

// Canonical Allergen Metadata Mapping
export const CANONICAL_ALLERGENS = [
  { id: 'milk', name: 'Milk / Dairy', icon: '🥛', description: 'Milk, lactose, whey, casein, butter, cream' },
  { id: 'egg', name: 'Egg', icon: '🥚', description: 'Eggs, egg whites, albumin, egg yolk, mayonnaise' },
  { id: 'peanut', name: 'Peanut', icon: '🥜', description: 'Peanuts, peanut butter, groundnuts, peanut oil' },
  { id: 'tree_nut', name: 'Tree Nuts', icon: '🌰', description: 'Almonds, walnuts, cashews, pecans, hazelnuts, pistachios' },
  { id: 'soy', name: 'Soy', icon: '🫘', description: 'Soybeans, soy lecithin, tofu, soya flour, edamame' },
  { id: 'wheat_gluten', name: 'Wheat / Gluten', icon: '🌾', description: 'Wheat, gluten, barley, rye, spelt, semolina, flour' },
  { id: 'fish', name: 'Fish', icon: '🐟', description: 'Cod, salmon, tuna, anchovy, trout, tilapia, fish oil' },
  { id: 'shellfish', name: 'Shellfish', icon: '🦐', description: 'Shrimp, crab, lobster, prawn, clams, mussels, oysters' },
  { id: 'sesame', name: 'Sesame', icon: '🥯', description: 'Sesame seeds, tahini, sesame oil, sesame flour' },
];

/**
 * Health check status (GET /health)
 */
export async function getHealth() {
  try {
    const res = await fetch(`${API_BASE_URL}/health`, {
      method: 'GET',
      headers: { 'Accept': 'application/json' },
      signal: AbortSignal.timeout(4000),
    });
    if (res.ok) {
      const data = await res.json();
      return { online: true, data };
    }
  } catch (err) {
    // Backend unreachable
  }
  return { online: false };
}

/**
 * Fetch canonical supported allergens (GET /allergens)
 */
export async function getAllergens() {
  try {
    const res = await fetch(`${API_BASE_URL}/allergens`, {
      method: 'GET',
      headers: { 'Accept': 'application/json' },
      signal: AbortSignal.timeout(4000),
    });
    if (res.ok) {
      const data = await res.json();
      if (data && data.allergens) {
        return data.allergens;
      }
    }
  } catch (err) {
    console.warn('Unable to reach backend /allergens endpoint, using canonical schema.');
  }
  return CANONICAL_ALLERGENS.map((a) => ({ id: a.id, name: a.name }));
}

/**
 * Analyze food label image (POST /analyze)
 * @param {File} file - Uploaded image file
 * @param {string|Array} allergiesCommaSeparated - Array or comma-separated string of canonical IDs
 * @param {string} languageCode - Language code ('en', 'fr', 'de', 'es', 'nl', 'it', 'pt', 'ar')
 */
export async function analyzeLabel(file, allergiesCommaSeparated = [], languageCode = 'en') {
  const formData = new FormData();
  formData.append('file', file);

  // Normalize allergies parameter format
  const allergiesValue = Array.isArray(allergiesCommaSeparated)
    ? JSON.stringify(allergiesCommaSeparated)
    : String(allergiesCommaSeparated);

  formData.append('allergies', allergiesValue);
  formData.append('language', languageCode);

  const res = await fetch(`${API_BASE_URL}/analyze`, {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Server returned error ${res.status}`);
  }

  const data = await res.json();
  return data;
}
