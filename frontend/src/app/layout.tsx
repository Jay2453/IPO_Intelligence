import React, { Suspense } from 'react';
import type { Metadata } from 'next';
import './globals.css';
import { Navbar } from '@/components/Navbar';

export const metadata: Metadata = {
  title: 'IPO Intelligence — Institutional Indian IPO Research & Predictive Analytics',
  description:
    'Institutional-grade financial intelligence, valuation modeling, subscription velocity tracking, and verified outcome analysis for Indian Mainboard and SME IPOs.',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-slate-950 text-slate-100 antialiased font-sans flex flex-col selection:bg-cyan-500/30 selection:text-cyan-200">
        <Suspense fallback={<div className="h-16 border-b border-slate-800 bg-slate-950" />}>
          <Navbar />
        </Suspense>
        <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <Suspense fallback={<div className="py-12 text-center text-xs font-mono text-slate-500">Loading view...</div>}>
            {children}
          </Suspense>
        </main>
        
        {/* Institutional Regulatory Disclaimer Footer */}
        <footer className="border-t border-slate-900 bg-slate-950/90 py-8 text-xs text-slate-500">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col md:flex-row items-center justify-between gap-4">
            <div className="space-y-1 text-center md:text-left">
              <p className="font-mono text-slate-400">IPO INTELLIGENCE PLATFORM — PHASE 1 FOUNDATION</p>
              <p>
                Strict provenance tracking. All predictions represent probabilistic research models, not trading advice or guaranteed returns.
              </p>
            </div>
            <div className="flex items-center gap-4 font-mono text-[11px] text-slate-400">
              <span>Exchange: NSE / BSE</span>
              <span>•</span>
              <span>Regulatory: SEBI Filings</span>
              <span>•</span>
              <span className="text-amber-500/80">Demo Environment Active</span>
            </div>
          </div>
        </footer>
      </body>
    </html>
  );
}
