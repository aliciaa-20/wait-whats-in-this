import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Camera, Upload, Edit, RefreshCw, Sparkles, Image as ImageIcon, X, AlertCircle } from 'lucide-react';
import { CANONICAL_ALLERGENS, analyzeLabel } from '../services/api';

export default function ScanPage() {
  const navigate = useNavigate();
  const fileInputRef = useRef(null);
  const cameraInputRef = useRef(null);

  // Read saved profile allergies or redirect if not set
  const [allergies, setAllergies] = useState([]);
  const [selectedFile, setSelectedFile] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);
  const [language, setLanguage] = useState('en');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [errorMessage, setErrorMessage] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const [analyzingStage, setAnalyzingStage] = useState(0);

  // Perceived-progress sequence while waiting on the real OCR/matcher
  // call - the stages don't track real backend progress (the API is a
  // single request/response), they just give the user a sense of what
  // is happening during the wait instead of one static spinner.
  const ANALYZING_STAGES = [
    'Reading label...',
    'Matching ingredients...',
    'Calculating risk...',
  ];

  useEffect(() => {
    if (!isAnalyzing) {
      setAnalyzingStage(0);
      return;
    }
    const interval = setInterval(() => {
      setAnalyzingStage((prev) => (prev + 1) % ANALYZING_STAGES.length);
    }, 1600);
    return () => clearInterval(interval);
  }, [isAnalyzing]);

  useEffect(() => {
    const saved = localStorage.getItem('wait-whats-in-this-allergies');
    if (!saved) {
      navigate('/');
    } else {
      try {
        setAllergies(JSON.parse(saved));
      } catch (e) {
        setAllergies([]);
      }
    }
  }, [navigate]);

  const LANGUAGES = [
    { code: 'en', label: '🇬🇧 English (en)' },
    { code: 'fr', label: '🇫🇷 French (fr)' },
    { code: 'de', label: '🇩🇪 German (de)' },
    { code: 'es', label: '🇪🇸 Spanish (es)' },
    { code: 'nl', label: '🇳🇱 Dutch (nl)' },
    { code: 'it', label: '🇮🇹 Italian (it)' },
    { code: 'pt', label: '🇵🇹 Portuguese (pt)' },
    { code: 'ar', label: '🇸🇦 Arabic (ar)' },
  ];

  const handleFileChange = (file) => {
    if (!file) return;
    if (!file.type.startsWith('image/')) {
      setErrorMessage('Please select a valid image file (.jpg, .jpeg, .png, .webp, .bmp).');
      return;
    }
    setErrorMessage(null);
    setSelectedFile(file);
    const url = URL.createObjectURL(file);
    setImagePreview(url);
  };

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') setDragActive(true);
    else if (e.type === 'dragleave') setDragActive(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileChange(e.dataTransfer.files[0]);
    }
  };

  const handleAnalyze = async () => {
    if (!selectedFile) return;
    setIsAnalyzing(true);
    setErrorMessage(null);

    try {
      // Call backend API
      const resultData = await analyzeLabel(selectedFile, allergies, language);

      const timestamp = new Date().toLocaleString();
      const uniqueId = `scan_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;

      const historyRecord = {
        id: uniqueId,
        timestamp,
        filename: selectedFile.name || 'Food Label Image',
        language,
        result: resultData,
        imagePreview,
      };

      // Save to localStorage history
      const savedHistory = localStorage.getItem('wait-whats-in-this-history');
      let historyList = [];
      if (savedHistory) {
        try {
          historyList = JSON.parse(savedHistory);
        } catch (e) {
          historyList = [];
        }
      }
      historyList.unshift(historyRecord);
      localStorage.setItem('wait-whats-in-this-history', JSON.stringify(historyList));

      // Automatic navigate to /results
      navigate('/results', {
        state: {
          result: resultData,
          imagePreview,
          timestamp,
          id: uniqueId,
        },
      });
    } catch (err) {
      setErrorMessage(err.message || 'Error occurred while contacting backend server.');
    } finally {
      setIsAnalyzing(false);
    }
  };

  // Get display names for active saved allergy tags
  const activeAllergyNames = allergies.map(
    (id) => CANONICAL_ALLERGENS.find((a) => a.id === id)?.name || id
  );

  return (
    <div className="max-w-4xl mx-auto px-4 py-8 space-y-6">
      
      {/* Top Banner: Active Saved Allergy Profile */}
      <div className="bg-white rounded-3xl p-5 shadow-sm border border-stone-200 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="space-y-1">
          <span className="text-xs font-bold uppercase tracking-wider text-stone-500 block">
            Active Allergy Profile
          </span>
          <div className="flex flex-wrap gap-1.5 pt-1">
            {activeAllergyNames.length > 0 ? (
              activeAllergyNames.map((name, i) => (
                <span
                  key={i}
                  className="px-2.5 py-0.5 text-xs font-bold bg-emerald-100 text-emerald-800 border border-emerald-300 rounded-lg"
                >
                  {name}
                </span>
              ))
            ) : (
              <span className="text-xs text-amber-700 italic">No specific allergies selected.</span>
            )}
          </div>
        </div>

        <Link
          to="/"
          className="px-4 py-2 bg-stone-100 hover:bg-stone-200 text-stone-800 text-xs font-bold rounded-2xl border border-stone-300 flex items-center justify-center gap-1.5 shrink-0 transition-colors"
        >
          <Edit className="w-3.5 h-3.5" /> Edit Profile
        </Link>
      </div>

      {/* Main Scanner Section */}
      <div className="bg-white rounded-3xl p-6 sm:p-8 shadow-sm border border-stone-200 space-y-6">
        
        {/* Header & Language Dropdown */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-stone-100 pb-4">
          <div>
            <h1 className="text-lg sm:text-xl font-extrabold text-stone-900 tracking-tight flex items-center gap-2">
              <Camera className="w-5 h-5 text-emerald-600" /> Scan Food Label
            </h1>
            <p className="text-xs text-stone-500 mt-0.5">
              Upload or photograph a packaged food ingredient label for instant AI analysis.
            </p>
          </div>

          {/* Language Selector Dropdown */}
          <div className="flex items-center gap-2 bg-stone-50 px-3 py-1.5 rounded-2xl border border-stone-200 shrink-0">
            <span className="text-xs font-bold text-stone-600">OCR Language:</span>
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              className="bg-transparent text-xs font-bold text-stone-900 rounded cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2"
            >
              {LANGUAGES.map((lang) => (
                <option key={lang.code} value={lang.code}>
                  {lang.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Dual Input Area */}
        <div className="space-y-4">
          
          {/* Dropzone & Preview Container */}
          <div
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            className={`relative border-2 border-dashed rounded-3xl p-6 sm:p-8 text-center transition-all ${
              dragActive
                ? 'border-emerald-500 bg-emerald-50/50 scale-[1.005]'
                : selectedFile
                ? 'border-emerald-300 bg-stone-50'
                : 'border-stone-300 bg-stone-50/60 hover:border-stone-400 hover:bg-stone-50'
            }`}
          >
            {/* Hidden File Inputs */}
            <input
              type="file"
              ref={fileInputRef}
              accept="image/jpeg,image/jpg,image/png,image/webp,image/bmp"
              onChange={(e) => e.target.files?.[0] && handleFileChange(e.target.files[0])}
              className="hidden"
            />
            <input
              type="file"
              ref={cameraInputRef}
              accept="image/*"
              capture="environment"
              onChange={(e) => e.target.files?.[0] && handleFileChange(e.target.files[0])}
              className="hidden"
            />

            {imagePreview ? (
              <div className="space-y-4 max-w-sm mx-auto">
                <div className="relative rounded-2xl overflow-hidden border border-stone-300 shadow-md">
                  <img
                    src={imagePreview}
                    alt="Food Label Preview"
                    className="w-full h-56 object-cover"
                  />
                  {isAnalyzing && (
                    <div
                      className="absolute inset-0 bg-black/60 backdrop-blur-xs flex flex-col items-center justify-center text-white"
                      role="status"
                      aria-live="polite"
                    >
                      <div className="scanner-beam motion-reduce:hidden" />
                      <RefreshCw className="w-8 h-8 text-emerald-400 animate-spin motion-reduce:animate-none mb-2" />
                      <span className="text-xs font-bold uppercase tracking-wider">
                        {ANALYZING_STAGES[analyzingStage]}
                      </span>
                    </div>
                  )}
                </div>

                <div className="flex items-center justify-center gap-2">
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    className="px-3.5 py-1.5 bg-stone-200 hover:bg-stone-300 text-stone-800 text-xs font-bold rounded-xl transition-colors"
                  >
                    Replace Image
                  </button>
                  <button
                    onClick={() => {
                      setSelectedFile(null);
                      setImagePreview(null);
                    }}
                    className="px-3.5 py-1.5 bg-rose-100 hover:bg-rose-200 text-rose-800 text-xs font-bold rounded-xl transition-colors"
                  >
                    Remove Image
                  </button>
                </div>
              </div>
            ) : (
              <div className="space-y-4 py-6">
                <div className="w-16 h-16 mx-auto rounded-3xl bg-emerald-100 text-emerald-700 flex items-center justify-center shadow-inner">
                  <Upload className="w-8 h-8" />
                </div>

                <div>
                  <p className="text-sm font-extrabold text-stone-800">
                    Drag and drop your food label image here
                  </p>
                  <p className="text-xs text-stone-500 mt-1">
                    Supports JPG, PNG, WEBP, and BMP up to 10 MB
                  </p>
                </div>

                <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    className="px-4 py-2.5 bg-stone-900 hover:bg-stone-800 text-white rounded-2xl text-xs font-bold shadow-md transition-all cursor-pointer"
                  >
                    <ImageIcon className="w-4 h-4 inline mr-1.5" /> Browse Files
                  </button>
                  <button
                    type="button"
                    onClick={() => cameraInputRef.current?.click()}
                    className="px-4 py-2.5 bg-emerald-700 hover:bg-emerald-800 text-white rounded-2xl text-xs font-bold shadow-md transition-all cursor-pointer"
                  >
                    <Camera className="w-4 h-4 inline mr-1.5" /> Take Photo / Open Camera
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Error Message Banner */}
          {errorMessage && (
            <div className="p-4 bg-rose-50 border border-rose-200 rounded-2xl text-rose-800 text-xs font-medium flex items-center justify-between">
              <span className="flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
                {errorMessage}
              </span>
              <button onClick={() => setErrorMessage(null)} className="text-rose-500 font-bold">
                <X className="w-4 h-4" />
              </button>
            </div>
          )}

          {/* Primary CTA: Analyze Label */}
          {selectedFile && (
            <div className="pt-2">
              <button
                onClick={handleAnalyze}
                disabled={isAnalyzing}
                className="w-full py-4 bg-emerald-700 hover:bg-emerald-800 text-white font-extrabold text-base rounded-2xl shadow-lg shadow-emerald-900/20 flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50 transition-all"
              >
                {isAnalyzing ? (
                  <>
                    <RefreshCw className="w-5 h-5 animate-spin motion-reduce:animate-none" /> Analyzing label...
                  </>
                ) : (
                  <>
                    <Sparkles className="w-5 h-5 text-amber-300" /> Analyze Label
                  </>
                )}
              </button>
            </div>
          )}

        </div>

      </div>

    </div>
  );
}
