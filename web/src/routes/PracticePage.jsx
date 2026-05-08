import React, { useEffect, useState, useCallback } from 'react';
import { ArrowRight, RotateCcw } from 'lucide-react';
import { api } from '../utils/api.js';
import MCQViewer from '../components/mcq/MCQViewer.jsx';
import EmptyState from '../components/shared/EmptyState.jsx';

export default function PracticePage() {
  const [benchmarks, setBenchmarks] = useState([]);
  const [bench, setBench] = useState(null);
  const [samples, setSamples] = useState([]);
  const [seenIds, setSeenIds] = useState([]);
  const [current, setCurrent] = useState(null);
  const [selected, setSelected] = useState(null);
  const [revealed, setRevealed] = useState(false);
  const [score, setScore] = useState({ correct: 0, total: 0, streak: 0 });
  const [error, setError] = useState(null);

  useEffect(() => {
    api.benchmarks().then((d) => {
      setBenchmarks(d.benchmarks);
      const initial = d.default || d.benchmarks?.[0]?.id;
      setBench(initial);
    }).catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    if (!bench) return;
    api.samples(bench)
      .then((d) => { setSamples(d.samples); setSeenIds([]); })
      .catch((e) => setError(String(e)));
  }, [bench]);

  const pickNext = useCallback(() => {
    if (!samples.length) return;
    const remaining = samples.filter((s) => !seenIds.includes(s.id));
    const pool = remaining.length ? remaining : samples;
    const next = pool[Math.floor(Math.random() * pool.length)];
    setSelected(null);
    setRevealed(false);
    api.sampleMeta(bench, next.id).then(setCurrent).catch((e) => setError(String(e)));
  }, [samples, seenIds, bench]);

  useEffect(() => { if (samples.length && !current) pickNext(); }, [samples, current, pickNext]);

  const onSelect = (letter) => {
    if (revealed || !current) return;
    setSelected(letter);
    setRevealed(true);
    const correct = letter === current.correct_answer;
    setScore((s) => ({
      correct: s.correct + (correct ? 1 : 0),
      total: s.total + 1,
      streak: correct ? s.streak + 1 : 0,
    }));
    setSeenIds((ids) => [...ids, current.id]);
  };

  const next = () => { setCurrent(null); pickNext(); };

  // Keyboard shortcuts: 1-5 select, n next, r reset
  useEffect(() => {
    const map = { '1': 'A', '2': 'B', '3': 'C', '4': 'D', '5': 'E', a: 'A', b: 'B', c: 'C', d: 'D', e: 'E' };
    const handler = (ev) => {
      const k = ev.key.toLowerCase();
      if (map[k]) onSelect(map[k]);
      else if (k === 'n' && revealed) next();
      else if (k === 'r') {
        setScore({ correct: 0, total: 0, streak: 0 });
        setSeenIds([]);
        next();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  });

  if (error) return <EmptyState variant="error" title="Error" description={error} />;

  return (
    <section className="max-w-5xl mx-auto px-6 py-10">
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3 mb-6">
        <div>
          <h1 className="text-xl sm:text-2xl font-semibold tracking-tight">Practice Arena</h1>
          <p className="text-sm text-gray-500 mt-1">Try the benchmark yourself. Press 1–5 to choose.</p>
        </div>
        <div className="flex items-center gap-4">
          <select value={bench || ''} onChange={(e) => setBench(e.target.value)}
                  className="text-xs px-2 py-1.5 border border-gray-200 rounded bg-white">
            {benchmarks.map((b) => <option key={b.id} value={b.id}>{b.title}</option>)}
          </select>
          <Stat label="Score" value={`${score.correct}/${score.total}`} />
          <Stat label="Streak" value={score.streak} />
          <Stat label="Accuracy" value={score.total ? `${Math.round((score.correct / score.total) * 100)}%` : '—'} />
        </div>
      </div>

      {!current ? (
        <EmptyState variant="loading" title="Loading sample…" />
      ) : (
        <div className="rounded-3xl border border-gray-100 bg-gray-50/50 p-6">
          <MCQViewer
            benchmarkId={bench}
            sample={current}
            selected={selected}
            revealed={revealed}
            onSelect={onSelect}
          />
          <div className="mt-6 flex items-center justify-between text-sm">
            <p className="text-gray-500">
              {revealed
                ? (selected === current.correct_answer ? 'Correct' : `Answer: ${current.correct_answer}`)
                : 'Pick the candidate that depicts the same person, or E if none do.'}
            </p>
            <div className="flex items-center gap-2">
              <button onClick={() => { setScore({ correct: 0, total: 0, streak: 0 }); setSeenIds([]); next(); }}
                className="text-xs px-3 py-1.5 bg-white border border-gray-200 rounded hover:bg-gray-100 inline-flex items-center gap-1">
                <RotateCcw size={12} /> Reset
              </button>
              <button onClick={next} disabled={!revealed}
                className="text-xs px-3 py-1.5 bg-black text-white rounded hover:bg-gray-800 disabled:opacity-50 inline-flex items-center gap-1">
                Next <ArrowRight size={12} />
              </button>
            </div>
          </div>
        </div>
      )}

      <p className="mt-6 text-xs text-gray-400 text-center">
        Shortcuts: <kbd className="px-1 border rounded">1-5</kbd> select · <kbd className="px-1 border rounded">N</kbd> next · <kbd className="px-1 border rounded">R</kbd> reset
      </p>
    </section>
  );
}

function Stat({ label, value }) {
  return (
    <div className="text-right">
      <div className="text-[10px] text-gray-400 uppercase font-bold tracking-wider">{label}</div>
      <div className="font-mono font-semibold text-gray-900">{value}</div>
    </div>
  );
}
