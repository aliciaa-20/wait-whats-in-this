import React, { useState, useRef } from 'react';
import { Upload, Camera, FileText, Image as ImageIcon, Sparkles, RefreshCw, CheckCircle2, AlertCircle } from 'lucide-react';

export default function FoodInputCenter({ onAnalyzeImage, onAnalyzeText, isAnalyzing, selectedAllergiesCount }) {
  const [activeTab, setActiveTab] = useState('image'); // 'image' | 'text' | 'camera'
  const [ocrLanguage, setOcrLanguage] = useState('en');

  // Image Upload State
  const [selectedImageFile, setSelectedImageFile] = useState(null);
  const [imagePreviewUrl, setImagePreviewUrl] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef(null);

  // Manual Text State
  const [manualText, setManualText] = useState('');

  // Sample Labels Preset
  const SAMPLE_LABELS = [
    {
      name: 'Sample Cookie Label (Milk & Wheat)',
      text: 'Ingredients: Wheat Flour, Sugar, Palm Oil, Milk Powder, Cocoa Butter, Soy Lecithin, Salt. May contain traces of peanuts and hazelnut.',
      imagePath: '/test_images/label1.jpg',
    },
    {
      name: 'Sample Snack Label (Peanut & Soy)',
      text: 'Ingredients: Roasted Peanuts, Sugar, Vegetable Oil (Soybean), Salt, Emulsifier (E322). Warning: Made in a facility that processes tree nuts and milk.',
      imagePath: null,
    },
    {
      name: 'Sample Dairy Free Oat Milk Label',
      text: 'Ingredients: Water, Whole Grain Oats, Sunflower Oil, Dipotassium Phosphate, Calcium Carbonate, Sea Salt. Contains: Oats. Free from dairy, soy, nuts.',
      imagePath: null,
    },
  ];

  // Drag & Drop Handlers
  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelected(e.dataTransfer.files[0]);
    }
  };

  const handleFileSelected = (file) => {
    if (!file.type.startsWith('image/')) {
      alert('Please upload a valid image file (JPG, PNG, WEBP, BMP).');
      return;
    }
    setSelectedImageFile(file);
    const url = URL.createObjectURL(file);
    setImagePreviewUrl(url);
  };

  const handleSelectSample = (sample) => {
    if (sample.imagePath) {
      // Fetch sample image file
      fetch(sample.imagePath)
        .then((res) => res.blob())
        .then((blob) => {
          const file = new File([blob], 'sample_label.jpg', { type: 'image/jpeg' });
          handleFileSelected(file);
          setActiveTab('image');
        })
        .catch(() => {
          // Fallback to text if file fetch fails
          setManualText(sample.text);
          setActiveTab('text');
        });
    } else {
      setManualText(sample.text);
      setActiveTab('text');
    }
  };

  const handleTriggerImageAnalysis = () => {
    if (!selectedImageFile) return;
    onAnalyzeImage(selectedImageFile, ocrLanguage);
  };

  const handleTriggerTextAnalysis = () => {
    if (!manualText.trim()) return;
    onAnalyzeText(manualText);
  };

  const LANGUAGES = [
    { code: 'en', label: '🇬🇧 English' },
    { code: 'fr', label: '🇫🇷 French' },
    { code: 'de', label: '🇩🇪 German' },
    { code: 'es', label: '🇪🇸 Spanish' },
    { code: 'nl', label: '🇳🇱 Dutch' },
    { code: 'it', label: '🇮🇹 Italian' },
    { code: 'pt', label: '🇵🇹 Portuguese' },
  ];

  return (
    <div className="glass-card p-5 sm:p-6 space-y-4">
      {/* Title & Tabs */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-4">
        <div>
          <h2 className="text-base sm:text-lg font-bold text-white tracking-tight flex items-center gap-2">
            <Upload className="w-5 h-5 text-blue-400" />
            2. Input Food Information
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Scan a food label image or type/paste ingredients for instant AI risk assessment.
          </p>
        </div>

        {/* Controls: Language & Mode Selector Tabs */}
        <div className="flex flex-wrap items-center gap-2 self-start sm:self-auto">
          {/* OCR Language Selector */}
          <div className="flex items-center gap-1 bg-slate-950 px-2 py-1 rounded-xl border border-slate-800 text-xs">
            <span className="text-slate-400 font-semibold text-[11px]">OCR Lang:</span>
            <select
              value={ocrLanguage}
              onChange={(e) => setOcrLanguage(e.target.value)}
              className="bg-transparent text-white font-medium focus:outline-none cursor-pointer text-xs"
            >
              {LANGUAGES.map((lang) => (
                <option key={lang.code} value={lang.code} className="bg-slate-900 text-white">
                  {lang.label}
                </option>
              ))}
            </select>
          </div>

          {/* Mode Selector Tabs */}
          <div className="flex items-center bg-slate-950 p-1 rounded-xl border border-slate-800">
            <button
              onClick={() => setActiveTab('image')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all cursor-pointer ${
                activeTab === 'image'
                  ? 'bg-blue-600 text-white shadow-md shadow-blue-500/20'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              <ImageIcon className="w-3.5 h-3.5" /> Image Label Scan
            </button>
            <button
              onClick={() => setActiveTab('text')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all cursor-pointer ${
                activeTab === 'text'
                  ? 'bg-blue-600 text-white shadow-md shadow-blue-500/20'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              <FileText className="w-3.5 h-3.5" /> Manual Text Input
            </button>
          </div>
        </div>
      </div>

      {/* Preset Sample Quick Selectors */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1 text-xs">
        <span className="text-slate-400 font-semibold flex items-center gap-1 shrink-0">
          <Sparkles className="w-3.5 h-3.5 text-blue-400" /> Test Presets:
        </span>
        {SAMPLE_LABELS.map((sample, idx) => (
          <button
            key={idx}
            onClick={() => handleSelectSample(sample)}
            className="px-2.5 py-1 bg-slate-900/80 hover:bg-slate-800 text-slate-300 hover:text-white border border-slate-800 rounded-lg shrink-0 transition-colors cursor-pointer"
          >
            {sample.name}
          </button>
        ))}
      </div>

      {/* TAB 1: IMAGE DROPZONE / CAMERA */}
      {activeTab === 'image' && (
        <div className="space-y-4">
          <div
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`relative border-2 border-dashed rounded-2xl p-6 text-center cursor-pointer transition-all ${
              dragActive
                ? 'border-blue-500 bg-blue-950/30 scale-[1.01]'
                : selectedImageFile
                ? 'border-emerald-500/50 bg-emerald-950/10'
                : 'border-slate-800 bg-slate-950/50 hover:border-slate-700 hover:bg-slate-900/40'
            }`}
          >
            <input
              type="file"
              ref={fileInputRef}
              onChange={(e) => e.target.files?.[0] && handleFileSelected(e.target.files[0])}
              accept="image/jpeg,image/png,image/webp,image/bmp"
              className="hidden"
            />

            {imagePreviewUrl ? (
              <div className="relative max-w-xs mx-auto overflow-hidden rounded-xl border border-slate-700 shadow-xl group">
                <img
                  src={imagePreviewUrl}
                  alt="Food Label Preview"
                  className="w-full h-48 object-cover"
                />
                {isAnalyzing && (
                  <div className="absolute inset-0 bg-black/60 backdrop-blur-xs flex flex-col items-center justify-center">
                    <div className="scanner-line"></div>
                    <RefreshCw className="w-8 h-8 text-blue-400 animate-spin mb-2" />
                    <span className="text-xs font-bold text-white tracking-wider uppercase">
                      Running OCR & Allergen Matcher...
                    </span>
                  </div>
                )}
                <div className="absolute bottom-2 right-2 bg-slate-950/80 px-2 py-1 rounded text-[10px] text-slate-300 font-mono">
                  {selectedImageFile?.name}
                </div>
              </div>
            ) : (
              <div className="space-y-3 py-4">
                <div className="w-14 h-14 mx-auto rounded-2xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-blue-400 shadow-lg shadow-blue-500/10">
                  <Camera className="w-7 h-7" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-white">
                    Drag and drop your food label image here
                  </p>
                  <p className="text-xs text-slate-400 mt-1">
                    Or click to browse from device / camera capture (JPG, PNG, WEBP)
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* Action Trigger Button */}
          {selectedImageFile && (
            <div className="flex items-center justify-between gap-3 pt-2">
              <button
                onClick={() => {
                  setSelectedImageFile(null);
                  setImagePreviewUrl(null);
                }}
                className="px-3 py-2 text-xs font-semibold text-slate-400 hover:text-slate-200"
              >
                Remove Image
              </button>
              <button
                onClick={handleTriggerImageAnalysis}
                disabled={isAnalyzing}
                className="flex-1 sm:flex-initial px-6 py-3 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white rounded-xl font-bold text-sm shadow-xl shadow-blue-600/30 flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50 transition-all"
              >
                {isAnalyzing ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" /> Analyzing Label...
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4 text-blue-200" /> Analyze Label with AI
                  </>
                )}
              </button>
            </div>
          )}
        </div>
      )}

      {/* TAB 2: MANUAL INGREDIENT TEXT INPUT */}
      {activeTab === 'text' && (
        <div className="space-y-3">
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1">
              Paste or Type Raw Ingredient List
            </label>
            <textarea
              rows={4}
              value={manualText}
              onChange={(e) => setManualText(e.target.value)}
              placeholder="e.g. Ingredients: Wheat flour, sugar, milk powder, vegetable oil, salt. May contain traces of peanuts."
              className="w-full p-3.5 bg-slate-950/80 border border-slate-800 rounded-xl text-xs text-white placeholder:text-slate-500 focus:outline-none focus:border-blue-500 leading-relaxed"
            />
          </div>

          <div className="flex items-center justify-between gap-3 pt-1">
            <button
              onClick={() => setManualText('')}
              className="text-xs text-slate-400 hover:text-slate-200"
            >
              Clear Text
            </button>
            <button
              onClick={handleTriggerTextAnalysis}
              disabled={isAnalyzing || !manualText.trim()}
              className="px-6 py-2.5 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white rounded-xl font-bold text-xs shadow-lg shadow-blue-600/30 flex items-center gap-2 cursor-pointer disabled:opacity-50 transition-all"
            >
              {isAnalyzing ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" /> Analyzing...
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4 text-blue-200" /> Evaluate Ingredients
                </>
              )}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
