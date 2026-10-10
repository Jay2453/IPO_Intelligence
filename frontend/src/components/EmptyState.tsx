import React from 'react';
import { AlertCircle, FileQuestion, Info } from 'lucide-react';

interface EmptyStateProps {
  title: string;
  description: string;
  reason?: string;
  icon?: 'info' | 'question' | 'alert';
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title,
  description,
  reason,
  icon = 'question',
}) => {
  return (
    <div className="flex flex-col items-center justify-center p-8 rounded-lg border border-dashed border-slate-800 bg-slate-900/40 text-center">
      <div className="p-3 rounded-full bg-slate-800/80 text-slate-400 mb-3">
        {icon === 'question' && <FileQuestion className="w-6 h-6" />}
        {icon === 'info' && <Info className="w-6 h-6" />}
        {icon === 'alert' && <AlertCircle className="w-6 h-6" />}
      </div>
      <h4 className="text-sm font-semibold text-slate-200">{title}</h4>
      <p className="text-xs text-slate-400 mt-1 max-w-md">{description}</p>
      {reason && (
        <span className="mt-3 inline-block px-2.5 py-1 text-[11px] font-mono text-amber-300 bg-amber-950/40 border border-amber-800/60 rounded">
          Status: {reason}
        </span>
      )}
    </div>
  );
};
