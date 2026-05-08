import React from 'react';
import clsx from 'clsx';

export default function CompanyLogo({ company, className }) {
  const initials = (company || '??').slice(0, 2).toUpperCase();
  return (
    <div className={clsx(
      'w-8 h-8 rounded border bg-gray-50 border-gray-100 text-gray-700 flex items-center justify-center text-[10px] font-semibold tracking-wider',
      className,
    )}>
      {initials}
    </div>
  );
}
