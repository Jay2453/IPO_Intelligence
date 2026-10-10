import React from 'react';

interface MetricCardProps {
  label: string;
  value: string | number | null | undefined;
  subtext?: string;
  icon?: React.ReactNode;
  trend?: 'up' | 'down' | 'neutral';
  highlight?: boolean;
}

export const MetricCard: React.FC<MetricCardProps> = ({
  label,
  value,
  subtext,
  icon,
  trend,
  highlight,
}) => {
  const isAvailable = value !== null && value !== undefined && value !== '';

  return (
    <div
      className={`p-4 rounded-xl border transition-all ${
        highlight
          ? 'bg-slate-900 border-indigo-500/40 shadow-lg shadow-indigo-950/20'
          : 'bg-slate-900/80 border-slate-800/80 hover:border-slate-700'
      }`}
    >
      <div className="flex items-center justify-between text-slate-400 mb-2">
        <span className="text-xs font-medium tracking-wide uppercase">{label}</span>
        {icon && <div className="text-slate-400">{icon}</div>}
      </div>

      <div className="flex items-baseline gap-2">
        {isAvailable ? (
          <div
            className={`text-xl font-bold font-mono tracking-tight ${
              highlight ? 'text-white' : 'text-slate-100'
            }`}
          >
            {value}
          </div>
        ) : (
          <div className="text-sm font-mono text-slate-500 italic">Unavailable</div>
        )}

        {trend === 'up' && <span className="text-xs text-emerald-400 font-semibold font-mono">▲</span>}
        {trend === 'down' && <span className="text-xs text-rose-400 font-semibold font-mono">▼</span>}
      </div>

      {subtext && <div className="text-xs text-slate-400 mt-1 font-sans">{subtext}</div>}
    </div>
  );
};
