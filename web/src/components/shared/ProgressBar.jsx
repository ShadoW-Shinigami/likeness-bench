import React from 'react';
import clsx from 'clsx';

export default function ProgressBar({ value, max = 1.0, className }) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  const color =
    pct > 80 ? 'bg-emerald-500'
    : pct > 50 ? 'bg-blue-500'
    : pct > 20 ? 'bg-amber-500'
    : 'bg-red-500';
  return (
    <div className={clsx('flex-1 h-2 bg-gray-100 rounded-full overflow-hidden max-w-[220px]', className)}>
      <div className={clsx('h-full rounded-full transition-all duration-700', color)}
           style={{ width: `${pct}%` }} />
    </div>
  );
}
