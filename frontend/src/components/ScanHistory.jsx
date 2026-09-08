import React from 'react';
import { History, Trash2, ChevronRight, Clock, ShieldAlert } from 'lucide-react';

export default function ScanHistory({ history, onSelectHistoryItem, onClearHistory }) {
  if (!history || history.length === 0) return null;

  return (
    <div className="glass-card p-5 sm:p-6 space-y-4">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <div className="flex items-center gap-2">
          <History className="w-5 h-5 text-blue-400" />
          <h3 className="text-base font-bold text-white tracking-tight">Recent Scan History</h3>
        </div>
        <button
          onClick={onClearHistory}
          className="text-xs text-slate-400 hover:text-rose-400 flex items-center gap-1"
        >
          <Trash2 className="w-3.5 h-3.5" /> Clear History
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
        {history.map((item, idx) => {
          const status = item.risk?.personalized || item.risk?.general || 'UNKNOWN';
          const badgeClass =
            status === 'SAFE'
              ? 'status-badge-safe'
              : status === 'CAUTION'
              ? 'status-badge-caution'
              : status === 'AVOID'
              ? 'status-badge-avoid'
              : 'status-badge-unknown';

          return (
            <div
              key={idx}
              onClick={() => onSelectHistoryItem(item)}
              className="p-3.5 rounded-xl bg-slate-900/60 hover:bg-slate-800/80 border border-slate-800 hover:border-slate-700 transition-all cursor-pointer flex flex-col justify-between space-y-2 group"
            >
              <div className="flex items-start justify-between gap-2">
                <span className="text-xs font-bold text-white truncate max-w-[150px]">
                  {item.filename || `Scan #${history.length - idx}`}
                </span>
                <span className={`px-2 py-0.5 rounded text-[10px] font-black uppercase border ${badgeClass}`}>
                  {status}
                </span>
              </div>

              <div className="text-[11px] text-slate-400 flex items-center gap-1 font-mono">
                <Clock className="w-3 h-3 text-slate-500" />
                {item.timestamp || 'Just now'}
              </div>

              <div className="text-xs text-blue-400 group-hover:text-blue-300 font-medium flex items-center justify-end gap-1 pt-1">
                Inspect Scan <ChevronRight className="w-3.5 h-3.5" />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
