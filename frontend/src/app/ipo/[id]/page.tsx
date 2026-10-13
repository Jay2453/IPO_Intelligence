'use client';

import React, { useEffect, useState, use, Suspense } from 'react';
import Link from 'next/link';
import { 
  ArrowLeft, 
  FileText, 
  TrendingUp, 
  Clock, 
  Building2, 
  Scale, 
  Users, 
  AlertTriangle, 
  BrainCircuit, 
  CheckCircle2, 
  ShieldCheck,
  Hash,
  ExternalLink
} from 'lucide-react';
import { api } from '@/lib/api';
import { IPODetail } from '@/lib/types';
import { StatusBadge } from '@/components/StatusBadge';
import { DemoBadge } from '@/components/DemoBadge';
import { EmptyState } from '@/components/EmptyState';
import { MetricCard } from '@/components/MetricCard';

interface PageProps {
  params: Promise<{ id: string }>;
}

export default function IpoDetailPage({ params }: PageProps) {
  return (
    <Suspense fallback={<div className="py-20 text-center font-mono text-xs text-slate-400">Loading IPO dossier...</div>}>
      <IpoDetailContent params={params} />
    </Suspense>
  );
}

function IpoDetailContent({ params }: PageProps) {
  const resolvedParams = use(params);
  const ipoId = resolvedParams.id;

  const [ipo, setIpo] = useState<IPODetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'overview' | 'financials' | 'subscription' | 'documents' | 'predictions' | 'risks'>('overview');

  const [extractingDocId, setExtractingDocId] = useState<string | null>(null);

  const handleExtractDocument = async (docId: string) => {
    try {
      setExtractingDocId(docId);
      await api.extractDocument(docId);
      await loadIpoDetail();
    } catch (err: any) {
      alert(`Extraction failed: ${err.message}`);
    } finally {
      setExtractingDocId(null);
    }
  };

  useEffect(() => {
    loadIpoDetail();
  }, [ipoId]);

  const loadIpoDetail = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getIpoDetail(ipoId);
      setIpo(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load IPO details.');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="py-20 text-center font-mono text-xs text-slate-400">
        <div className="inline-block animate-spin mr-2">◒</div> Loading comprehensive IPO intelligence dossier...
      </div>
    );
  }

  if (error || !ipo) {
    return (
      <div className="max-w-2xl mx-auto py-12 space-y-4">
        <Link href="/radar" className="inline-flex items-center gap-2 text-xs font-mono text-cyan-400 hover:text-cyan-300">
          <ArrowLeft className="w-3.5 h-3.5" /> Back to IPO Radar
        </Link>
        <div className="p-6 rounded-xl border border-rose-800 bg-rose-950/40 text-rose-200 text-xs">
          <h3 className="text-sm font-bold mb-1">Issue Record Not Found</h3>
          <p>{error || 'The requested IPO identifier does not exist.'}</p>
        </div>
      </div>
    );
  }

  const latestPrediction = ipo.predictions.find((p) => p.prediction_status === 'ACTIVE');
  const latestSubscription = ipo.subscriptions[0];
  const listingOutcome = ipo.market_observations.find((m) => m.observation_type === 'LISTING_OUTCOME');

  return (
    <div className="space-y-6">
      {/* Navigation Breadcrumb */}
      <div className="flex items-center justify-between">
        <Link
          href="/radar"
          className="inline-flex items-center gap-2 text-xs font-mono text-slate-400 hover:text-cyan-400 transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          Back to IPO Radar
        </Link>
        <div className="flex items-center gap-3">
          {ipo.is_demo && <DemoBadge size="md" />}
          <span className="text-xs font-mono text-slate-500">ID: {ipo.id.substring(0, 8)}...</span>
        </div>
      </div>

      {/* Hero Header Dossier */}
      <div className="p-6 sm:p-8 rounded-2xl border border-slate-800 bg-slate-900/80 backdrop-blur-sm space-y-6">
        <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2.5">
              <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
                {ipo.company_name}
              </h1>
            </div>

            <div className="flex flex-wrap items-center gap-3 text-xs font-mono text-slate-400">
              <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                {ipo.exchange.replace('_', ' & ')}
              </span>
              <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                {ipo.category}
              </span>
              {ipo.symbol && (
                <span className="text-cyan-400 font-semibold">Ticker: {ipo.symbol}</span>
              )}
              <span>•</span>
              <span>Updated: {new Date(ipo.updated_at).toLocaleDateString('en-IN')}</span>
            </div>
          </div>

          <div className="flex flex-col md:items-end gap-2 shrink-0">
            <StatusBadge status={ipo.lifecycle_status} type="lifecycle" />
            <div className="flex items-center gap-2 text-xs font-mono text-slate-400">
              <span>Data Completeness:</span>
              <span className="text-slate-200 font-semibold">{ipo.data_completeness_pct}%</span>
            </div>
          </div>
        </div>

        {/* Highlight Metrics Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 pt-4 border-t border-slate-800/80">
          <div>
            <span className="text-[11px] font-mono uppercase text-slate-400 block">Price Band</span>
            <span className="text-sm font-bold font-mono text-slate-100">
              {ipo.min_price && ipo.max_price
                ? `₹${ipo.min_price} - ₹${ipo.max_price}`
                : ipo.max_price
                ? `₹${ipo.max_price}`
                : 'Pending RHP'}
            </span>
          </div>

          <div>
            <span className="text-[11px] font-mono uppercase text-slate-400 block">Total Issue</span>
            <span className="text-sm font-bold font-mono text-slate-100">
              {ipo.issue_size_crores ? `₹${ipo.issue_size_crores.toLocaleString()} Cr` : 'Pending'}
            </span>
          </div>

          <div>
            <span className="text-[11px] font-mono uppercase text-slate-400 block">Fresh / OFS</span>
            <span className="text-sm font-mono text-slate-200">
              {ipo.fresh_issue_crores ? `₹${ipo.fresh_issue_crores} Cr` : '-'} /{' '}
              {ipo.ofs_crores ? `₹${ipo.ofs_crores} Cr` : '-'}
            </span>
          </div>

          <div>
            <span className="text-[11px] font-mono uppercase text-slate-400 block">Lot Size</span>
            <span className="text-sm font-mono text-slate-100">
              {ipo.lot_size ? `${ipo.lot_size} Shares` : 'Pending'}
            </span>
          </div>

          <div>
            <span className="text-[11px] font-mono uppercase text-slate-400 block">Subscription</span>
            <span className="text-sm font-bold font-mono text-cyan-400">
              {latestSubscription?.total_subscription_times
                ? `${latestSubscription.total_subscription_times}x`
                : 'Not Open'}
            </span>
          </div>

          <div>
            <span className="text-[11px] font-mono uppercase text-slate-400 block">Win Probability</span>
            <span className="text-sm font-bold font-mono text-emerald-400">
              {latestPrediction?.positive_return_prob
                ? `${(latestPrediction.positive_return_prob * 100).toFixed(1)}%`
                : 'Pre-Model'}
            </span>
          </div>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="flex border-b border-slate-800 overflow-x-auto space-x-1">
        {[
          { key: 'overview', label: 'Offering Overview' },
          { key: 'financials', label: 'Financial Statements' },
          { key: 'subscription', label: 'Subscription Velocity' },
          { key: 'documents', label: 'Filings & Provenance' },
          { key: 'predictions', label: 'Predictive Models' },
          { key: 'risks', label: 'Disclosed Risks' },
        ].map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key as any)}
            className={`px-4 py-2.5 text-xs font-mono font-medium whitespace-nowrap transition-colors border-b-2 ${
              activeTab === tab.key
                ? 'border-cyan-400 text-cyan-400 bg-slate-900/50'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab 1: Overview */}
      {activeTab === 'overview' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6">
            {/* Timeline Milestones */}
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 space-y-4">
              <h3 className="text-xs font-mono uppercase tracking-wider text-slate-300 font-bold flex items-center gap-2">
                <Clock className="w-4 h-4 text-cyan-400" /> Statutory Timeline & Milestones
              </h3>

              {ipo.events.length === 0 ? (
                <EmptyState
                  title="No Logged Timeline Events"
                  description="Awaiting initial filing publication or ROC circular."
                  reason="Statutory filings pending"
                />
              ) : (
                <div className="relative border-l border-slate-800 ml-3 space-y-6 py-2">
                  {ipo.events.map((event) => (
                    <div key={event.id} className="relative pl-6">
                      <div className="absolute -left-1.5 top-1.5 w-3 h-3 rounded-full border-2 border-slate-900 bg-cyan-400"></div>
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-bold text-slate-200">{event.headline}</span>
                          <span className="text-[10px] font-mono text-slate-500">
                            {new Date(event.event_timestamp).toLocaleDateString('en-IN', {
                              month: 'short',
                              day: 'numeric',
                              year: 'numeric',
                            })}
                          </span>
                        </div>
                        {event.description && (
                          <p className="text-xs text-slate-400">{event.description}</p>
                        )}
                        {event.to_status && (
                          <div className="pt-1">
                            <StatusBadge status={event.to_status} type="lifecycle" />
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Merchant Bankers & Intermediaries */}
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 space-y-3">
              <h3 className="text-xs font-mono uppercase tracking-wider text-slate-300 font-bold flex items-center gap-2">
                <Building2 className="w-4 h-4 text-indigo-400" /> Book Running Lead Managers & Registrar
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs font-mono">
                <div className="p-3 rounded-lg bg-slate-950/60 border border-slate-800">
                  <span className="text-slate-400 block text-[11px]">Lead Managers (BRLM):</span>
                  <span className="text-slate-200 mt-1 block">
                    {ipo.lead_managers || <span className="italic text-slate-500">Not Disclosed in Preliminary Draft</span>}
                  </span>
                </div>
                <div className="p-3 rounded-lg bg-slate-950/60 border border-slate-800">
                  <span className="text-slate-400 block text-[11px]">Registrar to Issue:</span>
                  <span className="text-slate-200 mt-1 block">
                    {ipo.registrar || <span className="italic text-slate-500">Not Disclosed</span>}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Right Rail: Key Offering Parameters */}
          <div className="space-y-6">
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 space-y-4">
              <h3 className="text-xs font-mono uppercase tracking-wider text-slate-300 font-bold">
                Issue Parameters
              </h3>
              <dl className="space-y-2.5 text-xs font-mono divide-y divide-slate-800/80">
                <div className="flex justify-between pt-2">
                  <dt className="text-slate-400">Face Value</dt>
                  <dd className="text-slate-200">
                    {ipo.face_value ? `₹${ipo.face_value} per share` : 'Unavailable'}
                  </dd>
                </div>
                <div className="flex justify-between pt-2">
                  <dt className="text-slate-400">Issue Type</dt>
                  <dd className="text-slate-200">Book Built Issue</dd>
                </div>
                <div className="flex justify-between pt-2">
                  <dt className="text-slate-400">Open Date</dt>
                  <dd className="text-slate-200">{ipo.open_date || 'Awaiting RHP'}</dd>
                </div>
                <div className="flex justify-between pt-2">
                  <dt className="text-slate-400">Close Date</dt>
                  <dd className="text-slate-200">{ipo.close_date || 'Awaiting RHP'}</dd>
                </div>
                <div className="flex justify-between pt-2">
                  <dt className="text-slate-400">Allotment Date</dt>
                  <dd className="text-slate-200">{ipo.allotment_date || 'Awaiting RHP'}</dd>
                </div>
                <div className="flex justify-between pt-2">
                  <dt className="text-slate-400">Listing Date</dt>
                  <dd className="text-slate-200">{ipo.listing_date || 'Awaiting Allotment'}</dd>
                </div>
              </dl>
            </div>

            {/* Listing Verification Outcome (if listed) */}
            {listingOutcome && (
              <div className="rounded-xl border border-teal-800/60 bg-teal-950/20 p-5 space-y-3">
                <div className="flex items-center gap-2 text-teal-300 font-mono text-xs font-bold uppercase">
                  <ShieldCheck className="w-4 h-4" /> Bhavcopy Verified Outcome
                </div>
                <div className="space-y-2 text-xs font-mono">
                  <div className="flex justify-between">
                    <span className="text-slate-400">Issue Price:</span>
                    <span className="text-slate-200">₹{listingOutcome.final_issue_price_inr}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Day 1 Open:</span>
                    <span className="text-slate-200">₹{listingOutcome.listing_open_price_inr}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Day 1 Close:</span>
                    <span className="text-slate-200">₹{listingOutcome.listing_close_price_inr}</span>
                  </div>
                  <div className="flex justify-between pt-2 border-t border-teal-800/40">
                    <span className="text-slate-300 font-bold">Listing Gain:</span>
                    <span className="text-emerald-400 font-bold">
                      +{listingOutcome.listing_gain_pct}%
                    </span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tab 2: Financials */}
      {activeTab === 'financials' && (
        <div className="space-y-6">
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-mono uppercase tracking-wider text-slate-200 font-bold">
                  Restated Financial Statements (INR Crores)
                </h3>
                <p className="text-xs text-slate-400 mt-1">
                  Extracted directly from Statutory Audited Annexures in the Prospectus.
                </p>
              </div>
            </div>

            {ipo.financials.length === 0 ? (
              <EmptyState
                title="Financial Statements Not Yet Extracted"
                description="Audited restated financials have not been parsed for this draft filing."
                reason="DRHP parsing scheduled in Phase 2 pipeline"
                icon="question"
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs font-mono border-collapse">
                  <thead>
                    <tr className="border-b border-slate-800 text-slate-400 uppercase text-[11px]">
                      <th className="py-2.5 px-3 text-left">Period</th>
                      <th className="py-2.5 px-3 text-right">Revenue (₹ Cr)</th>
                      <th className="py-2.5 px-3 text-right">EBITDA (₹ Cr)</th>
                      <th className="py-2.5 px-3 text-right">PAT (₹ Cr)</th>
                      <th className="py-2.5 px-3 text-right">Net Worth (₹ Cr)</th>
                      <th className="py-2.5 px-3 text-right">Total Debt (₹ Cr)</th>
                      <th className="py-2.5 px-3 text-right">ROE (%)</th>
                      <th className="py-2.5 px-3 text-right">EPS (₹)</th>
                      <th className="py-2.5 px-3 text-center">Provenance</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {ipo.financials.map((fin) => (
                      <tr key={fin.id} className="hover:bg-slate-800/30">
                        <td className="py-3 px-3 font-bold text-slate-200">
                          {fin.fiscal_year}
                          {fin.is_restated && (
                            <span className="ml-1.5 px-1.5 py-0.2 rounded text-[9px] bg-slate-800 text-slate-400 border border-slate-700">
                              Restated
                            </span>
                          )}
                        </td>
                        <td className="py-3 px-3 text-right text-slate-200">
                          {fin.revenue_crores?.toLocaleString() ?? '-'}
                        </td>
                        <td className="py-3 px-3 text-right text-slate-200">
                          {fin.ebitda_crores?.toLocaleString() ?? '-'}
                        </td>
                        <td className="py-3 px-3 text-right text-emerald-400 font-semibold">
                          {fin.pat_crores?.toLocaleString() ?? '-'}
                        </td>
                        <td className="py-3 px-3 text-right text-slate-300">
                          {fin.net_worth_crores?.toLocaleString() ?? '-'}
                        </td>
                        <td className="py-3 px-3 text-right text-slate-300">
                          {fin.total_debt_crores?.toLocaleString() ?? '-'}
                        </td>
                        <td className="py-3 px-3 text-right text-slate-300">
                          {fin.roe_pct ? `${fin.roe_pct}%` : '-'}
                        </td>
                        <td className="py-3 px-3 text-right text-slate-300">
                          {fin.eps_inr ? `₹${fin.eps_inr}` : '-'}
                        </td>
                        <td className="py-3 px-3 text-center">
                          {fin.source_page ? (
                            <span className="px-2 py-0.5 rounded bg-cyan-950/80 text-cyan-300 border border-cyan-800/60 text-[10px] font-semibold" title={`Extracted from Prospectus Page ${fin.source_page}`}>
                              Page {fin.source_page}
                            </span>
                          ) : (
                            <span className="text-slate-500 text-[10px]">-</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tab 3: Subscriptions */}
      {activeTab === 'subscription' && (
        <div className="space-y-6">
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 space-y-4">
            <h3 className="text-sm font-mono uppercase tracking-wider text-slate-200 font-bold">
              Bidding Demand & Category Oversubscription
            </h3>

            {ipo.subscriptions.length === 0 ? (
              <EmptyState
                title="Bidding Data Not Available"
                description="Subscription snapshots commence once the public issue opens on the exchange."
                reason={ipo.lifecycle_status === 'SUBSCRIPTION_OPEN' ? 'Polling live exchange feed' : 'Issue bidding not currently open'}
                icon="info"
              />
            ) : (
              <div className="space-y-4">
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                  <MetricCard
                    label="QIB Multiple"
                    value={latestSubscription?.qib_subscription_times ? `${latestSubscription.qib_subscription_times}x` : '0x'}
                    subtext="Qualified Institutional Buyers"
                  />
                  <MetricCard
                    label="NII / HNI Multiple"
                    value={latestSubscription?.nii_subscription_times ? `${latestSubscription.nii_subscription_times}x` : '0x'}
                    subtext="Non-Institutional Investors"
                  />
                  <MetricCard
                    label="Retail Multiple"
                    value={latestSubscription?.rii_subscription_times ? `${latestSubscription.rii_subscription_times}x` : '0x'}
                    subtext="Retail Individual Bidders"
                  />
                  <MetricCard
                    label="Total Oversubscription"
                    value={latestSubscription?.total_subscription_times ? `${latestSubscription.total_subscription_times}x` : '0x'}
                    subtext="Aggregate Cumulative"
                    highlight={true}
                  />
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tab 4: Documents & Provenance */}
      {activeTab === 'documents' && (
        <div className="space-y-6">
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-mono uppercase tracking-wider text-slate-200 font-bold flex items-center gap-2">
                  <FileText className="w-4 h-4 text-cyan-400" /> Statutory Filings & Document Provenance
                </h3>
                <p className="text-xs text-slate-400 mt-1">
                  Immutable document storage with SHA-256 fingerprint verification and SEBI origin tracking.
                </p>
              </div>
            </div>

            {ipo.documents.length === 0 ? (
              <EmptyState
                title="No Official Filings Attached"
                description="Awaiting SEBI / exchange public document ingestion."
                reason="Document sync pending"
              />
            ) : (
              <div className="space-y-3">
                {ipo.documents.map((doc) => (
                  <div
                    key={doc.id}
                    className="p-4 rounded-lg border border-slate-800 bg-slate-950/60 flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs font-mono"
                  >
                    <div className="space-y-1.5 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="px-2 py-0.5 rounded bg-indigo-950/80 text-indigo-300 border border-indigo-800 font-bold">
                          {doc.document_type} v{doc.version_number}
                        </span>
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          doc.extraction_status === 'EXTRACTED'
                            ? 'bg-emerald-950/80 text-emerald-300 border border-emerald-800/60'
                            : doc.extraction_status === 'PENDING'
                            ? 'bg-amber-950/80 text-amber-300 border border-amber-800/60'
                            : doc.extraction_status === 'FAILED'
                            ? 'bg-rose-950/80 text-rose-300 border border-rose-800/60'
                            : 'bg-purple-950/80 text-purple-300 border border-purple-800/60'
                        }`}>
                          {doc.extraction_status || 'PENDING'}
                        </span>
                        {doc.filing_date && (
                          <span className="text-slate-400 text-[11px]">
                            Filing Date: {doc.filing_date}
                          </span>
                        )}
                        <span className="font-semibold text-slate-200">{doc.file_name}</span>
                      </div>
                      <div className="text-[11px] text-slate-400 flex flex-wrap items-center gap-3 pt-0.5">
                        <div className="flex items-center gap-1">
                          <Hash className="w-3 h-3 text-slate-500" />
                          <span>SHA-256:</span>
                          <code className="text-slate-300" title={doc.file_hash_sha256}>
                            {doc.file_hash_sha256 ? `${doc.file_hash_sha256.substring(0, 16)}...` : '-'}
                          </code>
                        </div>
                        {doc.file_size_bytes && (
                          <span className="text-slate-500">
                            • {(doc.file_size_bytes / (1024 * 1024)).toFixed(2)} MB
                          </span>
                        )}
                      </div>
                      {doc.extraction_error && (
                        <p className="text-[11px] text-rose-400">
                          Error: {doc.extraction_error}
                        </p>
                      )}
                    </div>

                    <div className="flex items-center gap-2 shrink-0 self-start md:self-center">
                      {doc.extraction_status === 'PENDING' && (
                        <button
                          onClick={() => handleExtractDocument(doc.id)}
                          disabled={extractingDocId === doc.id}
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-900/60 hover:bg-indigo-800 text-indigo-200 border border-indigo-700 text-xs transition-colors disabled:opacity-50"
                          title="Extract financial statements from this filing"
                        >
                          <FileText className={`w-3.5 h-3.5 ${extractingDocId === doc.id ? 'animate-spin' : ''}`} />
                          {extractingDocId === doc.id ? 'Extracting...' : 'Extract Financials'}
                        </button>
                      )}
                      <a
                        href={doc.file_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs transition-colors"
                      >
                        View Filing
                        <ExternalLink className="w-3.5 h-3.5" />
                      </a>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tab 5: Predictions */}
      {activeTab === 'predictions' && (
        <div className="space-y-6">
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 space-y-4">
            <h3 className="text-sm font-mono uppercase tracking-wider text-slate-200 font-bold flex items-center gap-2">
              <BrainCircuit className="w-4 h-4 text-emerald-400" /> Historical Append-Only Predictions
            </h3>

            {ipo.predictions.length === 0 ? (
              <EmptyState
                title="No Model Inferences Computed"
                description="Predictive models execute only when necessary feature vectors (pricing, financials) are validated."
                reason="Pending required feature vector inputs"
              />
            ) : (
              <div className="space-y-4">
                {ipo.predictions.map((pred) => (
                  <div
                    key={pred.id}
                    className="p-5 rounded-xl border border-slate-800 bg-slate-950/70 space-y-4"
                  >
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800/60 pb-3">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-xs font-mono text-cyan-400">
                            {pred.model_version?.model_name || 'MODEL_REGISTRY'}
                          </span>
                          <span className="text-[11px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
                            {pred.model_version?.version_tag || 'v1.0'}
                          </span>
                        </div>
                        <span className="text-[11px] font-mono text-slate-500">
                          Forecast Horizon: {pred.forecast_horizon} • Inferred at:{' '}
                          {new Date(pred.prediction_timestamp).toLocaleDateString('en-IN')}
                        </span>
                      </div>

                      <div className="flex items-center gap-3">
                        <div className="text-right">
                          <span className="text-base font-bold font-mono text-emerald-400">
                            {pred.positive_return_prob
                              ? `${(pred.positive_return_prob * 100).toFixed(1)}%`
                              : '-'}
                          </span>
                          <span className="text-[10px] block font-mono text-slate-400">
                            Listing Win Prob
                          </span>
                        </div>
                        <div className="text-right pl-3 border-l border-slate-800">
                          <span className="text-base font-bold font-mono text-slate-200">
                            {pred.risk_decile}/10
                          </span>
                          <span className="text-[10px] block font-mono text-slate-400">
                            Risk Decile
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Explanatory Evidence */}
                    {pred.evidence_summary && (
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                        <div className="p-3 rounded-lg bg-emerald-950/20 border border-emerald-900/40 text-emerald-300">
                          <span className="font-bold block mb-1 font-mono uppercase text-[10px]">
                            Primary Positive Evidence
                          </span>
                          <ul className="list-disc list-inside space-y-0.5 text-slate-300">
                            {pred.evidence_summary.top_positive_factors?.map(
                              (factor: string, i: number) => (
                                <li key={i}>{factor}</li>
                              )
                            )}
                          </ul>
                        </div>
                        <div className="p-3 rounded-lg bg-rose-950/20 border border-rose-900/40 text-rose-300">
                          <span className="font-bold block mb-1 font-mono uppercase text-[10px]">
                            Primary Risk Factors
                          </span>
                          <ul className="list-disc list-inside space-y-0.5 text-slate-300">
                            {pred.evidence_summary.top_negative_factors?.map(
                              (factor: string, i: number) => (
                                <li key={i}>{factor}</li>
                              )
                            )}
                          </ul>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tab 6: Disclosed Risks */}
      {activeTab === 'risks' && (
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 space-y-4">
          <h3 className="text-sm font-mono uppercase tracking-wider text-slate-200 font-bold flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-400" /> Statutory Risk Disclosures (DRHP Section II)
          </h3>
          <EmptyState
            title="Automated Risk Extraction Pending Phase 2"
            description="Statutory Internal and External Risk Factors will be extracted using the structured NLP pipeline once OCR processing is enabled."
            reason="Automated NLP extractor scheduled"
            icon="info"
          />
        </div>
      )}
    </div>
  );
}
