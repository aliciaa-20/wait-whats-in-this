import React from 'react';
import { ShieldCheck, AlertTriangle, XCircle, HelpCircle, CheckCircle2, Info, ChevronRight, Share2 } from 'lucide-react';

export default function RiskDashboard({ result }) {
  if (!result) return null;

  const { risk, user_profile, allergens, ingredients, warning } = result;
  const status = risk?.personalized || risk?.general || 'UNKNOWN';

  // Config per status
  const STATUS_CONFIG = {
    SAFE: {
      title: 'SAFE TO CONSUME',
      subtitle: 'No Selected Allergens Detected',
      badgeClass: 'status-badge-safe',
      icon: <ShieldCheck className="w-10 h-10 text-emerald-400" />,
      colorTheme: 'emerald',
      bgGradient: 'from-emerald-950/40 to-slate-900/40',
      borderColor: 'border-emerald-500/30',
    },
    CAUTION: {
      title: 'POTENTIAL RISK / CAUTION',
      subtitle: 'Precautionary or Trace Warnings Detected',
      badgeClass: 'status-badge-caution',
      icon: <AlertTriangle className="w-10 h-10 text-amber-400" />,
      colorTheme: 'amber',
      bgGradient: 'from-amber-950/40 to-slate-900/40',
      borderColor: 'border-amber-500/30',
    },
    AVOID: {
      title: 'HIGH RISK - AVOID PRODUCT',
      subtitle: 'Selected Allergen Directly Detected',
      badgeClass: 'status-badge-avoid',
      icon: <XCircle className="w-10 h-10 text-rose-400 animate-pulse" />,
      colorTheme: 'rose',
      bgGradient: 'from-rose-950/40 to-slate-900/40',
      borderColor: 'border-rose-500/40',
    },
    UNKNOWN: {
      title: 'UNABLE TO ASSESS',
      subtitle: 'Ingredients Could Not Be Extracted',
      badgeClass: 'status-badge-unknown',
      icon: <HelpCircle className="w-10 h-10 text-slate-400" />,
      colorTheme: 'slate',
      bgGradient: 'from-slate-900/60 to-slate-950/60',
      borderColor: 'border-slate-800',
    },
  };

  const currentConfig = STATUS_CONFIG[status] || STATUS_CONFIG.UNKNOWN;

  const declaredList = allergens?.declared_names || allergens?.declared || [];
  const traceList = allergens?.trace_names || allergens?.trace || [];

  return (
    <div className={`glass-card p-6 border-2 ${currentConfig.borderColor} bg-gradient-to-br ${currentConfig.bgGradient} space-y-6 shadow-2xl transition-all animate-fadeIn`}>
      
      {/* Top Header & Main Risk Status Badge */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800/80 pb-5">
        <div className="flex items-center gap-4">
          <div className={`p-3.5 rounded-2xl ${currentConfig.badgeClass} flex items-center justify-center`}>
            {currentConfig.icon}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold uppercase tracking-widest text-slate-400">
                AI Risk Classification
              </span>
            </div>
            <h2 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white mt-0.5">
              {currentConfig.title}
            </h2>
            <p className="text-xs sm:text-sm font-medium text-slate-300 mt-1">
              {currentConfig.subtitle}
            </p>
          </div>
        </div>

        {/* Big Status Badge Pill */}
        <div className="self-start md:self-auto">
          <span className={`px-5 py-2.5 rounded-2xl text-lg font-black tracking-wider uppercase border inline-block shadow-lg ${currentConfig.badgeClass}`}>
            {status}
          </span>
        </div>
      </div>

      {/* Rationale & RATIONALE CARD */}
      <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 space-y-2">
        <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-300">
          <Info className="w-4 h-4 text-blue-400 shrink-0" />
          Explainability Analysis:
        </div>
        <p className="text-sm text-slate-200 leading-relaxed pl-6">
          {risk?.message || 'Assessment calculated based on ingredient text and selected allergy profile.'}
        </p>
      </div>

      {/* Flagged Allergens Summary */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        
        {/* Declared Allergens Card */}
        <div className="p-4 rounded-xl bg-slate-900/50 border border-slate-800/80 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
              <XCircle className="w-4 h-4 text-rose-400" /> Declared Ingredients
            </span>
            <span className="text-xs text-slate-500 font-mono">
              {declaredList.length} Found
            </span>
          </div>

          {declaredList.length > 0 ? (
            <div className="flex flex-wrap gap-1.5 pt-1">
              {declaredList.map((alg, idx) => (
                <span
                  key={idx}
                  className="px-3 py-1 text-xs font-bold rounded-lg border allergen-tag-danger flex items-center gap-1"
                >
                  ⚠️ {alg}
                </span>
              ))}
            </div>
          ) : (
            <p className="text-xs text-slate-400 italic pt-1">
              No declared allergens matched.
            </p>
          )}
        </div>

        {/* Precautionary / Trace Allergens Card */}
        <div className="p-4 rounded-xl bg-slate-900/50 border border-slate-800/80 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
              <AlertTriangle className="w-4 h-4 text-amber-400" /> Precautionary Statements
            </span>
            <span className="text-xs text-slate-500 font-mono">
              {traceList.length} Traces
            </span>
          </div>

          {traceList.length > 0 ? (
            <div className="flex flex-wrap gap-1.5 pt-1">
              {traceList.map((alg, idx) => (
                <span
                  key={idx}
                  className="px-3 py-1 text-xs font-bold rounded-lg border allergen-tag-warning flex items-center gap-1"
                >
                  ⚡ {alg}
                </span>
              ))}
            </div>
          ) : (
            <p className="text-xs text-slate-400 italic pt-1">
              No precautionary trace statements found.
            </p>
          )}
        </div>

      </div>

    </div>
  );
}
