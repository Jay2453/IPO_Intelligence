'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { 
  TrendingUp, 
  Calendar, 
  Sparkles, 
  Activity, 
  Database, 
  ShieldAlert, 
  ArrowRight, 
  Clock, 
  Layers,
  ChevronRight,
  BrainCircuit,
  FileCheck2
} from 'lucide-react';
import { api } from '@/lib/api';
import { IPOSummary, SystemStatusResponse } from '@/lib/types';
import { MetricCard } from '@/components/MetricCard';
import { StatusBadge } from '@/components/StatusBadge';
import { DemoBadge } from '@/components/DemoBadge';
import { EmptyState } from '@/components/EmptyState';

export default function DashboardPage() {
  const [ipos, setIpos] = useState<IPOSummary[]>([]);
  const [systemStatus, setSystemStatus] = useState<SystemStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadDashboardData();
  }, []);

  const loadDashboardData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [iposRes, statusRes] = await Promise.all([
        api.getIpos({ page: 1, page_size: 20, sort_by: 'created_at', sort_order: 'desc' }),
        api.getSystemStatus(),
      ]);
      setIpos(iposRes.items);
      setSystemStatus(statusRes);
    } catch (err: any) {
      setError(err.message || 'Unable to communicate with the backend service.');
    } finally {
      setLoading(false);
    }
  };

  // Groupings
  const activeOrUpcoming = ipos.filter(
    (i) => i.lifecycle_status === 'SUBSCRIPTION_OPEN' || i.lifecycle_status === 'PRICE_BAND_AVAILABLE'
  );
  const recentlyDiscovered = ipos.filter(
    (i) => i.lifecycle_status === 'DISCOVERED' || i.lifecycle_status === 'DOCUMENTS_PENDING' || i.lifecycle_status === 'PRELIMINARY_ANALYSIS'
  );
  const topRanked = ipos
    .filter((i) => i.positive_return_prob !== null && i.positive_return_prob !== undefined)
    .sort((a, b) => (b.positive_return_prob || 0) - (a.positive_return_prob || 0));

  const totalTracked = ipos.length;
  const demoCount = ipos.filter((i) => i.is_demo).length;

  return (
    <div className="space-y-8">
      {/* Overview Hero Header */}
      <div className="relative overflow-hidden rounded-2xl border border-slate-800 bg-gradient-to-r from-slate-900 via-slate-900/90 to-slate-950 p-6 sm:p-8">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
          <div className="space-y-2 max-w-2xl">
            <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-cyan-950/60 border border-cyan-800/50 text-[11px] font-mono text-cyan-300">
              <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse"></span>
              INDIAN CAPITAL MARKETS INTELLIGENCE
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight font-sans">
              IPO Discovery & Valuation Engine
            </h1>
            <p className="text-sm text-slate-400 leading-relaxed">
              Automated data extraction from SEBI DRHP/RHP filings, subscription velocity monitoring on NSE/BSE, calibrated return probabilities, and audit-grade provenance.
            </p>
          </div>

          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
            <Link
              href="/radar"
              className="inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-semibold text-xs tracking-wide transition-all shadow-lg shadow-cyan-950/30"
            >
              Launch IPO Radar
              <ArrowRight className="w-4 h-4" />
            </Link>
            <Link
              href="/methodology"
              className="inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 font-semibold text-xs transition-colors"
            >
              Methodology & Proof
            </Link>
          </div>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-xl border border-rose-800/60 bg-rose-950/30 text-rose-300 text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-rose-400 shrink-0" />
            <span>{error}</span>
          </div>
          <button
            onClick={loadDashboardData}
            className="px-2.5 py-1 bg-rose-900/50 border border-rose-700/60 rounded text-rose-200 font-mono text-xs hover:bg-rose-800/60"
          >
            Retry Connection
          </button>
        </div>
      )}

      {/* Top Level Metric Strip */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          label="Tracked Issues"
          value={totalTracked}
          subtext={`${demoCount} demo sandbox records`}
          icon={<Layers className="w-4 h-4" />}
        />
        <MetricCard
          label="Active & Upcoming"
          value={activeOrUpcoming.length}
          subtext="Bidding open or dates confirmed"
          icon={<Calendar className="w-4 h-4" />}
          highlight={activeOrUpcoming.length > 0}
        />
        <MetricCard
          label="Database Link"
          value={systemStatus?.database_connected ? 'CONNECTED' : 'DISCONNECTED'}
          subtext="Relational storage live"
          icon={<Database className="w-4 h-4" />}
        />
        <MetricCard
          label="Data Synchronization"
          value={systemStatus?.last_sync_status || 'IDLE'}
          subtext={
            systemStatus?.last_successful_sync
              ? `Last: ${new Date(systemStatus.last_successful_sync).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`
              : 'Crawler unconfigured'
          }
          icon={<Clock className="w-4 h-4" />}
        />
      </div>

      {/* Three Column Deep Sections */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Section 1: Active & Upcoming Bidding */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800/80 pb-3">
            <div className="flex items-center gap-2">
              <Calendar className="w-4 h-4 text-cyan-400" />
              <h2 className="text-sm font-semibold text-slate-100 uppercase tracking-wider font-mono">
                Active & Upcoming Issues
              </h2>
            </div>
            <span className="text-xs font-mono text-slate-400">({activeOrUpcoming.length})</span>
          </div>

          <div className="space-y-3">
            {activeOrUpcoming.length === 0 ? (
              <EmptyState
                title="No Open Subscription Issues"
                description="Currently no IPOs in active bidding or confirmed price band state."
                reason="Pipeline pending new RHP filings"
                icon="info"
              />
            ) : (
              activeOrUpcoming.map((ipo) => (
                <Link
                  key={ipo.id}
                  href={`/ipo/${ipo.id}`}
                  className="block p-3 rounded-lg border border-slate-800 bg-slate-950/40 hover:bg-slate-800/40 hover:border-slate-700 transition-all group"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-xs text-slate-200 group-hover:text-cyan-400 transition-colors">
                          {ipo.company_name}
                        </span>
                        {ipo.is_demo && <DemoBadge size="sm" />}
                      </div>
                      <div className="flex items-center gap-2 text-[11px] text-slate-400 mt-1 font-mono">
                        <span>{ipo.exchange}</span>
                        <span>•</span>
                        <span>{ipo.category}</span>
                        {ipo.max_price && (
                          <>
                            <span>•</span>
                            <span className="text-slate-300">₹{ipo.max_price}</span>
                          </>
                        )}
                      </div>
                    </div>
                    <StatusBadge status={ipo.lifecycle_status} type="lifecycle" />
                  </div>
                  
                  {ipo.latest_gmp_percent !== null && ipo.latest_gmp_percent !== undefined && (
                    <div className="mt-2.5 pt-2 border-t border-slate-800/60 flex items-center justify-between text-[11px] font-mono">
                      <span className="text-slate-400">Attributed GMP:</span>
                      <span className="text-emerald-400 font-semibold">
                        +₹{ipo.latest_gmp_inr} ({ipo.latest_gmp_percent}%)
                      </span>
                    </div>
                  )}
                </Link>
              ))
            )}
          </div>
        </div>

        {/* Section 2: Recently Discovered Filings */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800/80 pb-3">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-indigo-400" />
              <h2 className="text-sm font-semibold text-slate-100 uppercase tracking-wider font-mono">
                Recently Discovered Filings
              </h2>
            </div>
            <span className="text-xs font-mono text-slate-400">({recentlyDiscovered.length})</span>
          </div>

          <div className="space-y-3">
            {recentlyDiscovered.length === 0 ? (
              <EmptyState
                title="No Unprocessed Filings"
                description="All discovered filings have completed preliminary processing."
                icon="info"
              />
            ) : (
              recentlyDiscovered.map((ipo) => (
                <Link
                  key={ipo.id}
                  href={`/ipo/${ipo.id}`}
                  className="block p-3 rounded-lg border border-slate-800 bg-slate-950/40 hover:bg-slate-800/40 hover:border-slate-700 transition-all group"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-xs text-slate-200 group-hover:text-cyan-400 transition-colors">
                          {ipo.company_name}
                        </span>
                        {ipo.is_demo && <DemoBadge size="sm" />}
                      </div>
                      <div className="flex items-center gap-2 text-[11px] text-slate-400 mt-1 font-mono">
                        <span>{ipo.category}</span>
                        {ipo.issue_size_crores && (
                          <>
                            <span>•</span>
                            <span>₹{ipo.issue_size_crores.toLocaleString()} Cr</span>
                          </>
                        )}
                      </div>
                    </div>
                    <StatusBadge status={ipo.lifecycle_status} type="lifecycle" />
                  </div>

                  <div className="mt-2.5 pt-2 border-t border-slate-800/60 flex items-center justify-between text-[11px] font-mono">
                    <span className="text-slate-400">Data Completeness:</span>
                    <span className="text-slate-300">{ipo.data_completeness_pct}%</span>
                  </div>
                </Link>
              ))
            )}
          </div>
        </div>

        {/* Section 3: Calibrated Predictive Opportunities */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800/80 pb-3">
            <div className="flex items-center gap-2">
              <BrainCircuit className="w-4 h-4 text-emerald-400" />
              <h2 className="text-sm font-semibold text-slate-100 uppercase tracking-wider font-mono">
                Model Ranked Forecasts
              </h2>
            </div>
            <span className="text-xs font-mono text-slate-400">({topRanked.length})</span>
          </div>

          <div className="space-y-3">
            {topRanked.length === 0 ? (
              <EmptyState
                title="Awaiting Model Inferences"
                description="No active model predictions generated. Models trigger when RHP price bands and preliminary financials are finalized."
                reason="Pre-requisite features pending"
                icon="question"
              />
            ) : (
              topRanked.map((ipo) => (
                <Link
                  key={ipo.id}
                  href={`/ipo/${ipo.id}`}
                  className="block p-3 rounded-lg border border-slate-800 bg-slate-950/40 hover:bg-slate-800/40 hover:border-slate-700 transition-all group"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-xs text-slate-200 group-hover:text-cyan-400 transition-colors">
                          {ipo.company_name}
                        </span>
                        {ipo.is_demo && <DemoBadge size="sm" />}
                      </div>
                      <span className="text-[11px] font-mono text-slate-400 mt-1 block">
                        Risk Decile: {ipo.risk_decile}/10
                      </span>
                    </div>

                    {ipo.positive_return_prob != null && (
                      <div className="text-right">
                        <span className="text-xs font-bold font-mono text-emerald-400">
                          {(ipo.positive_return_prob * 100).toFixed(1)}%
                        </span>
                        <span className="text-[10px] block text-slate-400 font-mono">Win Prob</span>
                      </div>
                    )}
                  </div>
                </Link>
              ))
            )}
          </div>
        </div>

      </div>

      {/* System Integrity & Regulatory Lineage Banner */}
      <div className="rounded-xl border border-slate-800/80 bg-slate-900/30 p-4 sm:p-5 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-lg bg-slate-800 text-cyan-400">
            <FileCheck2 className="w-5 h-5" />
          </div>
          <div>
            <h4 className="text-xs font-bold font-mono uppercase tracking-wide text-slate-200">
              Regulatory Audit Guarantee & Anti-Leakage Protocol
            </h4>
            <p className="text-xs text-slate-400">
              All documents are cryptographically SHA-256 hashed. Pre-listing features strictly prohibit post-listing lookahead bias.
            </p>
          </div>
        </div>
        <Link
          href="/health"
          className="shrink-0 text-xs font-mono text-cyan-400 hover:text-cyan-300 flex items-center gap-1"
        >
          Check Ingestion Telemetry
          <ChevronRight className="w-3.5 h-3.5" />
        </Link>
      </div>
    </div>
  );
}
