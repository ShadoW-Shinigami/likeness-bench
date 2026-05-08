import React from 'react';
import { AlertCircle, Inbox, Loader2 } from 'lucide-react';

export default function EmptyState({ variant = 'empty', title, description, action }) {
  const Icon = variant === 'loading' ? Loader2 : variant === 'error' ? AlertCircle : Inbox;
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <Icon
        size={28}
        className={`mb-3 ${variant === 'loading' ? 'animate-spin text-gray-400' : 'text-gray-300'}`}
      />
      <p className="text-sm font-medium text-gray-700">{title}</p>
      {description && <p className="mt-1 text-xs text-gray-500 max-w-md">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
