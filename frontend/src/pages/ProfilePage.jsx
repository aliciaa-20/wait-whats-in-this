import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { UserCheck, Check, Sparkles, Trash2, CheckCircle2, ArrowRight, Info } from 'lucide-react';
import { CANONICAL_ALLERGENS } from '../services/api';

export default function ProfilePage() {
  const navigate = useNavigate();

  // Captured once, before any save happens - true only for someone who
  // has never set up a profile on this device. Used to show a one-time
  // explainer rather than repeating it on every visit.
  const [isFirstVisit] = useState(
    () => localStorage.getItem('wait-whats-in-this-allergies') === null
  );

  const [selectedAllergies, setSelectedAllergies] = useState(() => {
    const saved = localStorage.getItem('wait-whats-in-this-allergies');
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch (e) {
        // fallback
      }
    }
    // Default initial selection if empty
    return ['milk', 'peanut', 'wheat_gluten'];
  });

  const handleToggle = (id) => {
    setSelectedAllergies((prev) =>
      prev.includes(id) ? prev.filter((a) => a !== id) : [...prev, id]
    );
  };

  const handleSelectAll = () => {
    setSelectedAllergies(CANONICAL_ALLERGENS.map((a) => a.id));
  };

  const handleClearAll = () => {
    setSelectedAllergies([]);
  };

  const handleSaveAndScan = () => {
    localStorage.setItem('wait-whats-in-this-allergies', JSON.stringify(selectedAllergies));
    navigate('/scan');
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-8 space-y-6">
      
      {/* Header Banner */}
      <div className="bg-gradient-to-r from-stone-900 to-stone-800 rounded-3xl p-6 sm:p-8 text-white shadow-xl space-y-3 border border-stone-700">
        <div className="flex items-center gap-3">
          <div className="p-3 bg-emerald-600/30 border border-emerald-500/40 rounded-2xl text-emerald-400">
            <UserCheck className="w-8 h-8" />
          </div>
          <div>
            <h1 className="text-xl sm:text-2xl font-extrabold tracking-tight">
              Personal Allergy Profile
            </h1>
            <p className="text-xs sm:text-sm text-stone-300">
              Select your specific allergen triggers. The AI evaluates ingredients against this profile to assess your personal risk.
            </p>
          </div>
        </div>
      </div>

      {/* First-time explainer - shown once, before a profile has ever
          been saved on this device. Explains *why* this step exists
          rather than dropping a new user straight into a checkbox grid. */}
      {isFirstVisit && (
        <div className="bg-emerald-50 border border-emerald-200 rounded-2xl p-4 flex items-start gap-3">
          <Info className="w-5 h-5 text-emerald-700 shrink-0 mt-0.5" />
          <p className="text-xs sm:text-sm text-emerald-900 leading-relaxed">
            <strong>Why we ask:</strong> we only ask this once. Every label you
            scan afterward is checked against these allergens specifically, so
            results say <em>AVOID</em> or <em>SAFE</em> for you personally, not
            just a generic list of whatever the label contains. You can change
            this anytime from Profile.
          </p>
        </div>
      )}

      {/* Preset Action Bar */}
      <div className="bg-white rounded-2xl p-4 shadow-sm border border-stone-200 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-wider text-stone-500">
            Quick Actions:
          </span>
          <button
            onClick={handleSelectAll}
            className="px-3 py-1.5 bg-stone-100 hover:bg-stone-200 text-stone-800 rounded-xl text-xs font-semibold transition-colors flex items-center gap-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2"
          >
            <Sparkles className="w-3.5 h-3.5 text-amber-600" /> Select All Common
          </button>
          <button
            onClick={handleClearAll}
            className="px-3 py-1.5 bg-stone-100 hover:bg-stone-200 text-stone-600 hover:text-rose-600 rounded-xl text-xs font-semibold transition-colors flex items-center gap-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2"
          >
            <Trash2 className="w-3.5 h-3.5" /> Clear All
          </button>
        </div>

        <span className="text-xs font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 px-3 py-1 rounded-full">
          {selectedAllergies.length} Selected Triggers
        </span>
      </div>

      {/* Interactive Allergen Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3.5">
        {CANONICAL_ALLERGENS.map((allergen) => {
          const isSelected = selectedAllergies.includes(allergen.id);
          return (
            <button
              key={allergen.id}
              onClick={() => handleToggle(allergen.id)}
              className={`p-4 rounded-2xl border text-left transition-all cursor-pointer flex flex-col justify-between space-y-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2 ${
                isSelected
                  ? 'bg-emerald-50/90 border-emerald-400 text-stone-900 shadow-md ring-2 ring-emerald-500/20'
                  : 'bg-white border-stone-200 text-stone-700 hover:border-stone-300 hover:bg-stone-50/50'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-2xl">{allergen.icon}</span>
                <div
                  className={`w-6 h-6 rounded-full flex items-center justify-center border transition-all ${
                    isSelected
                      ? 'bg-emerald-600 border-emerald-500 text-white'
                      : 'border-stone-300 bg-stone-100'
                  }`}
                >
                  {isSelected && <Check className="w-4 h-4 stroke-[3]" />}
                </div>
              </div>

              <div>
                <span className="font-bold text-sm block text-stone-900">{allergen.name}</span>
                <span className="text-[11px] text-stone-500 block leading-tight mt-0.5">
                  {allergen.description}
                </span>
              </div>
            </button>
          );
        })}
      </div>

      {/* Primary CTA Button */}
      <div className="pt-4 flex justify-end">
        <button
          onClick={handleSaveAndScan}
          className="w-full sm:w-auto px-8 py-3.5 bg-emerald-700 hover:bg-emerald-800 text-white font-extrabold text-sm rounded-2xl shadow-lg shadow-emerald-900/20 flex items-center justify-center gap-2 cursor-pointer transition-all hover:scale-[1.01] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2"
        >
          <CheckCircle2 className="w-5 h-5" /> Save Profile & Start Scanning
          <ArrowRight className="w-4 h-4 ml-1" />
        </button>
      </div>

    </div>
  );
}
