'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { Search, Filter, RotateCcw } from 'lucide-react';
import { api } from '@/lib/api';
import { IPOSummary } from '@/lib/types';
import { IpoTable } from '@/components/IpoTable';

export default function IpoRadarPage() {
  const [ipos, setIpos] = useState<IPOSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  
  // Filters & Sorting state
  const [search, setSearch] = useState('');
  const [exchange, setExchange] = useState('ALL');
  const [category, setCategory] = useState('ALL');
  const [lifecycleStatus, setLifecycleStatus] = useState('ALL');
  const [analysisStatus, setAnalysisStatus] = useState('ALL');
  const [sortBy, setSortBy] = useState('created_at');
  const [sortOrder, setSortOrder] = useState('desc');
  const [page, setPage] = useState(1);
  const pageSize = 15;

  const fetchIpos = useCallback(async () => {
    try {
      setLoading(true);
      const res = await api.getIpos({
        exchange: exchange === 'ALL' ? undefined : exchange,
        category: category === 'ALL' ? undefined : category,
        lifecycle_status: lifecycleStatus === 'ALL' ? undefined : lifecycleStatus,
        analysis_status: analysisStatus === 'ALL' ? undefined : analysisStatus,
        search: search.trim() || undefined,
        sort_by: sortBy,
        sort_order: sortOrder,
        page,
        page_size: pageSize,
      });
      setIpos(res.items);
      setTotal(res.total);
    } catch (err) {
      console.error('Failed to fetch IPOs for radar:', err);
    } finally {
      setLoading(false);
    }
  }, [exchange, category, lifecycleStatus, analysisStatus, search, sortBy, sortOrder, page]);

  useEffect(() => {
    fetchIpos();
  }, [fetchIpos]);

  const handleSort = (field: string) => {
    if (sortBy === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setSortOrder('desc');
    }
    setPage(1);
  };

  const handleResetFilters = () => {
    setSearch('');
    setExchange('ALL');
    setCategory('ALL');
    setLifecycleStatus('ALL');
    setAnalysisStatus('ALL');
    setSortBy('created_at');
    setSortOrder('desc');
    setPage(1);
  };

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="w-2 h-2 rounded-full bg-cyan-400"></span>
            <span className="text-xs font-mono uppercase tracking-wider text-cyan-400">
              Live Regulatory Stream
            </span>
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight">IPO Radar</h1>
          <p className="text-xs text-slate-400 mt-1">
            Comprehensive directory of tracked Mainboard & SME offerings across NSE and BSE.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <span className="text-xs font-mono text-slate-400">
            Showing <strong className="text-slate-200">{ipos.length}</strong> of{' '}
            <strong className="text-slate-200">{total}</strong> issues
          </span>
          <button
            onClick={handleResetFilters}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-700 bg-slate-850 hover:bg-slate-800 text-xs font-medium text-slate-300 transition-colors"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            Reset Filters
          </button>
        </div>
      </div>

      {/* Search & Filter Toolbar */}
      <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/60 backdrop-blur-sm grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
        {/* Search */}
        <div className="relative sm:col-span-2 lg:col-span-1">
          <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search company or ticker..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            className="w-full pl-9 pr-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500 transition-colors"
          />
        </div>

        {/* Exchange Filter */}
        <div>
          <select
            value={exchange}
            onChange={(e) => {
              setExchange(e.target.value);
              setPage(1);
            }}
            className="w-full py-2 px-3 rounded-lg bg-slate-950 border border-slate-800 text-xs text-slate-300 focus:outline-none focus:border-cyan-500 font-mono"
          >
            <option value="ALL">All Exchanges</option>
            <option value="NSE_BSE">NSE & BSE</option>
            <option value="NSE">NSE Only</option>
            <option value="BSE">BSE Only</option>
          </select>
        </div>

        {/* Category Filter */}
        <div>
          <select
            value={category}
            onChange={(e) => {
              setCategory(e.target.value);
              setPage(1);
            }}
            className="w-full py-2 px-3 rounded-lg bg-slate-950 border border-slate-800 text-xs text-slate-300 focus:outline-none focus:border-cyan-500 font-mono"
          >
            <option value="ALL">All Categories</option>
            <option value="MAINBOARD">Mainboard</option>
            <option value="SME">SME Emerge / SME</option>
          </select>
        </div>

        {/* Lifecycle Status Filter */}
        <div>
          <select
            value={lifecycleStatus}
            onChange={(e) => {
              setLifecycleStatus(e.target.value);
              setPage(1);
            }}
            className="w-full py-2 px-3 rounded-lg bg-slate-950 border border-slate-800 text-xs text-slate-300 focus:outline-none focus:border-cyan-500 font-mono"
          >
            <option value="ALL">All Lifecycle States</option>
            <option value="DISCOVERED">Discovered</option>
            <option value="DOCUMENTS_PENDING">Documents Pending</option>
            <option value="PRELIMINARY_ANALYSIS">Preliminary Analysis</option>
            <option value="PRICE_BAND_AVAILABLE">Price Band Available</option>
            <option value="SUBSCRIPTION_OPEN">Subscription Open</option>
            <option value="SUBSCRIPTION_CLOSED">Subscription Closed</option>
            <option value="FINAL_ANALYSIS">Final Analysis</option>
            <option value="LISTED">Listed</option>
            <option value="OUTCOME_VERIFIED">Outcome Verified</option>
            <option value="WITHDRAWN">Withdrawn</option>
          </select>
        </div>

        {/* Analysis Status Filter */}
        <div>
          <select
            value={analysisStatus}
            onChange={(e) => {
              setAnalysisStatus(e.target.value);
              setPage(1);
            }}
            className="w-full py-2 px-3 rounded-lg bg-slate-950 border border-slate-800 text-xs text-slate-300 focus:outline-none focus:border-cyan-500 font-mono"
          >
            <option value="ALL">All Analysis States</option>
            <option value="COMPLETED">Analysis Completed</option>
            <option value="IN_PROGRESS">Analysis In Progress</option>
            <option value="PENDING">Pending Data</option>
            <option value="FAILED">Analysis Failed</option>
          </select>
        </div>
      </div>

      {/* Main Table */}
      <IpoTable
        ipos={ipos}
        sortBy={sortBy}
        sortOrder={sortOrder}
        onSort={handleSort}
        isLoading={loading}
      />

      {/* Pagination Bar */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between border-t border-slate-800 pt-4">
          <span className="text-xs font-mono text-slate-400">
            Page {page} of {totalPages}
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="px-3 py-1.5 rounded-lg border border-slate-800 bg-slate-900 text-xs font-mono text-slate-300 hover:bg-slate-800 disabled:opacity-40 transition-colors"
            >
              Previous
            </button>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="px-3 py-1.5 rounded-lg border border-slate-800 bg-slate-900 text-xs font-mono text-slate-300 hover:bg-slate-800 disabled:opacity-40 transition-colors"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
