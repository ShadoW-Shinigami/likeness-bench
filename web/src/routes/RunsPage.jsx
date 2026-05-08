import React, { useEffect, useState } from 'react';
import { Pause, Play, Square, RotateCcw, Plus, Sparkles, FileText } from 'lucide-react';
import clsx from 'clsx';
import { api } from '../utils/api.js';
import EmptyState from '../components/shared/EmptyState.jsx';

const STATUS_STYLES = {
  running: 'bg-blue-100 text-blue-700',
  queued: 'bg-gray-100 text-gray-600',
  paused: 'bg-amber-100 text-amber-700',
  completed: 'bg-emerald-100 text-emerald-700',
  failed: 'bg-red-100 text-red-700',
  killed: 'bg-red-50 text-red-600',
};

export default function RunsPage() {
  const [runs, setRuns] = useState([]);
  const [models, setModels] = useState([]);
  const [benchmarks, setBenchmarks] = useState([]);
  const [showStart, setShowStart] = useState(false);
  const [error, setError] = useState(null);
  const [showcase, setShowcase] = useState(null);

  const refresh = () => api.runs().then((d) => setRuns(d.runs)).catch((e) => setError(String(e)));
  const refreshShowcase = () => api.showcaseStatus().then(setShowcase).catch(() => {});

  useEffect(() => {
    refresh();
    refreshShowcase();
    const t = setInterval(() => { refresh(); refreshShowcase(); }, 1500);
    api.models().then((d) => setModels(d.models));
    api.benchmarks().then((d) => setBenchmarks(d.benchmarks));
    return () => clearInterval(t);
  }, []);

  const buildShowcase = async () => {
    try { await api.showcaseBuild(); refreshShowcase(); }
    catch (e) { setError(String(e)); }
  };

  if (error) return <EmptyState variant="error" title="Error" description={error} />;

  return (
    <section className="max-w-6xl mx-auto px-6 py-10">
      <div className="flex items-end justify-between mb-6 gap-3 flex-wrap">
        <div>
          <h1 className="text-xl sm:text-2xl font-semibold tracking-tight">Runs</h1>
          <p className="text-sm text-gray-500 mt-1">Live evaluation runs. Pause, resume, or kill in flight.</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={buildShowcase}
            disabled={showcase?.status === 'running'}
            className="text-sm font-medium px-3 py-1.5 bg-white border border-gray-200 hover:bg-gray-50 rounded inline-flex items-center gap-1.5 disabled:opacity-50"
            title={showcase?.modified_at ? `Last built: ${new Date(showcase.modified_at*1000).toLocaleString()}` : 'never'}
          >
            <Sparkles size={14} className={showcase?.status === 'running' ? 'animate-pulse text-fuchsia-500' : ''} />
            {showcase?.status === 'running' ? 'Rebuilding…' : 'Rebuild showcase'}
          </button>
          {showcase?.exists && (
            <a href={api.showcaseUrl()} target="_blank" rel="noreferrer"
               className="text-sm font-medium px-3 py-1.5 bg-white border border-gray-200 hover:bg-gray-50 rounded inline-flex items-center gap-1.5">
              <FileText size={14} /> Open
            </a>
          )}
          <button
            onClick={() => setShowStart(true)}
            className="text-sm font-medium px-3 py-1.5 bg-black text-white rounded hover:bg-gray-800 inline-flex items-center gap-1"
          >
            <Plus size={14} /> Start run
          </button>
        </div>
      </div>

      {showStart && (
        <StartRunDialog
          models={models}
          benchmarks={benchmarks}
          onClose={() => setShowStart(false)}
          onStarted={() => { setShowStart(false); refresh(); }}
        />
      )}

      {runs.length === 0 ? (
        <EmptyState
          variant="empty"
          title="No runs yet"
          description="Click 'Start run' or use the CLI: bench eval --model mock --benchmark tiny_benchmark"
        />
      ) : (
        <div className="border border-gray-200 rounded-lg overflow-hidden shadow-sm">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-gray-500">
              <tr>
                <th className="px-4 py-3 text-left">Run ID</th>
                <th className="px-4 py-3 text-left">Status</th>
                <th className="px-4 py-3 text-left">Model</th>
                <th className="px-4 py-3 text-left">Benchmark</th>
                <th className="px-4 py-3 text-left">Progress</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 bg-white">
              {runs.map((r) => (
                <RunRow key={r.run_id} run={r} onChange={refresh} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function RunRow({ run, onChange }) {
  const pct = run.n_samples ? Math.round((run.completed / run.n_samples) * 100) : 0;
  const active = run.status === 'running' || run.status === 'paused' || run.status === 'queued';
  return (
    <tr className="hover:bg-gray-50">
      <td className="px-4 py-3 font-mono text-xs text-gray-700">{run.run_id}</td>
      <td className="px-4 py-3">
        <span className={clsx('px-2 py-0.5 rounded text-xs font-medium', STATUS_STYLES[run.status])}>
          {run.status}
        </span>
      </td>
      <td className="px-4 py-3">{run.model_id}</td>
      <td className="px-4 py-3 text-gray-500 text-xs">{run.benchmark_id}</td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-2">
          <div className="flex-1 h-1.5 bg-gray-100 rounded overflow-hidden max-w-[180px]">
            <div className="h-full bg-blue-500 transition-all duration-500"
                 style={{ width: `${pct}%` }} />
          </div>
          <span className="text-xs text-gray-500 font-mono">{run.completed}/{run.n_samples}</span>
        </div>
      </td>
      <td className="px-4 py-3 text-right">
        <div className="inline-flex items-center gap-1">
          {active && run.status !== 'paused' && (
            <button title="Pause" onClick={() => api.pauseRun(run.run_id).then(onChange)}
              className="p-1.5 rounded hover:bg-amber-100 text-amber-700">
              <Pause size={14} />
            </button>
          )}
          {run.status === 'paused' && (
            <button title="Resume" onClick={() => api.resumeRun(run.run_id).then(onChange)}
              className="p-1.5 rounded hover:bg-emerald-100 text-emerald-700">
              <Play size={14} />
            </button>
          )}
          {(run.status === 'killed' || run.status === 'failed') && (
            <button title="Continue" onClick={async () => {
              await api.startRun({ model: run.model_id, benchmark: run.benchmark_id, resume: true });
              onChange();
            }} className="p-1.5 rounded hover:bg-blue-100 text-blue-700">
              <RotateCcw size={14} />
            </button>
          )}
          {active && (
            <button title="Kill" onClick={() => api.killRun(run.run_id).then(onChange)}
              className="p-1.5 rounded hover:bg-red-100 text-red-600">
              <Square size={14} />
            </button>
          )}
        </div>
      </td>
    </tr>
  );
}

function StartRunDialog({ models, benchmarks, onClose, onStarted }) {
  const [model, setModel] = useState(models[0]?.key || 'mock');
  const [bench, setBench] = useState(benchmarks[0]?.id || 'tiny_benchmark');
  const [concurrency, setConcurrency] = useState(4);
  const [maxCost, setMaxCost] = useState(5);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  useEffect(() => { setModel(models[0]?.key || 'mock'); }, [models]);
  useEffect(() => { setBench(benchmarks[0]?.id || 'tiny_benchmark'); }, [benchmarks]);

  const submit = async () => {
    setBusy(true); setErr(null);
    try {
      await api.startRun({
        model, benchmark: bench, concurrency: Number(concurrency), max_cost_usd: Number(maxCost),
      });
      onStarted();
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm p-4"
         onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-2xl border border-gray-100 max-w-md w-full p-6"
           onClick={(e) => e.stopPropagation()}>
        <h3 className="text-lg font-semibold mb-4">Start a new run</h3>
        <div className="space-y-3">
          <Field label="Model">
            <select value={model} onChange={(e) => setModel(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-200 rounded text-sm">
              {models.map((m) => (
                <option key={m.key} value={m.key} disabled={!m.configured}>
                  {m.display} {!m.configured && '(no API key)'}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Benchmark">
            <select value={bench} onChange={(e) => setBench(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-200 rounded text-sm">
              {benchmarks.map((b) => (
                <option key={b.id} value={b.id}>{b.title} ({b.n_samples})</option>
              ))}
            </select>
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Concurrency">
              <input type="number" min={1} max={32} value={concurrency}
                     onChange={(e) => setConcurrency(e.target.value)}
                     className="w-full px-3 py-2 border border-gray-200 rounded text-sm" />
            </Field>
            <Field label="Max cost ($)">
              <input type="number" min={0} step={0.5} value={maxCost}
                     onChange={(e) => setMaxCost(e.target.value)}
                     className="w-full px-3 py-2 border border-gray-200 rounded text-sm" />
            </Field>
          </div>
          {err && <p className="text-xs text-red-600">{err}</p>}
        </div>
        <div className="mt-6 flex justify-end gap-2">
          <button onClick={onClose} className="text-sm px-3 py-1.5 bg-gray-100 hover:bg-gray-200 rounded">
            Cancel
          </button>
          <button onClick={submit} disabled={busy}
                  className="text-sm px-3 py-1.5 bg-black text-white rounded hover:bg-gray-800 disabled:opacity-50">
            {busy ? 'Starting…' : 'Start'}
          </button>
        </div>
      </div>
    </div>
  );
}

function Field({ label, children }) {
  return (
    <label className="block">
      <span className="text-xs font-medium text-gray-700">{label}</span>
      <div className="mt-1">{children}</div>
    </label>
  );
}
