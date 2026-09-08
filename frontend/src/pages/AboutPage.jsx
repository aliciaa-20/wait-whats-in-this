import React, { useState, useEffect } from 'react';
import { Info, AlertTriangle, ShieldCheck, Cpu, Layers, CheckCircle2, Wifi, WifiOff } from 'lucide-react';
import { getHealth } from '../services/api';

export default function AboutPage() {
  const [healthState, setHealthState] = useState({ online: false, data: null });

  useEffect(() => {
    const fetchStatus = async () => {
      const res = await getHealth();
      setHealthState(res);
    };
    fetchStatus();
  }, []);

  const PIPELINE_STEPS = [
    {
      step: '01',
      title: 'Image Capture & Preprocessing',
      desc: 'Users photograph or upload food ingredient label images in JPG, PNG, WEBP, or BMP format.',
    },
    {
      step: '02',
      title: 'OCR Text Extraction',
      desc: 'EasyOCR engine reads raw text strings across multi-language support (English, French, German, Spanish, etc.).',
    },
    {
      step: '03',
      title: 'Ingredient Normalization',
      desc: 'Raw text is cleaned, split into declared ingredients vs precautionary statements ("May contain...", "Traces of...").',
    },
    {
      step: '04',
      title: 'Ontology Allergen Matching',
      desc: 'Extracted terms are matched against canonical allergen dictionaries (Milk, Egg, Peanut, Tree Nuts, Soy, Wheat, Fish, Shellfish, Sesame).',
    },
    {
      step: '05',
      title: 'Personalized Risk Assessment',
      desc: 'Pipeline evaluates matched ingredients against user profile to classify risk: SAFE, CAUTION, or AVOID with explainability.',
    },
  ];

  return (
    <div className="max-w-4xl mx-auto px-4 py-8 space-y-6">
      
      {/* Header Banner */}
      <div className="bg-white rounded-3xl p-6 sm:p-8 shadow-sm border border-stone-200 space-y-3">
        <div className="flex items-center gap-3">
          <div className="p-3 bg-emerald-100 text-emerald-800 rounded-2xl">
            <Info className="w-7 h-7" />
          </div>
          <div>
            <h1 className="text-xl sm:text-2xl font-extrabold text-stone-900 tracking-tight">
              About & Methodology
            </h1>
            <p className="text-xs sm:text-sm text-stone-500">
              Personalized Food Allergen Detection and Risk Classification Pipeline Architecture.
            </p>
          </div>
        </div>
      </div>

      {/* Mandatory Research Disclaimer Box */}
      <div className="bg-amber-50 border border-amber-300 rounded-3xl p-5 sm:p-6 text-amber-900 space-y-2 shadow-sm">
        <div className="flex items-center gap-2 font-extrabold text-sm text-amber-950">
          <AlertTriangle className="w-5 h-5 text-amber-700 shrink-0" />
          Mandatory Research & Educational Disclaimer
        </div>
        <p className="text-xs sm:text-sm leading-relaxed font-medium text-amber-900">
          This tool is an educational and research prototype. It is not a medical diagnostic tool and should not replace professional medical advice or official allergen labeling. Users with severe or life-threatening food allergies must always verify physical product labels independently before consumption.
        </p>
      </div>

      {/* Pipeline Overview Card */}
      <div className="bg-white rounded-3xl p-6 sm:p-8 shadow-sm border border-stone-200 space-y-6">
        <div className="flex items-center gap-2 border-b border-stone-100 pb-4">
          <Layers className="w-5 h-5 text-emerald-700" />
          <h2 className="text-base font-extrabold text-stone-900">
            System Pipeline Architecture
          </h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {PIPELINE_STEPS.map((item, idx) => (
            <div
              key={idx}
              className="p-4 rounded-2xl bg-stone-50 border border-stone-200 space-y-1.5"
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-black text-emerald-700 font-mono">
                  STEP {item.step}
                </span>
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              </div>
              <h3 className="font-extrabold text-sm text-stone-900">{item.title}</h3>
              <p className="text-xs text-stone-600 leading-relaxed">{item.desc}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Live Backend Connection Card */}
      <div className="bg-stone-900 rounded-3xl p-6 text-white shadow-xl border border-stone-800 space-y-4">
        <div className="flex items-center justify-between border-b border-stone-800 pb-3">
          <div className="flex items-center gap-2">
            <Cpu className="w-5 h-5 text-emerald-400" />
            <h3 className="font-bold text-sm text-white">Live Backend Status & Endpoint Info</h3>
          </div>
          <span
            className={`px-3 py-1 rounded-full text-xs font-bold flex items-center gap-1.5 border ${
              healthState.online
                ? 'bg-emerald-950 text-emerald-300 border-emerald-700'
                : 'bg-amber-950 text-amber-300 border-amber-700'
            }`}
          >
            {healthState.online ? <Wifi className="w-3.5 h-3.5 text-emerald-400" /> : <WifiOff className="w-3.5 h-3.5 text-amber-400" />}
            {healthState.online ? 'Online' : 'Offline'}
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
          <div className="p-3 bg-stone-950 rounded-2xl border border-stone-800">
            <span className="text-[10px] uppercase font-bold text-stone-400 block">FastAPI Server</span>
            <span className="font-mono font-bold text-emerald-400 text-xs mt-0.5 block">http://127.0.0.1:8000</span>
          </div>
          <div className="p-3 bg-stone-950 rounded-2xl border border-stone-800">
            <span className="text-[10px] uppercase font-bold text-stone-400 block">OCR Engine</span>
            <span className="font-mono font-bold text-white text-xs mt-0.5 block">{healthState.data?.ocr || 'EasyOCR'}</span>
          </div>
          <div className="p-3 bg-stone-950 rounded-2xl border border-stone-800">
            <span className="text-[10px] uppercase font-bold text-stone-400 block">Dataset Origin</span>
            <span className="font-mono font-bold text-white text-xs mt-0.5 block">Open Food Facts</span>
          </div>
        </div>
      </div>

    </div>
  );
}
