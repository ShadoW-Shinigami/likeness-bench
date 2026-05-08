"""Build a single self-contained showcase.html showing every sample, every
model's prediction, and the leaderboard.

Image URL resolution:
  1. `cdn_url` / `base_cdn_url` field in meta.json (if a CDN backend was used)
  2. relative path `dataset/<bench>/samples/<sid>/<filename>` (default — local)

Per-sample predictions:
  Read from each result JSON's `samples` array.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from dotenv import load_dotenv

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
load_dotenv(REPO / ".env", override=False)

BENCHMARK_ID = "likeness_v2"
DATASET_DIR = REPO / "dataset" / BENCHMARK_ID / "samples"
RESULTS_DIR = REPO / "results" / BENCHMARK_ID
SHOWCASE_HTML = REPO / "showcase.html"


def _rel_image_path(sid: str, fname: str) -> str:
    sample_dir = DATASET_DIR / sid
    jpg = sample_dir / fname.replace(".png", ".jpg")
    if jpg.exists():
        return f"dataset/{BENCHMARK_ID}/samples/{sid}/{jpg.name}"
    return f"dataset/{BENCHMARK_ID}/samples/{sid}/{fname}"


def _resolve_url(meta: dict, sid: str, *, base: bool, letter: str | None = None) -> str:
    if base:
        cdn = meta.get("base_cdn_url") or meta.get("_base_cdn_url")
        if cdn:
            return cdn
        return _rel_image_path(sid, meta.get("base_image", "base.jpg"))
    opt = (meta.get("options") or {}).get(letter, {})
    cdn = opt.get("cdn_url")
    if cdn:
        return cdn
    return _rel_image_path(sid, opt.get("image", f"option_{letter.lower()}.jpg"))


def load_samples() -> list[dict]:
    out: list[dict] = []
    for sample_dir in sorted(DATASET_DIR.iterdir()):
        if not sample_dir.is_dir():
            continue
        meta_path = sample_dir / "meta.json"
        if not meta_path.exists():
            continue
        meta = json.loads(meta_path.read_text())
        sid = meta["id"]
        item = {
            "id": sid,
            "type_b": meta.get("none_of_the_above_is_correct", False),
            "correct_answer": meta["correct_answer"],
            "action_scenario": (meta.get("metadata") or {}).get("action_scenario", ""),
            "base_jpg": _resolve_url(meta, sid, base=True),
            "options": {},
        }
        for letter in ("A", "B", "C", "D"):
            opt = (meta.get("options") or {}).get(letter, {})
            if opt.get("image"):
                item["options"][letter] = {
                    "url": _resolve_url(meta, sid, base=False, letter=letter),
                    "kind": opt.get("kind"),
                    "source": opt.get("source"),
                    "tier": opt.get("similarity_tier"),
                    "cosine": opt.get("similarity_cosine"),
                }
        out.append(item)
    return out


def load_per_model_predictions() -> dict[str, dict[str, dict]]:
    out: dict[str, dict[str, dict]] = {}
    for result_path in sorted(RESULTS_DIR.glob("*__*.json")):
        d = json.loads(result_path.read_text())
        model_id = d["model"]["id"]
        per_sample = {}
        for sr in d.get("samples", []):
            sid = sr.get("sample_id")
            if sid:
                per_sample[sid] = {"predicted": sr.get("predicted"), "correct": sr.get("correct")}
        out[model_id] = per_sample
    return out


def load_leaderboard() -> dict:
    idx = RESULTS_DIR / "index.json"
    if not idx.exists():
        return {"rows": [], "baselines": []}
    d = json.loads(idx.read_text())
    for r in d.get("rows", []):
        f = RESULTS_DIR / r["file"]
        if f.exists():
            sub = json.loads(f.read_text())
            m = sub.get("metrics", {})
            r["accuracy_when_present"] = m.get("accuracy_when_present", 0)
            r["accuracy_when_absent"] = m.get("accuracy_when_absent", 0)
    return d


def render_html(samples, preds, leaderboard) -> str:
    payload = json.dumps({
        "samples": samples,
        "predictions": preds,
        "leaderboard": leaderboard,
        "generated_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
    })
    return HTML_TEMPLATE.replace("__DATA_JSON__", payload)


HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Likeness Detector · likeness_v2</title>
<link href="https://rsms.me/inter/inter.css" rel="stylesheet">
<script src="https://cdn.tailwindcss.com"></script>
<style>
  :root { font-family: 'Inter', system-ui, sans-serif; }
  body { font-feature-settings: "ss01","cv11"; }
  .accent-grad { background: linear-gradient(135deg,#0ea5e9,#a855f7); }
  .skeleton { background: linear-gradient(90deg,#f3f4f6 0%,#e5e7eb 50%,#f3f4f6 100%);
              background-size: 200% 100%; animation: shimmer 1.4s linear infinite; }
  @keyframes shimmer { 0% { background-position: 0% 0% } 100% { background-position: -200% 0% } }
  .glow-correct { box-shadow: 0 0 0 3px rgba(16,185,129,0.5), 0 8px 30px -10px rgba(16,185,129,0.4); }
  .glow-wrong { box-shadow: 0 0 0 3px rgba(244,63,94,0.5); }
  .scrollbar-thin::-webkit-scrollbar { height: 6px; width: 6px; }
  .scrollbar-thin::-webkit-scrollbar-thumb { background: #d4d4d8; border-radius: 3px; }
  details > summary { cursor: pointer; list-style: none; }
  details > summary::-webkit-details-marker { display: none; }
</style>
</head>
<body class="bg-zinc-50 text-zinc-900 antialiased">
  <script id="data" type="application/json">__DATA_JSON__</script>

  <!-- Header -->
  <header class="border-b border-zinc-200 bg-white sticky top-0 z-30 backdrop-blur-md bg-white/80">
    <div class="max-w-7xl mx-auto px-6 h-14 flex items-center justify-between">
      <div class="flex items-center gap-3">
        <div class="w-7 h-7 rounded accent-grad"></div>
        <div>
          <div class="font-semibold tracking-tight text-sm">Likeness Detector</div>
          <div class="text-[10px] text-zinc-500 uppercase tracking-widest">likeness_v2 · 50 samples</div>
        </div>
      </div>
      <nav class="flex items-center gap-4 text-sm text-zinc-600">
        <a href="#leaderboard" class="hover:text-zinc-900 transition">Leaderboard</a>
        <a href="#samples" class="hover:text-zinc-900 transition">Samples</a>
        <a href="#methodology" class="hover:text-zinc-900 transition">Methodology</a>
      </nav>
    </div>
  </header>

  <!-- Hero -->
  <section class="max-w-7xl mx-auto px-6 pt-14 pb-10">
    <div class="max-w-2xl">
      <h1 class="text-4xl font-semibold tracking-tight">Can vision-language models tell people apart when they're <span class="italic text-transparent bg-clip-text accent-grad">doing the same thing</span>?</h1>
      <p class="text-zinc-600 mt-4 leading-relaxed text-[15px]">
        Each item is a 5-option MCQ. Reference photo of a person, four candidate full-body action shots — all of the same activity. ~50% of items have the actual person somewhere in the four; the rest are all lookalikes (E = "none of the above"). Distractors are vision-described and identity-verified through Gemini 2.5 Flash; the correct option is a GPT-Image-2 edit of the reference; an ArcFace baseline gives the empirical ceiling.
      </p>
    </div>
  </section>

  <!-- Leaderboard -->
  <section id="leaderboard" class="max-w-7xl mx-auto px-6 pb-14">
    <h2 class="text-xs uppercase tracking-widest text-zinc-500 font-medium mb-3">Leaderboard</h2>
    <div id="leaderboard-table" class="rounded-2xl border border-zinc-200 bg-white overflow-hidden shadow-[0_1px_2px_rgba(0,0,0,0.04)]"></div>
    <p class="text-[11px] text-zinc-500 mt-3">
      <strong>Composite</strong> = ½·acc(present) + ½·acc(absent) − ¼·(false-pos<sub>E</sub> + false-neg<sub>E</sub>)/2.
      Baselines: random = 20%, always-pick-E = 50%.
    </p>
  </section>

  <!-- Sample browser -->
  <section id="samples" class="max-w-7xl mx-auto px-6 pb-20">
    <div class="flex items-center justify-between mb-3">
      <h2 class="text-xs uppercase tracking-widest text-zinc-500 font-medium">Samples</h2>
      <div class="flex items-center gap-2 text-xs">
        <select id="filter" class="border border-zinc-200 rounded-md px-2 py-1 bg-white">
          <option value="all">all</option>
          <option value="present">correct present (Type A)</option>
          <option value="absent">correct absent (Type B)</option>
        </select>
        <select id="model-filter" class="border border-zinc-200 rounded-md px-2 py-1 bg-white">
          <option value="">highlight: none</option>
        </select>
      </div>
    </div>

    <div id="sample-grid" class="grid grid-cols-1 gap-6"></div>

    <nav id="pagination" class="flex items-center justify-center gap-2 mt-10 text-sm select-none"></nav>
  </section>

  <!-- Methodology footer -->
  <section id="methodology" class="border-t border-zinc-200 bg-white">
    <div class="max-w-7xl mx-auto px-6 py-12 grid grid-cols-1 md:grid-cols-2 gap-10 text-sm">
      <div>
        <h3 class="text-xs uppercase tracking-widest text-zinc-500 font-medium mb-2">Pipeline</h3>
        <ol class="list-decimal list-inside space-y-1 text-zinc-700">
          <li>Sample seeded with one full-body action scenario (bar, bicycle, jogging…).</li>
          <li>Subject portrait via Nano Banana 2 (text-to-image).</li>
          <li>Vision describe (Gemini 2.5 Flash via OR-on-Fal).</li>
          <li>Type A correct answer: GPT-Image-2 Edit putting subject in the action.</li>
          <li>3 (Type A) or 4 (Type B) NB2 t2i lookalikes — same action, vision-derived "different person".</li>
          <li>All 50 × 5 images uploaded to Azure as JPEG q=85 (this page).</li>
        </ol>
      </div>
      <div>
        <h3 class="text-xs uppercase tracking-widest text-zinc-500 font-medium mb-2">Models evaluated</h3>
        <ul class="space-y-1 text-zinc-700">
          <li><span class="inline-block w-2 h-2 rounded-full bg-fuchsia-500 mr-2"></span>ArcFace buffalo_l (face-recognition baseline, no LLM)</li>
          <li><span class="inline-block w-2 h-2 rounded-full bg-blue-500 mr-2"></span>Gemini 3 Flash · Seed 2.0 Lite · Seed 1.6</li>
          <li><span class="inline-block w-2 h-2 rounded-full bg-amber-500 mr-2"></span>Claude Opus 4.6 · 4.7</li>
          <li><span class="inline-block w-2 h-2 rounded-full bg-rose-500 mr-2"></span>GPT-5.5</li>
        </ul>
        <p class="text-[11px] text-zinc-500 mt-3" id="generated-meta"></p>
      </div>
    </div>
  </section>

<script>
(() => {
  const DATA = JSON.parse(document.getElementById('data').textContent);
  const PER_PAGE = 8;
  let page = 1;
  let presenceFilter = 'all';
  let highlightModel = '';

  // ---- helpers ----
  const fmtPct = v => (v * 100).toFixed(1) + '%';
  const escapeHTML = s => (s ?? '').toString()
      .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
      .replace(/"/g,'&quot;');

  const FAMILY_COLOR = {
    'InsightFace': 'fuchsia',
    'OpenAI': 'rose',
    'Anthropic': 'amber',
    'Google': 'blue',
    'ByteDance': 'sky',
  };

  // ---- leaderboard ----
  function renderLeaderboard() {
    const rows = (DATA.leaderboard.rows || []).slice().sort((a,b) => b.composite - a.composite);
    const max = Math.max(...rows.map(r => r.composite), 0.6);
    let html = `
      <table class="w-full text-sm">
        <thead class="text-[11px] uppercase tracking-wider text-zinc-500 bg-zinc-50/70">
          <tr>
            <th class="px-5 py-3 text-left w-12">#</th>
            <th class="px-5 py-3 text-left">Model</th>
            <th class="px-5 py-3 text-left">Composite</th>
            <th class="px-5 py-3 text-right">Accuracy</th>
            <th class="px-5 py-3 text-right">Type A · present</th>
            <th class="px-5 py-3 text-right">Type B · absent</th>
            <th class="px-5 py-3 text-right">N</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-zinc-100">`;
    rows.forEach((r, i) => {
      const fam = FAMILY_COLOR[r.company] || 'zinc';
      const w = Math.round((r.composite / max) * 100);
      const tone = r.composite > 0.8 ? 'emerald' : r.composite > 0.5 ? 'blue' : r.composite > 0.3 ? 'amber' : 'rose';
      html += `<tr class="hover:bg-zinc-50/50 transition">
        <td class="px-5 py-4 text-zinc-400 font-mono text-xs">${i+1}</td>
        <td class="px-5 py-4">
          <div class="flex items-center gap-3">
            <div class="w-8 h-8 rounded-md bg-${fam}-100 text-${fam}-700 grid place-items-center text-[10px] font-semibold tracking-wider">${(r.company||'??').slice(0,2).toUpperCase()}</div>
            <div>
              <div class="font-medium">${escapeHTML(r.model_name)}</div>
              <div class="text-xs text-zinc-500">${escapeHTML(r.company || '')}</div>
            </div>
          </div>
        </td>
        <td class="px-5 py-4">
          <div class="flex items-center gap-3">
            <span class="font-mono font-semibold w-14 text-right tabular-nums">${fmtPct(r.composite)}</span>
            <div class="flex-1 max-w-xs h-1.5 rounded-full bg-zinc-100 overflow-hidden">
              <div class="h-full bg-${tone}-500 rounded-full transition-all duration-700" style="width:${w}%"></div>
            </div>
          </div>
        </td>
        <td class="px-5 py-4 text-right tabular-nums">${fmtPct(r.accuracy)}</td>
        <td class="px-5 py-4 text-right tabular-nums text-zinc-600">${fmtPct(r.accuracy_when_present||0)}</td>
        <td class="px-5 py-4 text-right tabular-nums text-zinc-600">${fmtPct(r.accuracy_when_absent||0)}</td>
        <td class="px-5 py-4 text-right tabular-nums text-zinc-500">${r.n_samples}</td>
      </tr>`;
    });
    (DATA.leaderboard.baselines || []).forEach(b => {
      const w = Math.round((b.composite / max) * 100);
      html += `<tr class="bg-zinc-50/50 text-zinc-500 italic">
        <td class="px-5 py-3 font-mono text-xs">·</td>
        <td class="px-5 py-3">${escapeHTML(b.label)}</td>
        <td class="px-5 py-3">
          <div class="flex items-center gap-3">
            <span class="font-mono w-14 text-right">${fmtPct(b.composite)}</span>
            <div class="flex-1 max-w-xs h-1 rounded-full bg-zinc-200 overflow-hidden">
              <div class="h-full bg-zinc-400" style="width:${w}%"></div>
            </div>
          </div>
        </td>
        <td colspan="4"></td>
      </tr>`;
    });
    html += `</tbody></table>`;
    document.getElementById('leaderboard-table').innerHTML = html;
  }

  // ---- model filter dropdown ----
  function renderModelFilter() {
    const sel = document.getElementById('model-filter');
    sel.innerHTML = '<option value="">highlight: none</option>';
    DATA.leaderboard.rows.forEach(r => {
      const opt = document.createElement('option');
      opt.value = r.model_id;
      opt.textContent = `highlight: ${r.model_name}`;
      sel.appendChild(opt);
    });
    sel.addEventListener('change', e => { highlightModel = e.target.value; renderSamples(); });
  }

  // ---- samples ----
  function filteredSamples() {
    return DATA.samples.filter(s => {
      if (presenceFilter === 'all') return true;
      if (presenceFilter === 'present') return !s.type_b;
      if (presenceFilter === 'absent') return s.type_b;
      return true;
    });
  }

  function renderSamples() {
    const all = filteredSamples();
    const totalPages = Math.max(1, Math.ceil(all.length / PER_PAGE));
    page = Math.min(page, totalPages);
    const slice = all.slice((page-1)*PER_PAGE, page*PER_PAGE);
    const grid = document.getElementById('sample-grid');
    grid.innerHTML = slice.map(renderSampleCard).join('');
    renderPagination(totalPages, all.length);
    // re-arm lazy loading
    grid.querySelectorAll('img[data-src]').forEach(img => {
      io.observe(img);
    });
  }

  function modelPredsPills(sid) {
    const rows = DATA.leaderboard.rows.slice().sort((a,b)=>b.composite-a.composite);
    return rows.map(r => {
      const p = (DATA.predictions[r.model_id] || {})[sid] || {};
      const pred = p.predicted ?? '—';
      const correct = !!p.correct;
      const fam = FAMILY_COLOR[r.company] || 'zinc';
      const isHighlighted = highlightModel && highlightModel === r.model_id;
      const ring = isHighlighted ? 'ring-2 ring-offset-1 ring-zinc-900' : '';
      return `<div class="flex items-center gap-2 ${ring} rounded-md px-2 py-1.5 ${correct ? 'bg-emerald-50' : 'bg-rose-50'}">
        <div class="w-5 h-5 rounded bg-${fam}-100 text-${fam}-700 grid place-items-center text-[8px] font-semibold tracking-wider">${(r.company||'??').slice(0,2).toUpperCase()}</div>
        <div class="text-[11px] leading-tight">
          <div class="font-medium text-zinc-700">${escapeHTML(r.model_name)}</div>
          <div class="text-zinc-500">picked <span class="font-mono font-semibold ${correct ? 'text-emerald-700' : 'text-rose-700'}">${escapeHTML(pred)}</span> ${correct ? '<span class="text-emerald-600">✓</span>' : '<span class="text-rose-600">✗</span>'}</div>
        </div>
      </div>`;
    }).join('');
  }

  function optionTile(s, letter) {
    const opt = s.options[letter] || {};
    const isCorrect = letter === s.correct_answer;
    const ring = isCorrect ? 'glow-correct ring-emerald-500' : 'ring-zinc-200';
    const isAI = (opt.source||'').includes('nb2_action_lookalike') || (opt.source||'').includes('gpt_image_2_edit');
    const labelTone = opt.kind === 'true_match' ? 'bg-emerald-600 text-white' : 'bg-white/95 text-zinc-700 border border-zinc-200';
    const tier = opt.tier ? `<span class="absolute top-1.5 right-1.5 text-[9px] px-1 py-0.5 rounded bg-white/95 border border-zinc-200 text-zinc-600 uppercase tracking-wider">${escapeHTML(opt.tier)}</span>` : '';
    const sources = opt.source==='gpt_image_2_edit' ? '<span class="absolute bottom-1.5 left-1.5 text-[9px] px-1 py-0.5 rounded bg-fuchsia-100 text-fuchsia-700 font-medium">GPT-IM-2</span>' :
                    opt.source==='nb2_action_lookalike' ? '<span class="absolute bottom-1.5 left-1.5 text-[9px] px-1 py-0.5 rounded bg-blue-100 text-blue-700 font-medium">NB2</span>' : '';
    return `<div class="relative aspect-square rounded-lg overflow-hidden bg-zinc-100 ${ring} ring-1 group">
      <div class="absolute inset-0 skeleton"></div>
      <img data-src="${opt.url || ''}" alt="${letter}" class="absolute inset-0 w-full h-full object-cover opacity-0 transition-opacity duration-300" />
      <div class="absolute top-1.5 left-1.5 ${labelTone} text-[10px] font-bold rounded w-5 h-5 grid place-items-center">${letter}</div>
      ${tier}
      ${sources}
      ${isCorrect ? '<div class="absolute bottom-1.5 right-1.5 text-[9px] px-1 py-0.5 rounded bg-emerald-600 text-white font-medium">CORRECT</div>' : ''}
    </div>`;
  }

  function renderSampleCard(s) {
    const correctIsE = s.correct_answer === 'E';
    const noneTile = `<div class="relative aspect-square rounded-lg border-2 border-dashed ${correctIsE ? 'glow-correct border-emerald-500 bg-emerald-50' : 'border-zinc-300 bg-zinc-50'} flex flex-col items-center justify-center text-zinc-500">
      <div class="text-2xl font-bold">E</div>
      <div class="text-[9px] uppercase tracking-wider">none of the above</div>
      ${correctIsE ? '<div class="absolute bottom-1.5 right-1.5 text-[9px] px-1 py-0.5 rounded bg-emerald-600 text-white font-medium">CORRECT</div>' : ''}
    </div>`;
    const tilesAD = ['A','B','C','D'].map(L => optionTile(s, L)).join('');
    const typeLabel = s.type_b
      ? '<span class="text-[10px] px-2 py-0.5 rounded-full bg-purple-100 text-purple-700 font-medium uppercase tracking-wider">Type B · correct absent</span>'
      : '<span class="text-[10px] px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700 font-medium uppercase tracking-wider">Type A · correct present</span>';
    const action = s.action_scenario || '';
    return `<article class="rounded-2xl bg-white border border-zinc-200 shadow-[0_1px_2px_rgba(0,0,0,0.04)] overflow-hidden">
      <header class="px-6 pt-5 pb-3 flex items-center justify-between gap-4 flex-wrap">
        <div class="flex items-center gap-3">
          <div class="font-mono text-[11px] text-zinc-400">${escapeHTML(s.id)}</div>
          ${typeLabel}
        </div>
        <div class="text-xs text-zinc-500 italic max-w-md text-right line-clamp-1">"${escapeHTML(action)}"</div>
      </header>

      <div class="px-6 pb-6 grid grid-cols-1 md:grid-cols-12 gap-5">
        <div class="md:col-span-4">
          <div class="text-[10px] uppercase tracking-widest text-zinc-500 mb-1.5">Reference</div>
          <div class="relative aspect-square rounded-lg overflow-hidden bg-zinc-100 ring-1 ring-zinc-200">
            <div class="absolute inset-0 skeleton"></div>
            <img data-src="${s.base_jpg}" alt="${s.id} base" class="absolute inset-0 w-full h-full object-cover opacity-0 transition-opacity duration-300" />
          </div>
        </div>
        <div class="md:col-span-8">
          <div class="text-[10px] uppercase tracking-widest text-zinc-500 mb-1.5">Candidates</div>
          <div class="grid grid-cols-2 sm:grid-cols-5 gap-2.5">
            ${tilesAD}
            ${noneTile}
          </div>
        </div>
      </div>

      <div class="border-t border-zinc-100 px-6 py-4 bg-zinc-50/50">
        <div class="text-[10px] uppercase tracking-widest text-zinc-500 mb-2">Model picks</div>
        <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-2">
          ${modelPredsPills(s.id)}
        </div>
      </div>
    </article>`;
  }

  function renderPagination(totalPages, totalCount) {
    const nav = document.getElementById('pagination');
    if (totalPages <= 1) {
      nav.innerHTML = `<span class="text-[11px] text-zinc-500">${totalCount} samples</span>`;
      return;
    }
    const btn = (label, target, disabled, current) =>
      `<button data-page="${target}" ${disabled?'disabled':''} class="px-3 py-1.5 rounded-md ${current?'bg-zinc-900 text-white':'bg-white border border-zinc-200 text-zinc-700 hover:bg-zinc-100'} ${disabled?'opacity-40 cursor-not-allowed':''}">${label}</button>`;
    let html = btn('← Prev', page-1, page===1);
    for (let p=1; p<=totalPages; p++) html += btn(String(p), p, false, p===page);
    html += btn('Next →', page+1, page===totalPages);
    html += `<span class="text-[11px] text-zinc-500 ml-3">${totalCount} samples</span>`;
    nav.innerHTML = html;
    nav.querySelectorAll('button[data-page]').forEach(b => {
      b.addEventListener('click', () => {
        const p = parseInt(b.dataset.page);
        if (!isNaN(p) && p>=1 && p<=totalPages) { page = p; renderSamples();
          window.scrollTo({top: document.getElementById('samples').offsetTop - 60, behavior: 'smooth'});
        }
      });
    });
  }

  // ---- intersection observer for lazy loading ----
  const io = new IntersectionObserver(entries => {
    entries.forEach(e => {
      if (!e.isIntersecting) return;
      const img = e.target;
      const src = img.getAttribute('data-src');
      if (src) {
        img.src = src;
        img.removeAttribute('data-src');
        img.onload = () => {
          img.style.opacity = '1';
          const skel = img.previousElementSibling;
          if (skel && skel.classList.contains('skeleton')) skel.remove();
        };
        img.onerror = () => {
          img.style.opacity = '0';
          const skel = img.previousElementSibling;
          if (skel && skel.classList.contains('skeleton')) {
            skel.classList.remove('skeleton');
            skel.classList.add('bg-zinc-100');
            skel.innerHTML = '<div class="absolute inset-0 grid place-items-center text-[10px] text-zinc-400">image error</div>';
          }
        };
        io.unobserve(img);
      }
    });
  }, { rootMargin: '300px' });

  // ---- filter wiring ----
  document.getElementById('filter').addEventListener('change', e => { presenceFilter = e.target.value; page = 1; renderSamples(); });

  document.addEventListener('keydown', e => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
    const totalPages = Math.max(1, Math.ceil(filteredSamples().length / PER_PAGE));
    if (e.key === 'ArrowRight' && page < totalPages) { page++; renderSamples(); }
    else if (e.key === 'ArrowLeft' && page > 1) { page--; renderSamples(); }
  });

  // ---- init ----
  document.getElementById('generated-meta').textContent = 'Generated ' + DATA.generated_at;
  renderLeaderboard();
  renderModelFilter();
  renderSamples();
})();
</script>
</body>
</html>
"""


def main():
    samples = load_samples()
    preds = load_per_model_predictions()
    leaderboard = load_leaderboard()
    html = render_html(samples, preds, leaderboard)
    SHOWCASE_HTML.write_text(html)
    print(f"Wrote {SHOWCASE_HTML}")
    print(f"  {len(samples)} samples · {len(preds)} models")
    if samples:
        first_url = samples[0].get("base_jpg", "")
        kind = "CDN" if first_url.startswith("http") else "local relative"
        print(f"  using {kind} URLs (e.g. {first_url[:80]})")


if __name__ == "__main__":
    main()
