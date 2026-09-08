import React, { useState } from 'react';
import { Eye, FileCode, CheckCircle, Copy, Search, Sparkles, Code2, Check } from 'lucide-react';

export default function IngredientInspector({ result }) {
  const [activeTab, setActiveTab] = useState('ingredients'); // 'ingredients' | 'sections' | 'ocr'
  const [copied, setCopied] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');

  if (!result) return null;

  const { ocr, ingredients, allergens } = result;

  const rawOcrText = ocr?.raw_text || ingredients?.ingredient_text || '';
  const confidence = ocr?.confidence ? (ocr.confidence * 100).toFixed(1) : '95.0';

  const declaredText = ingredients?.declared_text || ingredients?.ingredient_text || '';
  const traceText = ingredients?.trace_text || '';

  const handleCopyText = () => {
    navigator.clipboard.writeText(rawOcrText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Helper to render text with highlighted allergen keywords
  const renderHighlightedText = (text) => {
    if (!text) return <span className="text-slate-500 italic">No text extracted.</span>;

    const allTriggerWords = [
      ...(allergens?.declared || []),
      ...(allergens?.trace || []),
      'milk', 'dairy', 'butter', 'cream', 'cheese', 'whey', 'casein', 'lactose',
      'egg', 'eggs', 'albumin', 'mayonnaise',
      'peanut', 'peanuts', 'groundnut',
      'almond', 'walnut', 'cashew', 'pecan', 'hazelnut', 'pistachio', 'tree nut',
      'soy', 'soya', 'soybean', 'tofu', 'lecithin',
      'wheat', 'gluten', 'flour', 'barley', 'rye', 'spelt',
      'fish', 'cod', 'salmon', 'tuna',
      'shellfish', 'shrimp', 'crab', 'lobster', 'prawn',
      'sesame', 'tahini'
    ];

    const words = text.split(/(\s+|[,;.:()])/);

    return (
      <p className="leading-relaxed text-xs sm:text-sm font-sans">
        {words.map((chunk, i) => {
          const cleanChunk = chunk.toLowerCase().replace(/[^a-z0-9]/g, '');
          const isTrigger = cleanChunk.length > 2 && allTriggerWords.some((w) => cleanChunk.includes(w.toLowerCase()));
          const isMatchSearch = searchTerm.trim() && cleanChunk.includes(searchTerm.toLowerCase().trim());

          if (isTrigger || isMatchSearch) {
            return (
              <mark
                key={i}
                className="px-1 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/40 font-bold mx-0.5"
              >
                {chunk}
              </mark>
            );
          }
          return <span key={i}>{chunk}</span>;
        })}
      </p>
    );
  };

  return (
    <div className="glass-card p-5 sm:p-6 space-y-4">
      {/* Header & Tabs */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-4">
        <div>
          <h3 className="text-base sm:text-lg font-bold text-white tracking-tight flex items-center gap-2">
            <Eye className="w-5 h-5 text-blue-400" />
            3. Ingredient & OCR Inspector Card
          </h3>
          <p className="text-xs text-slate-400 mt-1">
            Deep-dive view of normalized ingredients, precautionary statements, and raw OCR output.
          </p>
        </div>

        {/* Tab Controls */}
        <div className="flex items-center bg-slate-950 p-1 rounded-xl border border-slate-800 self-start sm:self-auto">
          <button
            onClick={() => setActiveTab('ingredients')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all cursor-pointer ${
              activeTab === 'ingredients'
                ? 'bg-blue-600 text-white shadow-md shadow-blue-500/20'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            Ingredients View
          </button>
          <button
            onClick={() => setActiveTab('sections')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all cursor-pointer ${
              activeTab === 'sections'
                ? 'bg-blue-600 text-white shadow-md shadow-blue-500/20'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            Declared vs Trace
          </button>
          <button
            onClick={() => setActiveTab('ocr')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all cursor-pointer ${
              activeTab === 'ocr'
                ? 'bg-blue-600 text-white shadow-md shadow-blue-500/20'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            Raw OCR Text
          </button>
        </div>
      </div>

      {/* Filter / Search inside Inspector */}
      <div className="flex items-center justify-between gap-3 text-xs">
        <div className="relative flex-1">
          <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search specific term inside ingredients..."
            className="w-full pl-9 pr-3 py-1.5 bg-slate-950/80 border border-slate-800 rounded-lg text-xs text-white placeholder:text-slate-500 focus:outline-none focus:border-blue-500"
          />
        </div>

        {/* OCR Confidence Score Meter */}
        <div className="flex items-center gap-2 bg-slate-950/60 px-3 py-1.5 rounded-lg border border-slate-800 shrink-0">
          <span className="text-slate-400 font-medium">OCR Confidence:</span>
          <span className="font-mono font-bold text-blue-400">{confidence}%</span>
        </div>
      </div>

      {/* TAB 1: NORMALIZED INGREDIENTS */}
      {activeTab === 'ingredients' && (
        <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 text-slate-200 min-h-[120px]">
          {renderHighlightedText(ingredients?.ingredient_text || rawOcrText)}
        </div>
      )}

      {/* TAB 2: DECLARED VS TRACE SECTIONS */}
      {activeTab === 'sections' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 space-y-2">
            <h4 className="text-xs font-bold uppercase tracking-wider text-blue-400">
              Declared Ingredients Section
            </h4>
            <div className="text-xs text-slate-300">
              {renderHighlightedText(declaredText)}
            </div>
          </div>
          <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 space-y-2">
            <h4 className="text-xs font-bold uppercase tracking-wider text-amber-400">
              Precautionary / Trace Section
            </h4>
            <div className="text-xs text-slate-300">
              {renderHighlightedText(traceText || 'No precautionary statement detected.')}
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: RAW OCR DRAWER */}
      {activeTab === 'ocr' && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-400 flex items-center gap-1.5 font-mono">
              <Code2 className="w-3.5 h-3.5 text-blue-400" /> Raw EasyOCR Output Stream
            </span>
            <button
              onClick={handleCopyText}
              className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1 bg-blue-950/40 px-2.5 py-1 rounded border border-blue-800/40"
            >
              {copied ? (
                <>
                  <Check className="w-3.5 h-3.5 text-emerald-400" /> Copied!
                </>
              ) : (
                <>
                  <Copy className="w-3.5 h-3.5" /> Copy Text
                </>
              )}
            </button>
          </div>
          <pre className="p-4 rounded-xl bg-slate-950 border border-slate-800 text-xs font-mono text-slate-300 overflow-x-auto whitespace-pre-wrap leading-relaxed">
            {rawOcrText || 'No raw OCR output available.'}
          </pre>
        </div>
      )}
    </div>
  );
}
