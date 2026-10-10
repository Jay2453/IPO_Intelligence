'use client';

import React from 'react';
import Link from 'next/link';
import { ChevronDown, ChevronUp, ExternalLink, ShieldCheck } from 'lucide-react';
import { IPOSummary } from '@/lib/types';
import { StatusBadge } from './StatusBadge';
import { DemoBadge } from './DemoBadge';

interface IpoTableProps {
  ipos: IPOSummary[];
  sortBy?: string;
  sortOrder?: string;
  onSort?: (field: string) => void;
  isLoading?: boolean;
}

export const IpoTable: React.FC<IpoTableProps> = ({
  ipos,
  sortBy = 'created_at',
  sortOrder = 'desc',
  onSort,
  isLoading = false,
}) => {
  const renderSortIndicator = (field: string) => {
    if (sortBy !== field) return null;
    return sortOrder === 'asc' ? (
      <ChevronUp className="w-3.5 h-3.5 text-cyan-400 inline ml-1" />
    ) : (
      <ChevronDown className="w-3.5 h-3.5 text-cyan-400 inline ml-1" />
    );
  };

  const handleHeaderClick = (field: string) => {
    if (onSort) onSort(field);
  };

  const formatPriceBand = (min?: number | null, max?: number | null) => {
    if (min && max) {
      return `₹${min.toLocaleString()} - ₹${max.toLocaleString()}`;
    }
    if (max) return `₹${max.toLocaleString()}`;
    return <span className="text-slate-500 italic font-mono text-xs">Unspecified</span>;
  };

  const formatIssueDates = (open?: string | null, close?: string | null) => {
    if (open && close) {
      return (
        <span className="font-mono text-xs text-slate-300">
          {new Date(open).toLocaleDateString('en-IN', { month: 'short', day: 'numeric' })} –{' '}
          {new Date(close).toLocaleDateString('en-IN', { month: 'short', day: 'numeric' })}
        </span>
      );
    }
    if (open) {
      return (
        <span className="font-mono text-xs text-slate-300">
          Opens {new Date(open).toLocaleDateString('en-IN', { month: 'short', day: 'numeric' })}
        </span>
      );
    }
    return <span className="text-slate-500 italic font-mono text-xs">Pending RHP</span>;
  };

  return (
    <div className="w-full overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/60 shadow-xl backdrop-blur-sm">
      <table className="w-full text-left text-xs border-collapse">
        <thead>
          <tr className="border-b border-slate-800 bg-slate-950/80 text-slate-400 font-mono uppercase tracking-wider text-[11px]">
            <th
              onClick={() => handleHeaderClick('company_name')}
              className="py-3.5 px-4 cursor-pointer hover:text-slate-200 transition-colors"
            >
              Company {renderSortIndicator('company_name')}
            </th>
            <th
              onClick={() => handleHeaderClick('exchange')}
              className="py-3.5 px-3 cursor-pointer hover:text-slate-200 transition-colors"
            >
              Exchange {renderSortIndicator('exchange')}
            </th>
            <th
              onClick={() => handleHeaderClick('category')}
              className="py-3.5 px-3 cursor-pointer hover:text-slate-200 transition-colors"
            >
              Category {renderSortIndicator('category')}
            </th>
            <th
              onClick={() => handleHeaderClick('open_date')}
              className="py-3.5 px-3 cursor-pointer hover:text-slate-200 transition-colors"
            >
              Issue Dates {renderSortIndicator('open_date')}
            </th>
            <th
              onClick={() => handleHeaderClick('max_price')}
              className="py-3.5 px-3 cursor-pointer hover:text-slate-200 transition-colors"
            >
              Price Band {renderSortIndicator('max_price')}
            </th>
            <th
              onClick={() => handleHeaderClick('issue_size_crores')}
              className="py-3.5 px-3 cursor-pointer hover:text-slate-200 transition-colors"
            >
              Issue Size {renderSortIndicator('issue_size_crores')}
            </th>
            <th
              onClick={() => handleHeaderClick('lifecycle_status')}
              className="py-3.5 px-3 cursor-pointer hover:text-slate-200 transition-colors"
            >
              Lifecycle Status {renderSortIndicator('lifecycle_status')}
            </th>
            <th
              onClick={() => handleHeaderClick('data_completeness_pct')}
              className="py-3.5 px-3 cursor-pointer hover:text-slate-200 transition-colors"
            >
              Completeness {renderSortIndicator('data_completeness_pct')}
            </th>
            <th className="py-3.5 px-3">Analysis</th>
            <th className="py-3.5 px-4 text-right">Action</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800/60 font-sans">
          {isLoading ? (
            <tr>
              <td colSpan={10} className="py-12 text-center text-slate-400 font-mono">
                <div className="inline-block animate-spin mr-2">◒</div> Loading IPO intelligence database...
              </td>
            </tr>
          ) : ipos.length === 0 ? (
            <tr>
              <td colSpan={10} className="py-12 text-center text-slate-500 font-mono">
                No IPO records match the selected filter criteria.
              </td>
            </tr>
          ) : (
            ipos.map((ipo) => (
              <tr
                key={ipo.id}
                className="hover:bg-slate-800/40 transition-colors group"
              >
                {/* Company & Symbol */}
                <td className="py-3.5 px-4">
                  <div className="flex flex-col">
                    <div className="flex items-center gap-2">
                      <Link
                        href={`/ipo/${ipo.id}`}
                        className="font-medium text-slate-100 hover:text-cyan-400 text-sm transition-colors"
                      >
                        {ipo.company_name}
                      </Link>
                      {ipo.is_demo && <DemoBadge size="sm" />}
                    </div>
                    {ipo.symbol ? (
                      <span className="font-mono text-[11px] text-slate-400 mt-0.5">
                        NSE/BSE: {ipo.symbol}
                      </span>
                    ) : (
                      <span className="font-mono text-[11px] text-slate-500 italic mt-0.5">
                        Ticker unassigned
                      </span>
                    )}
                  </div>
                </td>

                {/* Exchange */}
                <td className="py-3.5 px-3 font-mono text-slate-300">
                  <span className="px-2 py-0.5 rounded bg-slate-800 border border-slate-700 text-[11px]">
                    {ipo.exchange.replace('_', ' & ')}
                  </span>
                </td>

                {/* Category */}
                <td className="py-3.5 px-3 font-mono text-slate-300">
                  <span
                    className={`px-2 py-0.5 rounded text-[11px] ${
                      ipo.category === 'SME'
                        ? 'bg-purple-950/60 text-purple-300 border border-purple-800/60'
                        : 'bg-slate-800 text-slate-300 border border-slate-700'
                    }`}
                  >
                    {ipo.category}
                  </span>
                </td>

                {/* Issue Dates */}
                <td className="py-3.5 px-3">
                  {formatIssueDates(ipo.open_date, ipo.close_date)}
                </td>

                {/* Price Band */}
                <td className="py-3.5 px-3 font-mono text-slate-200">
                  {formatPriceBand(ipo.min_price, ipo.max_price)}
                </td>

                {/* Issue Size */}
                <td className="py-3.5 px-3 font-mono text-slate-200">
                  {ipo.issue_size_crores !== null && ipo.issue_size_crores !== undefined ? (
                    <span>₹{ipo.issue_size_crores.toLocaleString()} Cr</span>
                  ) : (
                    <span className="text-slate-500 italic text-xs">Awaiting DRHP</span>
                  )}
                </td>

                {/* Lifecycle Status */}
                <td className="py-3.5 px-3">
                  <StatusBadge status={ipo.lifecycle_status} type="lifecycle" />
                </td>

                {/* Data Completeness */}
                <td className="py-3.5 px-3">
                  <div className="flex items-center gap-2">
                    <div className="w-16 bg-slate-800 rounded-full h-1.5 overflow-hidden">
                      <div
                        className={`h-full rounded-full ${
                          ipo.data_completeness_pct >= 80
                            ? 'bg-emerald-400'
                            : ipo.data_completeness_pct >= 50
                            ? 'bg-amber-400'
                            : 'bg-rose-400'
                        }`}
                        style={{ width: `${ipo.data_completeness_pct}%` }}
                      />
                    </div>
                    <span className="font-mono text-[11px] text-slate-400">
                      {ipo.data_completeness_pct}%
                    </span>
                  </div>
                </td>

                {/* Analysis Status */}
                <td className="py-3.5 px-3">
                  <StatusBadge status={ipo.analysis_status} type="analysis" />
                </td>

                {/* Action Link */}
                <td className="py-3.5 px-4 text-right">
                  <Link
                    href={`/ipo/${ipo.id}`}
                    className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 hover:text-cyan-400 border border-slate-700 text-xs font-medium transition-colors"
                  >
                    Deep Dive
                    <ExternalLink className="w-3 h-3" />
                  </Link>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
};
