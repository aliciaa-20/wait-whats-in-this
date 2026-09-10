import React, { useState, useEffect } from 'react';
import { NavLink, Link } from 'react-router-dom';
import { ShieldCheck, UserCheck, Camera, History, Info, Wifi, WifiOff } from 'lucide-react';
import { getHealth } from '../services/api';

export default function Navbar() {
  const [isOnline, setIsOnline] = useState(false);

  useEffect(() => {
    let isMounted = true;
    const checkStatus = async () => {
      const res = await getHealth();
      if (isMounted) setIsOnline(res.online);
    };
    checkStatus();
    const interval = setInterval(checkStatus, 8000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  const navItems = [
    { to: '/', label: 'Profile', icon: UserCheck },
    { to: '/scan', label: 'Scan', icon: Camera },
    { to: '/history', label: 'History', icon: History },
    { to: '/about', label: 'About', icon: Info },
  ];

  return (
    <header className="sticky top-0 z-50 bg-stone-900 text-stone-100 shadow-md border-b border-stone-800">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
        
        {/* Brand Logo */}
        <Link to="/" className="flex items-center gap-2.5 group">
          <div className="w-9 h-9 rounded-xl bg-emerald-600 text-white flex items-center justify-center shadow-md shadow-emerald-900/30 group-hover:bg-emerald-500 transition-all">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div>
            <span className="font-extrabold text-base sm:text-lg tracking-tight text-white block leading-none">
              Wait, What's In This?
            </span>
            <span className="text-[10px] text-stone-400 font-medium tracking-wide">
              AI Food Allergen Detection
            </span>
          </div>
        </Link>

        {/* Navigation Links */}
        <nav className="flex items-center gap-1 sm:gap-2">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/'}
                className={({ isActive }) =>
                  `px-3 py-2 rounded-xl text-xs sm:text-sm font-semibold flex items-center gap-1.5 transition-all ${
                    isActive
                      ? 'bg-stone-800 text-emerald-400 shadow-inner'
                      : 'text-stone-300 hover:text-white hover:bg-stone-800/60'
                  }`
                }
              >
                <Icon className="w-4 h-4" />
                <span>{item.label}</span>
              </NavLink>
            );
          })}
        </nav>

        {/* Backend Status Dot Indicator */}
        <div className="hidden sm:flex items-center gap-2 pl-2">
          <div
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium border ${
              isOnline
                ? 'bg-emerald-950/60 text-emerald-300 border-emerald-700/50'
                : 'bg-amber-950/60 text-amber-300 border-amber-700/50'
            }`}
            title={isOnline ? 'Backend API connected (http://127.0.0.1:8000)' : 'Backend API offline or connecting...'}
          >
            <span className={`w-2 h-2 rounded-full ${isOnline ? 'bg-emerald-400 motion-safe:animate-pulse' : 'bg-amber-400'}`} />
            <span>{isOnline ? 'API Connected' : 'API Offline'}</span>
          </div>
        </div>

      </div>
    </header>
  );
}
