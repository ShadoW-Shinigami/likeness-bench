import React, { useState } from 'react';
import clsx from 'clsx';

export default function ImageWithSkeleton({ src, alt, className, imgClassName }) {
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState(false);
  return (
    <div className={clsx('relative bg-gray-100 overflow-hidden', className)}>
      {!loaded && !error && <div className="absolute inset-0 bg-gray-200 skeleton" />}
      {error && (
        <div className="absolute inset-0 flex items-center justify-center text-xs text-gray-400">
          image error
        </div>
      )}
      <img
        src={src}
        alt={alt || ''}
        loading="lazy"
        onLoad={() => setLoaded(true)}
        onError={() => setError(true)}
        className={clsx(
          'w-full h-full object-cover transition-opacity duration-300',
          loaded ? 'opacity-100' : 'opacity-0',
          imgClassName,
        )}
      />
    </div>
  );
}
