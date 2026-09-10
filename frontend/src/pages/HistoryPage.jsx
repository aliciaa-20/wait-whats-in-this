import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import {
  History,
  Download,
  Trash2,
  ChevronRight,
  Camera,
  FileText,
  ShieldCheck,
  AlertTriangle,
  XCircle,
  HelpCircle,
} from 'lucide-react';

const VERDICT_ICON = {
  SAFE: ShieldCheck,
  CAUTION: AlertTriangle,
  AVOID: XCircle,
  UNKNOWN: HelpCircle,
};

const FILTERS = ['ALL', 'SAFE', 'CAUTION', 'AVOID', 'UNKNOWN'];

export default function HistoryPage() {
  const navigate = useNavigate();
  const [history, setHistory] = useState([]);
  const [activeFilter, setActiveFilter] = useState('ALL');

  useEffect(() => {
    const saved = localStorage.getItem('wait-whats-in-this-history');
    if (saved) {
      try {
        setHistory(JSON.parse(saved));
      } catch (e) {
        setHistory([]);
      }
    }
  }, []);

  const handleOpenScan = (entry) => {
    navigate('/results', {
      state: {
        result: entry.result,
        imagePreview: entry.imagePreview,
        timestamp: entry.timestamp,
        id: entry.id,
      },
    });
  };

  const handleExportJson = () => {
    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(history, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute('href', dataStr);
    downloadAnchor.setAttribute('download', `wait-whats-in-this-history-${Date.now()}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  const handleClearHistory = () => {
    if (window.confirm('Are you sure you want to clear all scan history records?')) {
      localStorage.removeItem('wait-whats-in-this-history');
      setHistory([]);
    }
  };

  const verdictOf = (entry) =>
    entry.result?.risk?.personalized || entry.result?.risk?.general || 'UNKNOWN';

  const filteredHistory =
    activeFilter === 'ALL' ? history : history.filter((entry) => verdictOf(entry) === activeFilter);

  const stats = {
    total: history.length,
    SAFE: history.filter((e) => verdictOf(e) === 'SAFE').length,
    CAUTION: history.filter((e) => verdictOf(e) === 'CAUTION').length,
    AVOID: history.filter((e) => verdictOf(e) === 'AVOID').length,
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-8 space-y-6">
      
      {/* Header Bar */}
      <div className="bg-white rounded-3xl p-6 shadow-sm border border-stone-200 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-lg sm:text-xl font-extrabold text-stone-900 tracking-tight flex items-center gap-2">
            <History className="w-5 h-5 text-emerald-700" /> Scan History
          </h1>
          <p className="text-xs text-stone-500 mt-0.5">
            View chronologically saved label evaluations stored locally in your browser.
          </p>
        </div>

        {history.length > 0 && (
          <div className="flex items-center gap-2 self-start sm:self-auto">
            <button
              onClick={handleExportJson}
              className="px-3.5 py-2 bg-stone-100 hover:bg-stone-200 text-stone-800 text-xs font-bold rounded-2xl border border-stone-300 flex items-center gap-1.5 transition-colors cursor-pointer"
            >
              <Download className="w-3.5 h-3.5" /> Export History (JSON)
            </button>
            <button
              onClick={handleClearHistory}
              className="px-3 py-2 bg-rose-50 hover:bg-rose-100 text-rose-700 text-xs font-bold rounded-2xl border border-rose-200 flex items-center gap-1.5 transition-colors cursor-pointer"
            >
              <Trash2 className="w-3.5 h-3.5" /> Clear
            </button>
          </div>
        )}
      </div>

      {/* Summary Statistics */}
      {history.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="bg-white p-4 rounded-2xl border border-stone-200 shadow-sm">
            <span className="text-[11px] font-bold uppercase tracking-wider text-stone-500 block">Total Scans</span>
            <span className="text-2xl font-extrabold text-stone-900 block mt-0.5 font-mono tabular-nums">{stats.total}</span>
          </div>
          <div className="bg-white p-4 rounded-2xl border border-stone-200 shadow-sm">
            <span className="text-[11px] font-bold uppercase tracking-wider text-emerald-700 block">Safe</span>
            <span className="text-2xl font-extrabold text-emerald-800 block mt-0.5 font-mono tabular-nums">{stats.SAFE}</span>
          </div>
          <div className="bg-white p-4 rounded-2xl border border-stone-200 shadow-sm">
            <span className="text-[11px] font-bold uppercase tracking-wider text-amber-700 block">Caution</span>
            <span className="text-2xl font-extrabold text-amber-800 block mt-0.5 font-mono tabular-nums">{stats.CAUTION}</span>
          </div>
          <div className="bg-white p-4 rounded-2xl border border-stone-200 shadow-sm">
            <span className="text-[11px] font-bold uppercase tracking-wider text-rose-700 block">Avoid</span>
            <span className="text-2xl font-extrabold text-rose-800 block mt-0.5 font-mono tabular-nums">{stats.AVOID}</span>
          </div>
        </div>
      )}

      {/* Verdict Filter Bar */}
      {history.length > 0 && (
        <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Filter history by verdict">
          {FILTERS.map((f) => (
            <button
              key={f}
              onClick={() => setActiveFilter(f)}
              aria-pressed={activeFilter === f}
              className={`px-3.5 py-1.5 rounded-2xl text-xs font-bold border transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2 ${
                activeFilter === f
                  ? 'bg-stone-900 text-white border-stone-900'
                  : 'bg-white text-stone-600 border-stone-200 hover:border-stone-300'
              }`}
            >
              {f === 'ALL' ? 'All' : f.charAt(0) + f.slice(1).toLowerCase()}
            </button>
          ))}
        </div>
      )}

      {/* History List Container */}
      {history.length === 0 ? (
        <div className="bg-white rounded-3xl p-12 text-center border border-stone-200 space-y-3">
          <div className="w-14 h-14 mx-auto rounded-3xl bg-stone-100 text-stone-400 flex items-center justify-center">
            <History className="w-7 h-7" />
          </div>
          <h3 className="text-base font-bold text-stone-800">No History Records Found</h3>
          <p className="text-xs text-stone-500 max-w-sm mx-auto">
            You haven't scanned any food labels yet. Start scanning to keep track of product allergen safety.
          </p>
          <div className="pt-2">
            <Link
              to="/scan"
              className="inline-flex items-center gap-2 px-6 py-2.5 bg-emerald-700 hover:bg-emerald-800 text-white font-bold text-xs rounded-2xl shadow transition-colors"
            >
              <Camera className="w-4 h-4" /> Scan First Label
            </Link>
          </div>
        </div>
      ) : filteredHistory.length === 0 ? (
        <div className="bg-white rounded-3xl p-10 text-center border border-stone-200 space-y-2">
          <p className="text-sm font-bold text-stone-700">
            No scans match the "{activeFilter.charAt(0) + activeFilter.slice(1).toLowerCase()}" filter.
          </p>
          <button
            onClick={() => setActiveFilter('ALL')}
            className="text-xs font-bold text-emerald-700 hover:text-emerald-800 underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2 rounded"
          >
            Clear filter
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {filteredHistory.map((entry, idx) => {
            const verdict = entry.result?.risk?.personalized || entry.result?.risk?.general || 'UNKNOWN';
            const badgeClass =
              verdict === 'SAFE'
                ? 'badge-safe'
                : verdict === 'CAUTION'
                ? 'badge-caution'
                : verdict === 'AVOID'
                ? 'badge-avoid'
                : 'badge-unknown';
            const VerdictIcon = VERDICT_ICON[verdict] || HelpCircle;

            const declared = entry.result?.allergens?.declared_names || entry.result?.allergens?.declared || [];
            const trace = entry.result?.allergens?.trace_names || entry.result?.allergens?.trace || [];
            const allFlagged = [...declared, ...trace];

            return (
              <button
                key={entry.id || idx}
                onClick={() => handleOpenScan(entry)}
                className="w-full text-left bg-white hover:bg-stone-50/80 p-5 rounded-3xl border border-stone-200 shadow-sm transition-all cursor-pointer flex flex-col sm:flex-row sm:items-center justify-between gap-4 group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2"
              >
                <div className="flex items-start sm:items-center gap-4">
                  {entry.imagePreview ? (
                    <img
                      src={entry.imagePreview}
                      alt="Thumbnail"
                      className="w-14 h-14 rounded-2xl object-cover border border-stone-200 shrink-0"
                    />
                  ) : (
                    <div className="w-14 h-14 rounded-2xl bg-stone-100 text-stone-400 flex items-center justify-center shrink-0">
                      <FileText className="w-6 h-6" />
                    </div>
                  )}

                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-extrabold text-sm text-stone-900 truncate max-w-[200px] sm:max-w-[300px]">
                        {entry.filename || `Scan #${history.length - idx}`}
                      </span>
                      <span className="text-[10px] font-bold text-stone-400 uppercase font-mono">
                        [{entry.language || 'en'}]
                      </span>
                    </div>

                    <div className="flex flex-wrap items-center gap-1.5">
                      {allFlagged.length > 0 ? (
                        allFlagged.map((alg, i) => (
                          <span key={i} className="text-[10px] font-bold text-stone-600 bg-stone-100 px-2 py-0.5 rounded-md">
                            {alg}
                          </span>
                        ))
                      ) : (
                        <span className="text-[11px] text-emerald-700 font-medium">No allergens flagged</span>
                      )}
                    </div>

                    <span className="text-[11px] text-stone-400 block font-mono">
                      {entry.timestamp}
                    </span>
                  </div>
                </div>

                <div className="flex items-center justify-between sm:justify-end gap-3 shrink-0 pt-2 sm:pt-0 border-t sm:border-t-0 border-stone-100">
                  <span className={`px-3 py-1 rounded-xl text-xs font-extrabold border flex items-center gap-1.5 ${badgeClass}`}>
                    <VerdictIcon className="w-3.5 h-3.5" aria-hidden="true" />
                    {verdict}
                  </span>
                  <ChevronRight className="w-5 h-5 text-stone-400 group-hover:text-stone-700 transition-colors" />
                </div>
              </button>
            );
          })}
        </div>
      )}

    </div>
  );
}
