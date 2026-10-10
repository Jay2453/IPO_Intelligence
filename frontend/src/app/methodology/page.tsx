'use client';

import React from 'react';
import { 
  ShieldCheck, 
  BrainCircuit, 
  AlertTriangle, 
  Scale, 
  FileCheck2, 
  Lock,
  ArrowRight
} from 'lucide-react';
import Link from 'next/link';

export default function MethodologyPage() {
  return (
    <div className="max-w-4xl mx-auto space-y-10 py-4">
      {/* Page Title */}
      <div className="border-b border-slate-800 pb-6 space-y-2">
        <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-indigo-950/60 border border-indigo-800/50 text-[11px] font-mono text-indigo-300">
          <ShieldCheck className="w-3.5 h-3.5 text-indigo-400" />
          DISCLOSURE & METHODOLOGICAL FOUNDATION
        </div>
        <h1 className="text-3xl font-extrabold text-white tracking-tight">
          Research Principles & Predictive Architecture
        </h1>
        <p className="text-sm text-slate-400 leading-relaxed">
          How IPO Intelligence approaches Indian capital market offerings: strict data provenance, prevention of data leakage, and rigorous statistical calibration.
        </p>
      </div>

      {/* 4 Pillars of Product Design */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        
        {/* Card 1: What the App Predicts */}
        <div className="p-6 rounded-xl border border-slate-800 bg-slate-900/60 space-y-3">
          <div className="w-9 h-9 rounded-lg bg-cyan-950 flex items-center justify-center text-cyan-400 border border-cyan-800/60">
            <BrainCircuit className="w-5 h-5" />
          </div>
          <h3 className="text-base font-bold text-slate-100 font-mono">1. What The Engine Predicts</h3>
          <p className="text-xs text-slate-300 leading-relaxed">
            The platform models two distinct target variables:
          </p>
          <ul className="text-xs text-slate-400 space-y-1.5 list-disc list-inside">
            <li>
              <strong className="text-slate-200">Listing Win Probability:</strong> Calibrated probability that the official Day 1 closing price on the primary exchange equals or exceeds the discovered final issue price (Day-1 Close &ge; Issue Price).
            </li>
            <li>
              <strong className="text-slate-200">Listing Gain Decile:</strong> Estimated relative ranking and risk decile (1 to 10) evaluating volatility and post-listing distribution.
            </li>
          </ul>
        </div>

        {/* Card 2: Listing vs Long-Term Returns */}
        <div className="p-6 rounded-xl border border-slate-800 bg-slate-900/60 space-y-3">
          <div className="w-9 h-9 rounded-lg bg-indigo-950 flex items-center justify-center text-indigo-400 border border-indigo-800/60">
            <Scale className="w-5 h-5" />
          </div>
          <h3 className="text-base font-bold text-slate-100 font-mono">2. Listing Gains vs Long-Term Returns</h3>
          <p className="text-xs text-slate-300 leading-relaxed">
            Listing day return is heavily governed by immediate liquidity, retail excitement, and institutional oversubscription velocity. 
          </p>
          <p className="text-xs text-slate-400 leading-relaxed">
            Conversely, 1-year and 3-year performance depends fundamentally on operating cash flows, return on equity (ROE), capital expenditure discipline, and promoter integrity. The models treat short-term listing dynamics and multi-year investment quality as separate regimes.
          </p>
        </div>

        {/* Card 3: Anti-Leakage & Provenance */}
        <div className="p-6 rounded-xl border border-slate-800 bg-slate-900/60 space-y-3">
          <div className="w-9 h-9 rounded-lg bg-emerald-950 flex items-center justify-center text-emerald-400 border border-emerald-800/60">
            <Lock className="w-5 h-5" />
          </div>
          <h3 className="text-base font-bold text-slate-100 font-mono">3. Prevention of Future-Data Leakage</h3>
          <p className="text-xs text-slate-300 leading-relaxed">
            A fatal flaw in financial machine learning is allowing data known only <em>after</em> an event to leak into the historical training features.
          </p>
          <p className="text-xs text-slate-400 leading-relaxed">
            IPO Intelligence enforces hard temporal barriers: pre-listing models evaluate feature snapshots timestamped strictly before issue close date (T_close). Final listing prices, post-listing volumes, and subsequent earnings restatements are programmatically forbidden in inference vectors.
          </p>
        </div>

        {/* Card 4: Historical Performance Caveat */}
        <div className="p-6 rounded-xl border border-slate-800 bg-slate-900/60 space-y-3">
          <div className="w-9 h-9 rounded-lg bg-amber-950 flex items-center justify-center text-amber-400 border border-amber-800/60">
            <AlertTriangle className="w-5 h-5" />
          </div>
          <h3 className="text-base font-bold text-slate-100 font-mono">4. No Return Guarantees</h3>
          <p className="text-xs text-slate-300 leading-relaxed">
            Historical outcomes do not guarantee future performance. Capital market regimes shift during systemic macro pullbacks, liquidity tightening, or sector-specific headwinds.
          </p>
          <p className="text-xs text-slate-400 leading-relaxed">
            Probabilities produced by this system represent quantitative decision support. The application does not provide algorithmic order routing or investment advisory services.
          </p>
        </div>

      </div>

      {/* Model Validation & Provenance Process Flow */}
      <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-6 sm:p-8 space-y-6">
        <h3 className="text-sm font-mono uppercase tracking-wider text-slate-200 font-bold flex items-center gap-2">
          <FileCheck2 className="w-4 h-4 text-cyan-400" />
          Verification & Model Calibration Lifecycle
        </h3>

        <div className="space-y-4 text-xs font-mono text-slate-300">
          <div className="p-4 rounded-xl bg-slate-950/70 border border-slate-800 flex items-start gap-3">
            <span className="w-6 h-6 rounded-full bg-cyan-950 text-cyan-400 border border-cyan-800 flex items-center justify-center shrink-0 font-bold">1</span>
            <div>
              <strong className="text-white block mb-0.5">Statutory Document Hashing</strong>
              Every DRHP, RHP, and Basis of Allotment is recorded with SHA-256 integrity digests to ensure observations are tamper-evident.
            </div>
          </div>

          <div className="p-4 rounded-xl bg-slate-950/70 border border-slate-800 flex items-start gap-3">
            <span className="w-6 h-6 rounded-full bg-indigo-950 text-indigo-400 border border-indigo-800 flex items-center justify-center shrink-0 font-bold">2</span>
            <div>
              <strong className="text-white block mb-0.5">Model Version Registry</strong>
              Every prediction references an immutable ModelVersion ID, recording algorithm hyperparameters, training cutoff dates, and validation Brier scores.
            </div>
          </div>

          <div className="p-4 rounded-xl bg-slate-950/70 border border-slate-800 flex items-start gap-3">
            <span className="w-6 h-6 rounded-full bg-teal-950 text-teal-400 border border-teal-800 flex items-center justify-center shrink-0 font-bold">3</span>
            <div>
              <strong className="text-white block mb-0.5">Post-Listing Exchange Bhavcopy Reconciliation</strong>
              On listing day, official NSE and BSE daily Bhavcopy settlement files reconcile actual traded prices to verify predictions and prevent outcome falsification.
            </div>
          </div>
        </div>
      </div>

      {/* Bottom CTA */}
      <div className="flex items-center justify-between pt-4">
        <Link
          href="/radar"
          className="inline-flex items-center gap-2 text-xs font-mono text-cyan-400 hover:text-cyan-300"
        >
          Explore the Live IPO Radar
          <ArrowRight className="w-3.5 h-3.5" />
        </Link>
        <Link
          href="/health"
          className="inline-flex items-center gap-2 text-xs font-mono text-slate-400 hover:text-slate-200"
        >
          View System Telemetry
        </Link>
      </div>
    </div>
  );
}
