import React from 'react';

interface DemoBadgeProps {
  className?: string;
  size?: 'sm' | 'md';
}

export const DemoBadge: React.FC<DemoBadgeProps> = ({ className = '', size = 'sm' }) => {
  const sizeClasses = size === 'sm' ? 'text-[10px] px-1.5 py-0.5' : 'text-xs px-2 py-1';
  return (
    <span
      className={`inline-flex items-center gap-1 font-semibold uppercase tracking-wider rounded border border-amber-500/40 bg-amber-500/10 text-amber-400 font-mono shadow-sm ${sizeClasses} ${className}`}
      title="This is demonstration data. Not verified live market observation."
    >
      <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse"></span>
      DEMO DATA
    </span>
  );
};
