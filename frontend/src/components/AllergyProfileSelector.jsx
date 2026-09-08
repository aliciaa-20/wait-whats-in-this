import React, { useState } from 'react';
import { ShieldCheck, UserCheck, Sparkles, Check, Plus, Trash2, Filter } from 'lucide-react';
import { DEFAULT_ALLERGENS } from '../services/api';

export default function AllergyProfileSelector({ selectedAllergies, onToggleAllergy, onSelectPreset, onClearAll }) {
  const [customSearch, setCustomSearch] = useState('');

  const PRESETS = [
    { label: '🥛 Lactose Intolerant', allergies: ['milk'] },
    { label: '🥜 Nut Allergy', allergies: ['peanut', 'tree_nut'] },
    { label: '🌾 Gluten Free / Celiac', allergies: ['wheat_gluten'] },
    { label: '🦐 Shellfish & Fish', allergies: ['shellfish', 'fish'] },
    { label: '⚡ Top 9 Common Allergens', allergies: DEFAULT_ALLERGENS.map((a) => a.id) },
  ];

  const filteredAllergens = DEFAULT_ALLERGENS.filter(
    (a) =>
      a.name.toLowerCase().includes(customSearch.toLowerCase()) ||
      a.id.toLowerCase().includes(customSearch.toLowerCase()) ||
      a.keywords.some((k) => k.toLowerCase().includes(customSearch.toLowerCase()))
  );

  return (
    <div className="glass-card p-5 sm:p-6 space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <UserCheck className="w-5 h-5 text-blue-400" />
            <h2 className="text-base sm:text-lg font-bold text-white tracking-tight">
              1. Set Your Personal Allergy Profile
            </h2>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Select your personal allergy triggers. The AI matches food labels against your profile.
          </p>
        </div>

        {/* Clear All / Counter */}
        <div className="flex items-center gap-2 self-start sm:self-auto">
          <span className="px-2.5 py-1 text-xs font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20 rounded-full">
            {selectedAllergies.length} Selected
          </span>
          {selectedAllergies.length > 0 && (
            <button
              onClick={onClearAll}
              className="text-xs text-slate-400 hover:text-rose-400 flex items-center gap-1 px-2 py-1 rounded-lg hover:bg-rose-500/10 transition-colors"
            >
              <Trash2 className="w-3.5 h-3.5" /> Clear
            </button>
          )}
        </div>
      </div>

      {/* Preset Profiles */}
      <div className="space-y-2">
        <label className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
          <Sparkles className="w-3.5 h-3.5 text-blue-400" /> Quick Preset Profiles
        </label>
        <div className="flex flex-wrap gap-2">
          {PRESETS.map((preset, idx) => {
            const isPresetActive = preset.allergies.every((alg) => selectedAllergies.includes(alg));
            return (
              <button
                key={idx}
                onClick={() => onSelectPreset(preset.allergies)}
                className={`px-3 py-1.5 text-xs font-medium rounded-xl border transition-all cursor-pointer flex items-center gap-1.5 ${
                  isPresetActive
                    ? 'bg-blue-600/30 border-blue-500 text-blue-200 shadow-md shadow-blue-500/10'
                    : 'bg-slate-900/60 border-slate-700/60 text-slate-300 hover:bg-slate-800 hover:border-slate-600'
                }`}
              >
                {preset.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Search / Filter bar */}
      <div className="relative">
        <Filter className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
        <input
          type="text"
          value={customSearch}
          onChange={(e) => setCustomSearch(e.target.value)}
          placeholder="Filter allergen list or search ingredient terms (e.g., lactose, whey, almond)..."
          className="w-full pl-9 pr-3 py-2 bg-slate-950/80 border border-slate-800 rounded-xl text-xs text-white placeholder:text-slate-500 focus:outline-none focus:border-blue-500"
        />
      </div>

      {/* Grid of Allergen Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-2.5 pt-1">
        {filteredAllergens.map((allergen) => {
          const isSelected = selectedAllergies.includes(allergen.id);
          return (
            <button
              key={allergen.id}
              onClick={() => onToggleAllergy(allergen.id)}
              className={`relative p-3 rounded-xl border text-left transition-all cursor-pointer flex flex-col justify-between min-h-[76px] ${
                isSelected
                  ? 'bg-blue-950/50 border-blue-500 text-white shadow-lg shadow-blue-500/10 ring-1 ring-blue-500/50'
                  : 'bg-slate-900/40 border-slate-800 text-slate-300 hover:bg-slate-800/60 hover:border-slate-700'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-xl">{allergen.icon}</span>
                <div
                  className={`w-5 h-5 rounded-full flex items-center justify-center border transition-all ${
                    isSelected
                      ? 'bg-blue-500 border-blue-400 text-white'
                      : 'border-slate-700 bg-slate-950/50'
                  }`}
                >
                  {isSelected && <Check className="w-3 h-3 stroke-[3]" />}
                </div>
              </div>
              <div className="mt-2">
                <span className="text-xs font-semibold block leading-snug">{allergen.name}</span>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
