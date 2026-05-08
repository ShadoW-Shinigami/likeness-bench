import React, { useEffect, useState } from 'react';
import { api } from '../utils/api.js';
import EmptyState from '../components/shared/EmptyState.jsx';
import TierBadge from '../components/shared/TierBadge.jsx';
import ImageWithSkeleton from '../components/shared/ImageWithSkeleton.jsx';

export default function SamplesPage() {
  const [benchmarks, setBenchmarks] = useState([]);
  const [bench, setBench] = useState(null);
  const [samples, setSamples] = useState([]);
  const [filter, setFilter] = useState('all');
  const [error, setError] = useState(null);

  useEffect(() => {
    api.benchmarks().then((d) => {
      setBenchmarks(d.benchmarks);
      setBench(d.default || d.benchmarks?.[0]?.id);
    }).catch((e) => setError(String(e)));
  }, []);
  useEffect(() => {
    if (!bench) return;
    api.samples(bench).then((d) => setSamples(d.samples)).catch((e) => setError(String(e)));
  }, [bench]);

  const visible = samples.filter((s) =>
    filter === 'all' ? true :
    filter === 'present' ? s.presence === 'correct_present' :
    filter === 'absent' ? s.presence === 'correct_absent' : true
  );

  if (error) return <EmptyState variant="error" title="Error" description={error} />;

  return (
    <section className="max-w-6xl mx-auto px-6 py-10">
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3 mb-6">
        <div>
          <h1 className="text-xl sm:text-2xl font-semibold tracking-tight">Samples</h1>
          <p className="text-sm text-gray-500 mt-1">{visible.length} of {samples.length} items</p>
        </div>
        <div className="flex items-center gap-2">
          <select value={bench || ''} onChange={(e) => setBench(e.target.value)}
                  className="text-xs px-2 py-1.5 border border-gray-200 rounded bg-white">
            {benchmarks.map((b) => <option key={b.id} value={b.id}>{b.title}</option>)}
          </select>
          {['all', 'present', 'absent'].map((k) => (
            <button key={k} onClick={() => setFilter(k)}
              className={`text-xs px-2 py-1 rounded border ${filter === k ? 'bg-black text-white border-black' : 'bg-white border-gray-200 text-gray-600'}`}>
              {k}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
        {visible.map((s) => (
          <div key={s.id} className="rounded-lg border border-gray-200 bg-white overflow-hidden">
            <ImageWithSkeleton
              src={api.imageUrl(bench, s.id, 'base.png')}
              alt={s.id}
              className="aspect-square"
            />
            <div className="p-2 flex items-center justify-between">
              <span className="text-xs font-mono text-gray-500">{s.id}</span>
              <div className="flex items-center gap-1">
                <TierBadge tier={s.tier} />
                {s.presence === 'correct_absent' && (
                  <span className="text-[10px] px-1 py-0.5 rounded bg-purple-50 text-purple-600 border border-purple-100">E</span>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
