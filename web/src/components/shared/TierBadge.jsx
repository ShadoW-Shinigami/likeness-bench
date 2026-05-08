import React from 'react';
import clsx from 'clsx';

const STYLES = {
  easy: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  medium: 'bg-amber-50 text-amber-700 border-amber-200',
  hard: 'bg-orange-50 text-orange-700 border-orange-200',
  extreme: 'bg-red-50 text-red-700 border-red-200',
  self: 'bg-blue-50 text-blue-700 border-blue-200',
};

export default function TierBadge({ tier, className }) {
  if (!tier) return null;
  return (
    <span className={clsx(
      'inline-flex items-center px-1.5 py-0.5 text-[10px] font-medium border rounded',
      STYLES[tier] ?? 'bg-gray-50 text-gray-600 border-gray-200',
      className,
    )}>
      {tier}
    </span>
  );
}
