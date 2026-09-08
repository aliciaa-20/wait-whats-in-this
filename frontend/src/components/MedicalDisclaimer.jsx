import React, { useState } from 'react';
import { AlertTriangle, Info, X } from 'lucide-react';

export default function MedicalDisclaimer() {
  const [dismissed, setDismissed] = useState(false);

  if (dismissed) {
    return (
      <div className="bg-amber-950/40 border-b border-amber-800/30 px-4 py-1.5 text-xs text-amber-300 flex justify-between items-center">
        <div className="flex items-center gap-1.5">
          <Info className="w-3.5 h-3.5 text-amber-400 shrink-0" />
          <span>Decision-Support Prototype • Not a medical diagnostic tool.</span>
        </div>
        <button 
          onClick={() => setDismissed(false)}
          className="text-amber-400 hover:underline font-medium cursor-pointer"
        >
          Expand Notice
        </button>
      </div>
    );
  }

  return (
    <div className="bg-amber-950/60 border-b border-amber-500/30 px-4 py-2 text-xs text-amber-200 backdrop-blur-md">
      <div className="max-w-7xl mx-auto flex items-start justify-between gap-3">
        <div className="flex items-start gap-2.5">
          <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
          <div>
            <span className="font-semibold text-amber-300">IMPORTANT MEDICAL & SAFETY DISCLAIMER:</span>{' '}
            <span className="text-amber-200/90">
              Wait What's In This? is an AI-powered decision-support prototype intended for educational and reference purposes only. It is <strong>not a medical diagnostic tool</strong>. Users with severe or life-threatening food allergies must always verify physical product labels independently before consumption.
            </span>
          </div>
        </div>
        <button
          onClick={() => setDismissed(true)}
          className="text-amber-400 hover:text-amber-100 transition-colors p-0.5 rounded cursor-pointer shrink-0"
          title="Minimize disclaimer"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
