import React, { useState } from 'react';
import { useLocation, useNavigate, Link } from 'react-router-dom';
import {
  ShieldCheck,
  AlertTriangle,
  XCircle,
  HelpCircle,
  ChevronDown,
  ChevronUp,
  Camera,
  History,
  FileText,
  Info,
  CheckCircle2,
} from 'lucide-react';

export default function ResultsPage() {
  const location = useLocation();
  const navigate = useNavigate();

  const [isAccordionOpen, setIsAccordionOpen] = useState(false);

  // If navigated without state, redirect to /
  const stateData = location.state;
  if (!stateData || !stateData.result) {
    return (
      <div className="max-w-xl mx-auto px-4 py-16 text-center space-y-4">
        <div className="w-16 h-16 mx-auto rounded-3xl bg-amber-100 text-amber-800 flex items-center justify-center">
          <AlertTriangle className="w-8 h-8" />
        </div>
        <h2 className="text-xl font-bold text-stone-900">No Scan Result Loaded</h2>
        <p className="text-xs text-stone-600">
          Please upload or capture a food label first to view the assessment results.
        </p>
        <Link
          to="/scan"
          className="inline-block px-6 py-2.5 bg-emerald-700 hover:bg-emerald-800 text-white font-bold text-xs rounded-2xl shadow transition-colors"
        >
          Go to Label Scanner
        </Link>
      </div>
    );
  }

  const { result, imagePreview, timestamp } = stateData;
  const { risk, user_profile, allergens, ingredients, ocr, warning } = result;

  const verdict = risk?.personalized || risk?.general || 'UNKNOWN';

  // Config per verdict badge
  const VERDICT_CONFIG = {
    SAFE: {
      title: 'SAFE TO CONSUME',
      badgeClass: 'badge-safe',
      icon: <ShieldCheck className="w-8 h-8 text-emerald-700" />,
      bannerBg: 'bg-emerald-50 border-emerald-300',
    },
    CAUTION: {
      title: 'CAUTION - PRECAUTIONARY RISK',
      badgeClass: 'badge-caution',
      icon: <AlertTriangle className="w-8 h-8 text-amber-700" />,
      bannerBg: 'bg-amber-50 border-amber-300',
    },
    AVOID: {
      title: 'AVOID - ALLERGEN DETECTED',
      badgeClass: 'badge-avoid',
      icon: <XCircle className="w-8 h-8 text-rose-700 motion-safe:animate-pulse" />,
      bannerBg: 'bg-rose-50 border-rose-300',
    },
    UNKNOWN: {
      title: 'UNABLE TO ASSESS RISK',
      badgeClass: 'badge-unknown',
      icon: <HelpCircle className="w-8 h-8 text-stone-600" />,
      bannerBg: 'bg-stone-100 border-stone-300',
    },
  };

  const currentConfig = VERDICT_CONFIG[verdict] || VERDICT_CONFIG.UNKNOWN;

  // declared/trace lists use display names, but the matcher's evidence
  // objects key by allergen id (e.g. "milk", not "Milk / Dairy") - pair
  // them up by position against the id lists, not by name, and read the
  // API's actual field name (`matched_term`, singular).
  const declaredIds = allergens?.declared || [];
  const traceIds = allergens?.trace || [];
  const declaredList = allergens?.declared_names || declaredIds;
  const traceList = allergens?.trace_names || traceIds;
  const declaredMatches = allergens?.matches || [];
  const traceMatches = allergens?.trace_matches || [];

  const evidenceFor = (matches, ids, index) => {
    const id = ids[index];
    const match = matches.find((m) => m.allergen === id);
    return match?.matched_term || null;
  };

  // Backend-built, template-generated explanations (not LLM narrative) -
  // one sentence per matched allergen, traceable straight back to the
  // dictionary term that triggered it. Falls back to nothing for older
  // history entries saved before this field existed.
  const explanations = allergens?.explanations || [];
  const explanationFor = (section, allergenId) =>
    explanations.find((e) => e.section === section && e.allergen === allergenId)?.text || null;

  // No fabricated fallback: if the API didn't return a confidence
  // value, say so rather than implying a specific measured number.
  const hasConfidence = typeof ocr?.confidence === 'number';
  const confidencePct = hasConfidence ? ocr.confidence * 100 : null;
  const confidenceScore = hasConfidence ? confidencePct.toFixed(1) : null;
  const confidenceLevel =
    confidencePct === null ? 'unknown' : confidencePct < 40 ? 'low' : confidencePct < 70 ? 'medium' : 'high';
  const CONFIDENCE_BAR_COLOR = {
    low: 'bg-rose-500',
    medium: 'bg-amber-500',
    high: 'bg-emerald-500',
    unknown: 'bg-stone-300',
  }[confidenceLevel];

  // Surfaced near the verdict itself, not just in the collapsed
  // accordion - the OCR benchmark work on this project measured real,
  // meaningful accuracy degradation under poor OCR conditions, so a
  // user should be able to tell at a glance whether THIS result came
  // from a clean read or a struggling one, not just the final verdict.
  const OCR_QUALITY_CONFIG = {
    high: {
      label: 'OCR read clearly',
      icon: <CheckCircle2 className="w-3.5 h-3.5" />,
      className: 'bg-emerald-50 text-emerald-800 border-emerald-200',
    },
    medium: {
      label: 'OCR moderately confident — worth a quick check',
      icon: <Info className="w-3.5 h-3.5" />,
      className: 'bg-amber-50 text-amber-800 border-amber-200',
    },
    low: {
      label: 'OCR struggled — verify this label yourself',
      icon: <AlertTriangle className="w-3.5 h-3.5" />,
      className: 'bg-rose-50 text-rose-800 border-rose-200',
    },
    unknown: {
      label: 'OCR confidence not reported',
      icon: <HelpCircle className="w-3.5 h-3.5" />,
      className: 'bg-stone-100 text-stone-600 border-stone-200',
    },
  }[confidenceLevel];

  return (
    <div className="max-w-4xl mx-auto px-4 py-8 space-y-6">
      
      {/* 1. Compact Risk Verdict Card */}
      <div className={`rounded-3xl p-6 border ${currentConfig.bannerBg} shadow-sm space-y-4`}>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3.5">
            <div className="p-3 bg-white rounded-2xl shadow-sm border border-stone-200">
              {currentConfig.icon}
            </div>
            <div>
              <span className="text-[11px] font-bold uppercase tracking-wider text-stone-500 block">
                Allergen Risk Assessment Rationale
              </span>
              <h1 className="text-xl sm:text-2xl font-extrabold text-stone-900 tracking-tight">
                {currentConfig.title}
              </h1>
            </div>
          </div>

          <div className="flex flex-col items-start sm:items-end gap-1.5 self-start sm:self-auto">
            <span className={`px-4 py-2 rounded-2xl text-base font-extrabold border ${currentConfig.badgeClass}`}>
              {verdict}
            </span>
            <span
              className={`px-2.5 py-1 rounded-xl text-[11px] font-bold border flex items-center gap-1.5 ${OCR_QUALITY_CONFIG.className}`}
              title={hasConfidence ? `OCR confidence: ${confidenceScore}%` : undefined}
            >
              {OCR_QUALITY_CONFIG.icon}
              {OCR_QUALITY_CONFIG.label}
            </span>
          </div>
        </div>

        {/* Backend Explanation Text */}
        <div className="p-4 bg-white/90 rounded-2xl border border-stone-200 text-xs sm:text-sm text-stone-800 leading-relaxed font-medium">
          {risk?.message || 'Assessment completed based on OCR extraction and user allergy profile.'}
        </div>

        {/* Distinction between Personal & General Risk if both exist */}
        {risk?.general && risk?.personalized && risk.general !== risk.personalized && (
          <div className="flex items-center gap-4 text-xs text-stone-600 pt-1">
            <span><strong>Personal Risk:</strong> {risk.personalized}</span>
            <span>•</span>
            <span><strong>General Label Risk:</strong> {risk.general}</span>
          </div>
        )}
      </div>

      {/* Image Preview & Evidence Section */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        
        {/* Left Column: Image Preview Thumbnail */}
        {imagePreview && (
          <div className="bg-white p-4 rounded-3xl border border-stone-200 shadow-sm space-y-2">
            <span className="text-xs font-bold text-stone-500 uppercase tracking-wider block">
              Analyzed Label Image
            </span>
            <div className="rounded-2xl overflow-hidden border border-stone-200 shadow-inner">
              <img
                src={imagePreview}
                alt="Analyzed food label"
                className="w-full h-48 object-cover"
              />
            </div>
            <span className="text-[10px] text-stone-400 font-mono block text-center">
              Scanned: {timestamp}
            </span>
          </div>
        )}

        {/* Right Column: Relevant Allergens & Evidence Chips */}
        <div className={`space-y-4 ${imagePreview ? 'md:col-span-2' : 'md:col-span-3'}`}>
          
          {/* Declared Allergens Evidence */}
          <div className="bg-white p-5 rounded-3xl border border-stone-200 shadow-sm space-y-3">
            <h3 className="text-xs font-extrabold uppercase tracking-wider text-rose-800 flex items-center gap-1.5">
              <XCircle className="w-4 h-4 text-rose-600" /> Declared Ingredients Evidence
            </h3>

            {declaredList.length > 0 ? (
              <>
                <div className="flex flex-wrap gap-2">
                  {declaredList.map((alg, idx) => {
                    const matchedTerm = evidenceFor(declaredMatches, declaredIds, idx);
                    const explanation = explanationFor('declared', declaredIds[idx]);
                    return (
                      <span
                        key={idx}
                        title={explanation || undefined}
                        className="px-3 py-1.5 bg-rose-50 text-rose-900 border border-rose-200 rounded-xl text-xs font-bold flex items-center gap-1.5"
                      >
                        ⚠️ {alg} {matchedTerm && <span className="text-[11px] text-rose-600 font-normal">({matchedTerm})</span>}
                      </span>
                    );
                  })}
                </div>
                <ul className="space-y-1 pt-1">
                  {declaredIds.map((id, idx) => {
                    const explanation = explanationFor('declared', id);
                    if (!explanation) return null;
                    return (
                      <li key={idx} className="text-[11px] text-stone-500 leading-snug">
                        {declaredList[idx]}: {explanation}
                      </li>
                    );
                  })}
                </ul>
              </>
            ) : (
              <p className="text-xs text-stone-500 italic">
                No direct declared allergens detected for your profile.
              </p>
            )}
          </div>

          {/* Precautionary / Trace Allergens Evidence */}
          <div className="bg-white p-5 rounded-3xl border border-stone-200 shadow-sm space-y-3">
            <h3 className="text-xs font-extrabold uppercase tracking-wider text-amber-800 flex items-center gap-1.5">
              <AlertTriangle className="w-4 h-4 text-amber-600" /> Precautionary & Trace Warnings
            </h3>

            {traceList.length > 0 ? (
              <>
                <div className="flex flex-wrap gap-2">
                  {traceList.map((alg, idx) => {
                    const matchedTerm = evidenceFor(traceMatches, traceIds, idx);
                    const explanation = explanationFor('trace', traceIds[idx]);
                    return (
                      <span
                        key={idx}
                        title={explanation || undefined}
                        className="px-3 py-1.5 bg-amber-50 text-amber-900 border border-amber-200 rounded-xl text-xs font-bold flex items-center gap-1.5"
                      >
                        ⚡ {alg} {matchedTerm && <span className="text-[11px] text-amber-700 font-normal">({matchedTerm})</span>}
                      </span>
                    );
                  })}
                </div>
                <ul className="space-y-1 pt-1">
                  {traceIds.map((id, idx) => {
                    const explanation = explanationFor('trace', id);
                    if (!explanation) return null;
                    return (
                      <li key={idx} className="text-[11px] text-stone-500 leading-snug">
                        {traceList[idx]}: {explanation}
                      </li>
                    );
                  })}
                </ul>
              </>
            )
            ) : (
              <p className="text-xs text-stone-500 italic">
                No precautionary ("May contain / Traces of") warnings matched.
              </p>
            )}
          </div>

        </div>

      </div>

      {/* 3. Expandable "OCR & Technical Details" Accordion */}
      <div className="bg-white rounded-3xl border border-stone-200 shadow-sm overflow-hidden">
        <button
          onClick={() => setIsAccordionOpen(!isAccordionOpen)}
          className="w-full p-5 flex items-center justify-between text-left hover:bg-stone-50 transition-colors"
        >
          <div className="flex items-center gap-2">
            <FileText className="w-5 h-5 text-emerald-700" />
            <span className="font-extrabold text-sm text-stone-900">
              OCR & Technical Details
            </span>
          </div>
          {isAccordionOpen ? <ChevronUp className="w-5 h-5 text-stone-500" /> : <ChevronDown className="w-5 h-5 text-stone-500" />}
        </button>

        {isAccordionOpen && (
          <div className="p-5 border-t border-stone-100 bg-stone-50/50 space-y-4 text-xs text-stone-800">
            
            {/* Supporting OCR Confidence & Extraction Metadata */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className="p-3 bg-white rounded-2xl border border-stone-200">
                <span className="text-[11px] text-stone-500 font-bold uppercase block">
                  Supporting OCR Confidence
                </span>
                <span className="text-sm font-extrabold text-stone-900 mt-0.5 block">
                  {hasConfidence ? `${confidenceScore}%` : 'Not reported'}
                </span>
                <div
                  className="mt-1.5 h-1.5 w-full rounded-full bg-stone-200 overflow-hidden"
                  role="meter"
                  aria-label="OCR confidence"
                  aria-valuenow={hasConfidence ? Math.round(confidencePct) : undefined}
                  aria-valuemin={0}
                  aria-valuemax={100}
                >
                  <div
                    className={`h-full rounded-full ${CONFIDENCE_BAR_COLOR} transition-[width] duration-500`}
                    style={{ width: hasConfidence ? `${confidencePct}%` : '0%' }}
                  />
                </div>
              </div>
              <div className="p-3 bg-white rounded-2xl border border-stone-200">
                <span className="text-[11px] text-stone-500 font-bold uppercase block">
                  OCR Language
                </span>
                <span className="text-sm font-extrabold text-stone-900 mt-0.5 block uppercase">
                  {ocr?.language || 'EN'}
                </span>
              </div>
              <div className="p-3 bg-white rounded-2xl border border-stone-200">
                <span className="text-[11px] text-stone-500 font-bold uppercase block">
                  Extraction Status
                </span>
                <span className="text-sm font-extrabold text-stone-900 mt-0.5 block">
                  {ingredients?.extraction_status || 'FOUND'}
                </span>
                {ingredients?.reason_code && (
                  <span className="text-[10px] text-stone-500 font-mono mt-0.5 block">
                    {ingredients.reason_code}
                  </span>
                )}
              </div>
            </div>

            {/* Normalized & Raw Extracted Text */}
            <div className="space-y-2">
              <span className="font-bold text-stone-700 block">Extracted Ingredient Text:</span>
              <div className="p-4 bg-white rounded-2xl border border-stone-200 font-sans text-xs leading-relaxed text-stone-900">
                {ingredients?.ingredient_text || ocr?.raw_text || 'No text extracted.'}
              </div>
            </div>

          </div>
        )}
      </div>

      {/* Medical Warning Disclaimer */}
      {warning && (
        <div className="p-4 bg-stone-100 border border-stone-200 rounded-2xl text-[11px] text-stone-600 leading-relaxed flex items-start gap-2">
          <Info className="w-4 h-4 text-stone-500 shrink-0 mt-0.5" />
          <span>{warning}</span>
        </div>
      )}

      {/* Action Buttons */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-2">
        <Link
          to="/scan"
          className="w-full sm:w-auto px-6 py-3 bg-emerald-700 hover:bg-emerald-800 text-white font-extrabold text-xs rounded-2xl shadow flex items-center justify-center gap-2 transition-colors"
        >
          <Camera className="w-4 h-4" /> Scan Another Label
        </Link>
        <Link
          to="/history"
          className="w-full sm:w-auto px-6 py-3 bg-stone-900 hover:bg-stone-800 text-white font-extrabold text-xs rounded-2xl shadow flex items-center justify-center gap-2 transition-colors"
        >
          <History className="w-4 h-4" /> View in History
        </Link>
      </div>

    </div>
  );
}
