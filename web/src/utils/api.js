// Single-port: FastAPI serves both API and the React bundle, so relative URLs work.
const API_BASE = '';

export async function get(path) {
  const r = await fetch(`${API_BASE}${path}`);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

export async function post(path, body) {
  const r = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body == null ? null : JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

export const api = {
  benchmarks: () => get('/api/results/benchmarks'),
  benchmarkIndex: (id) => get(`/api/results/${id}/index`),
  runFile: (id, file) => get(`/api/results/${id}/runs/${file}`),

  samples: (id) => get(`/api/samples/${id}`),
  sampleMeta: (bench, sample) => get(`/api/samples/${bench}/${sample}/meta`),
  imageUrl: (bench, sample, file) => `/api/samples/${bench}/${sample}/image/${file}`,

  models: () => get('/api/models'),

  showcaseStatus: () => get('/api/showcase/status'),
  showcaseBuild: () => post('/api/showcase/build'),
  showcaseUrl: () => '/api/showcase/file',

  runs: () => get('/api/runs'),
  run: (id) => get(`/api/runs/${id}`),
  startRun: (payload) => post('/api/runs', payload),
  pauseRun: (id) => post(`/api/runs/${id}/pause`),
  resumeRun: (id) => post(`/api/runs/${id}/resume`),
  killRun: (id) => post(`/api/runs/${id}/kill`),
  streamRun: (id) => new EventSource(`/api/runs/${id}/stream`),
};
