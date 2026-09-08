import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Navbar from './components/Navbar';
import ProfilePage from './pages/ProfilePage';
import ScanPage from './pages/ScanPage';
import ResultsPage from './pages/ResultsPage';
import HistoryPage from './pages/HistoryPage';
import AboutPage from './pages/AboutPage';

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen flex flex-col bg-stone-50 text-stone-800 font-sans antialiased">
        {/* Sticky Top Navigation Bar */}
        <Navbar />

        {/* Page Content Routes */}
        <main className="flex-1 pb-12">
          <Routes>
            <Route path="/profile" element={<ProfilePage />} />
            <Route path="/" element={<ScanPage />} />
            <Route path="/results" element={<ResultsPage />} />
            <Route path="/history" element={<HistoryPage />} />
            <Route path="/about" element={<AboutPage />} />
          </Routes>
        </main>

        {/* Footer */}
        <footer className="border-t border-stone-200 py-6 bg-white text-center text-xs text-stone-500 space-y-1">
          <p className="font-bold text-stone-700">
            Wait, What's In This? — AI Food Allergen Detection Research Prototype
          </p>
          <p className="text-[11px] text-stone-400">
            Connected to FastAPI Backend (http://127.0.0.1:8000) • Open Food Facts Dataset
          </p>
        </footer>
      </div>
    </BrowserRouter>
  );
}
