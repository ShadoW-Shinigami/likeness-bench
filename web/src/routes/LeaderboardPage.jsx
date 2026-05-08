import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Info, Play } from 'lucide-react';
import { api } from '../utils/api.js';
import EmptyState from '../components/shared/EmptyState.jsx';
import CompanyLogo from '../components/shared/CompanyLogo.jsx';
import ProgressBar from '../components/shared/ProgressBar.jsx';

export default function LeaderboardPage() {
  const navigate = useNavigate();
  const { id } = useParams();
  const [benchmarks, setBenchmarks] = useState(null);
  const [activeId, setActiveId] = useState(id);
  const [index, setIndex] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showMethod, setShowMethod] = useState(false);

  useEffect(() => {
    api.benchmarks().then((d) => {
      setBenchmarks(d.benchmarks);
      const initial = id || d.default || d.benchmarks?.[0]?.id;
      setActiveId(initial);
    }).catch((e) => setError(String(e)));
  }, [id]);

  useEffect(() => {
    if (!activeId) return;
    setLoading(true);
    api.benchmarkIndex(activeId)
      .then((d) => { setIndex(d); setError(null); })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [activeId]);

  const rows = useMemo(() => index?.rows ?? [], [index]);
  const baselines = index?.baselines ?? [];

  return (
    <section className="max-w-5xl mx-auto px-6 py-10">
      <header className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-6">
        <div>
          <h1 className="text-xl sm:text-2xl font-semibold text-gray-900 tracking-tight">Likeness Benchmark</h1>
          <p className="text-sm text-gray-500 mt-1">
            VLMs pick the matching face out of 4 candidates + a "none of the above" option.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={activeId || ''}
            onChange={(e) => navigate(`/benchmark/${e.target.value}`)}
            className="text-xs px-2 py-1.5 border border-gray-200 rounded bg-white"
          >
            {benchmarks?.map((b) => (
              <option key={b.id} value={b.id}>
                {b.title} ({b.n_samples})
              </option>
            ))}
          </select>
          <button
            onClick={() => setShowMethod(true)}
            className="text-xs font-medium px-3 py-1.5 bg-gray-100 hover:bg-gray-200 rounded text-gray-700"
          >
            <Info size={12} className="inline mr-1" />
            Methodology
          </button>
        </div>
      </header>

      {showMethod && <MethodologyModal onClose={() => setShowMethod(false)} />}

      {loading && <EmptyState variant="loading" title="Loading leaderboard…" />}
      {error && <EmptyState variant="error" title="Error" description={error} />}

      {!loading && !error && rows.length === 0 && (
        <EmptyState
          variant="empty"
          title="No runs yet"
          description="Start a run from the Runs page or the CLI: bench eval --model mock --benchmark tiny_benchmark"
          action={
            <button onClick={() => navigate('/runs')}
              className="text-xs font-medium px-3 py-1.5 bg-black text-white rounded hover:bg-gray-800">
              <Play size={12} className="inline mr-1" />
              Open Runs
            </button>
          }
        />
      )}

      {rows.length > 0 && (
        <div className="border border-gray-200 rounded-lg overflow-hidden shadow-sm">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-gray-500 font-medium">
              <tr>
                <th className="px-4 py-3 w-12 text-center">#</th>
                <th className="px-4 py-3 text-left">Model</th>
                <th className="px-4 py-3 text-left w-1/3">Composite</th>
                <th className="px-4 py-3 text-right">Accuracy</th>
                <th className="px-4 py-3 text-right">Cost</th>
                <th className="px-4 py-3 text-right">Samples</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 bg-white">
              {rows.map((row, i) => (
                <tr key={row.run_id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-center text-gray-400 font-mono text-xs">{i + 1}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <CompanyLogo company={row.company} />
                      <div>
                        <div className="font-medium">{row.model_name}</div>
                        <div className="text-xs text-gray-500">{row.company}</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <span className="font-mono w-12 text-right">{(row.composite * 100).toFixed(1)}%</span>
                      <ProgressBar value={row.composite} max={1.0} />
                    </div>
                  </td>
                  <td className="px-4 py-3 text-right font-mono">{(row.accuracy * 100).toFixed(1)}%</td>
                  <td className="px-4 py-3 text-right text-gray-500 text-xs">${(row.cost_usd ?? 0).toFixed(2)}</td>
                  <td className="px-4 py-3 text-right text-gray-500 text-xs">{row.n_samples}</td>
                </tr>
              ))}
              {baselines.map((b) => (
                <tr key={b.label} className="bg-gray-50/50 text-gray-500">
                  <td className="px-4 py-3 text-center font-mono text-xs">·</td>
                  <td className="px-4 py-3 italic">{b.label}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <span className="font-mono w-12 text-right">{(b.composite * 100).toFixed(1)}%</span>
                      <ProgressBar value={b.composite} max={1.0} />
                    </div>
                  </td>
                  <td className="px-4 py-3 text-right text-gray-400">—</td>
                  <td className="px-4 py-3 text-right text-gray-400">—</td>
                  <td className="px-4 py-3 text-right text-gray-400">—</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function MethodologyModal({ onClose }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm p-4"
         onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-2xl border border-gray-100 max-w-lg p-6"
           onClick={(e) => e.stopPropagation()}>
        <h3 className="text-lg font-semibold mb-3 flex items-center gap-2">
          <Info size={16} /> Composite Likeness Score
        </h3>
        <div className="text-sm text-gray-600 leading-relaxed space-y-3">
          <p>
            Each item is a 5-option MCQ: 1 reference image, 4 face candidates, plus E ("none of the above").
            ~50% of items have the actual person among the candidates; ~50% don't.
          </p>
          <p>
            <strong>Composite</strong> = 0.5·acc<sub>present</sub> + 0.5·acc<sub>absent</sub>
            − 0.25·|FP<sub>E</sub> − FN<sub>E</sub>|.
            The penalty term punishes systematic over- or under-use of the abstention option.
          </p>
          <p className="text-xs text-gray-500">
            Distractors are calibrated by ArcFace cosine similarity to the reference; tiers easy / medium /
            hard / extreme.
          </p>
        </div>
        <button onClick={onClose}
          className="mt-4 text-xs font-medium px-3 py-1.5 bg-gray-100 hover:bg-gray-200 rounded">
          Close
        </button>
      </div>
    </div>
  );
}
