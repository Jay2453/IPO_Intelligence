'use client';

import React, { useEffect, useState } from 'react';
import { 
  Activity, 
  Database, 
  Radio, 
  Server, 
  CheckCircle2, 
  XCircle, 
  AlertCircle, 
  Clock, 
  RotateCcw,
  ShieldCheck,
  FileText
} from 'lucide-react';
import { api } from '@/lib/api';
import { SystemStatusResponse, IngestionJob } from '@/lib/types';
import { MetricCard } from '@/components/MetricCard';
import { StatusBadge } from '@/components/StatusBadge';

export default function SystemHealthPage() {
  const [status, setStatus] = useState<SystemStatusResponse | null>(null);
  const [jobs, setJobs] = useState<IngestionJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchHealthData();
  }, []);

  const fetchHealthData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [statusRes, jobsRes] = await Promise.all([
        api.getSystemStatus(),
        api.getIngestionJobs({ page: 1, page_size: 10 }),
      ]);
      setStatus(statusRes);
      setJobs(jobsRes.items);
    } catch (err: any) {
      setError(err.message || 'Unable to connect to telemetry service.');
    } finally {
      setLoading(false);
    }
  };

  const [syncing, setSyncing] = useState(false);
  const [syncNotice, setSyncNotice] = useState<string | null>(null);

  const handleSyncNse = async () => {
    try {
      setSyncing(true);
      const res = await api.syncNse(true, 30);
      setSyncNotice(`NSE sync completed: ${res.records_inserted} inserted, ${res.records_updated} updated.`);
      await fetchHealthData();
      setTimeout(() => setSyncNotice(null), 5000);
    } catch (err: any) {
      alert(`Sync failed: ${err.message}`);
    } finally {
      setSyncing(false);
    }
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="w-2 h-2 rounded-full bg-cyan-400"></span>
            <span className="text-xs font-mono uppercase tracking-wider text-cyan-400">
              System Telemetry & Audit
            </span>
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Platform Health & Integrations</h1>
          <p className="text-xs text-slate-400 mt-1">
            Live diagnostic connectivity across database, ingestion workers, and regulatory feeds.
          </p>
        </div>

        <div className="flex items-center gap-2 self-start sm:self-auto">
          <button
            onClick={handleSyncNse}
            disabled={syncing}
            className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-lg border border-cyan-500/40 bg-cyan-950/40 hover:bg-cyan-900/60 text-xs font-mono text-cyan-300 transition-colors disabled:opacity-50"
            title="Trigger live sync against official NSE public portal"
          >
            <RotateCcw className={`w-3.5 h-3.5 ${syncing ? 'animate-spin' : ''}`} />
            {syncing ? 'Syncing NSE...' : 'Sync NSE Feed Now'}
          </button>
          <button
            onClick={fetchHealthData}
            disabled={loading}
            className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-lg border border-slate-700 bg-slate-850 hover:bg-slate-800 text-xs font-mono text-slate-300 transition-colors disabled:opacity-50"
          >
            <RotateCcw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {syncNotice && (
        <div className="p-3 rounded-lg border border-emerald-500/30 bg-emerald-950/20 text-emerald-400 text-xs font-mono">
          ✓ {syncNotice}
        </div>
      )}

      {error && (
        <div className="p-4 rounded-xl border border-rose-800/60 bg-rose-950/40 text-rose-300 text-xs flex items-center gap-3">
          <XCircle className="w-5 h-5 shrink-0 text-rose-400" />
          <span>{error}</span>
        </div>
      )}

      {/* Top Metric Strip */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          label="Database Status"
          value={status?.database_connected ? 'CONNECTED' : 'DISCONNECTED'}
          subtext="Relational ACID Engine"
          icon={<Database className="w-4 h-4" />}
          highlight={status?.database_connected}
        />
        <MetricCard
          label="Tracked Records"
          value={status?.total_ipos_tracked ?? 0}
          subtext={`${status?.demo_ipos_count ?? 0} marked demo / sandbox`}
          icon={<Server className="w-4 h-4" />}
        />
        <MetricCard
          label="Last Ingestion Job"
          value={status?.last_sync_status ?? 'NONE'}
          subtext={
            status?.last_successful_sync
              ? new Date(status.last_successful_sync).toLocaleTimeString('en-IN')
              : 'No completed sync'
          }
          icon={<Clock className="w-4 h-4" />}
        />
        <MetricCard
          label="Ingestion Errors (24h)"
          value={status?.recent_errors?.length ?? 0}
          subtext="Pipeline exceptions"
          icon={<AlertCircle className="w-4 h-4" />}
        />
      </div>

      {/* Regulatory Source Integrations Section */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 space-y-4">
        <div className="border-b border-slate-800/80 pb-3">
          <h2 className="text-sm font-mono uppercase tracking-wider text-slate-200 font-bold flex items-center gap-2">
            <Radio className="w-4 h-4 text-cyan-400" />
            Public Source Integrations & Lineage
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Zero fictitious green status reports. Unconnected sources are honestly marked as <strong>NOT CONFIGURED</strong>.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {status?.integrations?.map((integ, index) => (
            <div
              key={index}
              className="p-4 rounded-xl border border-slate-800 bg-slate-950/60 space-y-3"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="space-y-0.5">
                  <h3 className="text-xs font-bold text-slate-200">{integ.name}</h3>
                  <span className="text-[10px] font-mono text-slate-500 block">
                    Verified: {integ.verified ? 'YES' : 'PENDING CREDENTIALS'}
                  </span>
                </div>
                <StatusBadge status={integ.status} type="integration" />
              </div>

              <p className="text-xs text-slate-400 font-sans leading-relaxed">
                {integ.message}
              </p>

              <div className="pt-2 border-t border-slate-850 flex items-center justify-between text-[11px] font-mono text-slate-500">
                <span>Errors (24h): {integ.error_count_last_24h}</span>
                <span>
                  {integ.last_successful_sync
                    ? `Synced ${new Date(integ.last_successful_sync).toLocaleTimeString('en-IN')}`
                    : 'Awaiting setup'}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Background Ingestion Jobs Audit Log */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 space-y-4">
        <div className="border-b border-slate-800/80 pb-3">
          <h2 className="text-sm font-mono uppercase tracking-wider text-slate-200 font-bold flex items-center gap-2">
            <FileText className="w-4 h-4 text-indigo-400" />
            Recent Ingestion & Extraction Audit Log
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Historical audit log of scheduled discovery polls, document syncs, and Bhavcopy reconciliation jobs.
          </p>
        </div>

        {jobs.length === 0 ? (
          <div className="py-8 text-center text-xs font-mono text-slate-500">
            No historical ingestion jobs logged.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs font-mono border-collapse">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400 uppercase text-[11px]">
                  <th className="py-2.5 px-3 text-left">Job Type</th>
                  <th className="py-2.5 px-3 text-left">Source System</th>
                  <th className="py-2.5 px-3 text-left">Status</th>
                  <th className="py-2.5 px-3 text-right">Records</th>
                  <th className="py-2.5 px-3 text-left">Started At</th>
                  <th className="py-2.5 px-3 text-left">Details / Error</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {jobs.map((job) => (
                  <tr key={job.id} className="hover:bg-slate-800/30">
                    <td className="py-3 px-3 font-semibold text-slate-200">{job.job_type}</td>
                    <td className="py-3 px-3 text-slate-300">{job.source_system}</td>
                    <td className="py-3 px-3">
                      <span
                        className={`px-2 py-0.5 rounded text-[11px] font-bold ${
                          job.status === 'SUCCESS'
                            ? 'bg-emerald-950/80 text-emerald-300 border border-emerald-800/60'
                            : job.status === 'PARTIAL'
                            ? 'bg-amber-950/80 text-amber-300 border border-amber-800/60'
                            : 'bg-rose-950/80 text-rose-300 border border-rose-800/60'
                        }`}
                      >
                        {job.status}
                      </span>
                    </td>
                    <td className="py-3 px-3 text-right text-slate-200">{job.records_processed}</td>
                    <td className="py-3 px-3 text-slate-400">
                      {new Date(job.started_at).toLocaleString('en-IN', {
                        month: 'short',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </td>
                    <td className="py-3 px-3 text-slate-400 max-w-xs truncate">
                      {job.error_details || <span className="text-emerald-500">Normal execution</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
