import React from 'react';

interface StatusBadgeProps {
  status: string;
  type?: 'lifecycle' | 'analysis' | 'integration';
  className?: string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  status,
  type = 'lifecycle',
  className = '',
}) => {
  let colorStyles = 'bg-slate-800 text-slate-300 border-slate-700';

  if (type === 'lifecycle') {
    switch (status) {
      case 'SUBSCRIPTION_OPEN':
        colorStyles = 'bg-emerald-950/60 text-emerald-300 border-emerald-500/40';
        break;
      case 'PRICE_BAND_AVAILABLE':
        colorStyles = 'bg-cyan-950/60 text-cyan-300 border-cyan-500/40';
        break;
      case 'PRELIMINARY_ANALYSIS':
        colorStyles = 'bg-sky-950/60 text-sky-300 border-sky-500/40';
        break;
      case 'DOCUMENTS_PENDING':
      case 'DISCOVERED':
        colorStyles = 'bg-slate-900 text-slate-400 border-slate-800';
        break;
      case 'SUBSCRIPTION_CLOSED':
      case 'FINAL_ANALYSIS':
        colorStyles = 'bg-indigo-950/60 text-indigo-300 border-indigo-500/40';
        break;
      case 'LISTED':
        colorStyles = 'bg-blue-950/60 text-blue-300 border-blue-500/40';
        break;
      case 'OUTCOME_VERIFIED':
        colorStyles = 'bg-teal-950/60 text-teal-300 border-teal-500/40';
        break;
      case 'WITHDRAWN':
      case 'POSTPONED':
        colorStyles = 'bg-rose-950/60 text-rose-300 border-rose-500/40';
        break;
    }
  } else if (type === 'integration') {
    switch (status) {
      case 'CONNECTED':
        colorStyles = 'bg-emerald-950/60 text-emerald-300 border-emerald-500/40';
        break;
      case 'NOT_CONFIGURED':
        colorStyles = 'bg-amber-950/60 text-amber-300 border-amber-500/40';
        break;
      case 'FAILED':
        colorStyles = 'bg-rose-950/60 text-rose-300 border-rose-500/40';
        break;
    }
  } else if (type === 'analysis') {
    switch (status) {
      case 'COMPLETED':
        colorStyles = 'bg-emerald-950/60 text-emerald-300 border-emerald-500/40';
        break;
      case 'IN_PROGRESS':
        colorStyles = 'bg-sky-950/60 text-sky-300 border-sky-500/40';
        break;
      case 'PENDING':
        colorStyles = 'bg-slate-900 text-slate-400 border-slate-800';
        break;
      case 'FAILED':
        colorStyles = 'bg-rose-950/60 text-rose-300 border-rose-500/40';
        break;
    }
  }

  const formatText = status.replace(/_/g, ' ');

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-medium border tracking-wide uppercase ${colorStyles} ${className}`}
    >
      {formatText}
    </span>
  );
};
