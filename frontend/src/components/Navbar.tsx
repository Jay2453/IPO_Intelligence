'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { 
  Activity, 
  BarChart3, 
  BookOpen, 
  Layers, 
  Radio, 
  Database,
  RefreshCw 
} from 'lucide-react';
import { api } from '@/lib/api';

export const Navbar: React.FC = () => {
  const pathname = usePathname();
  const [dbHealthy, setDbHealthy] = useState<boolean | null>(null);
  const [seeding, setSeeding] = useState(false);
  const [seedSuccess, setSeedSuccess] = useState<string | null>(null);

  useEffect(() => {
    checkHealth();
  }, []);

  const checkHealth = async () => {
    try {
      const res = await api.getHealth();
      setDbHealthy(res.database === 'connected');
    } catch {
      setDbHealthy(false);
    }
  };

  const handleSeed = async () => {
    try {
      setSeeding(true);
      const res = await api.seedDemoData(true);
      setSeedSuccess('Demo data reset & seeded!');
      setTimeout(() => setSeedSuccess(null), 3000);
      window.location.reload();
    } catch (err: any) {
      alert(`Seeding failed: ${err.message}`);
    } finally {
      setSeeding(false);
    }
  };

  const navLinks = [
    { href: '/', label: 'Dashboard', icon: <BarChart3 className="w-4 h-4" /> },
    { href: '/radar', label: 'IPO Radar', icon: <Radio className="w-4 h-4" /> },
    { href: '/methodology', label: 'Methodology', icon: <BookOpen className="w-4 h-4" /> },
    { href: '/health', label: 'System Health', icon: <Activity className="w-4 h-4" /> },
  ];

  return (
    <header className="sticky top-0 z-50 w-full border-b border-slate-800 bg-slate-950/80 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Brand */}
        <div className="flex items-center gap-6">
          <Link href="/" className="flex items-center gap-3 group">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-cyan-400 p-[1px]">
              <div className="w-full h-full bg-slate-950 rounded-lg flex items-center justify-center">
                <Layers className="w-4 h-4 text-cyan-400 group-hover:rotate-12 transition-transform" />
              </div>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-sm tracking-wider text-slate-100 font-mono">
                  IPO INTELLIGENCE
                </span>
                <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-indigo-950/80 text-indigo-300 border border-indigo-700/50">
                  v1.0
                </span>
              </div>
              <p className="text-[11px] text-slate-400 tracking-tight">Institutional IPO Research Engine</p>
            </div>
          </Link>

          {/* Nav Items */}
          <nav className="hidden md:flex items-center gap-1 ml-4">
            {navLinks.map((link) => {
              const isActive = pathname === link.href;
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                    isActive
                      ? 'bg-slate-800/90 text-cyan-400 border border-slate-700 shadow-sm'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/60'
                  }`}
                >
                  {link.icon}
                  {link.label}
                </Link>
              );
            })}
          </nav>
        </div>

        {/* Right Action Bar */}
        <div className="flex items-center gap-3">
          {/* Database Live Ping Status */}
          <div className="flex items-center gap-2 px-2.5 py-1 rounded-full bg-slate-900 border border-slate-800 text-[11px] font-mono">
            <Database className="w-3 h-3 text-slate-400" />
            <span className="text-slate-400">DB:</span>
            {dbHealthy === null ? (
              <span className="w-2 h-2 rounded-full bg-slate-500 animate-pulse" />
            ) : dbHealthy ? (
              <span className="flex items-center gap-1.5 text-emerald-400">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping opacity-75" />
                Live
              </span>
            ) : (
              <span className="flex items-center gap-1.5 text-rose-400">
                <span className="w-2 h-2 rounded-full bg-rose-400" />
                Offline
              </span>
            )}
          </div>

          {/* Dev Seed Button */}
          <button
            onClick={handleSeed}
            disabled={seeding}
            className="hidden sm:flex items-center gap-1.5 px-3 py-1 text-xs font-mono rounded-lg border border-amber-500/30 bg-amber-950/20 text-amber-400 hover:bg-amber-950/40 transition-colors disabled:opacity-50"
            title="Development-only: Reset and seed verified demo records"
          >
            <RefreshCw className={`w-3 h-3 ${seeding ? 'animate-spin' : ''}`} />
            {seeding ? 'Seeding...' : 'Reset Demo Data'}
          </button>
        </div>
      </div>
      {seedSuccess && (
        <div className="bg-amber-500/10 border-b border-amber-500/20 text-amber-400 text-xs py-1 text-center font-mono">
          ✓ {seedSuccess}
        </div>
      )}
    </header>
  );
};
