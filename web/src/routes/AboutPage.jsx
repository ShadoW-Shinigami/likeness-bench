import React from 'react';

export default function AboutPage() {
  return (
    <section className="max-w-3xl mx-auto px-6 py-10 prose prose-sm prose-gray">
      <h1 className="text-xl sm:text-2xl font-semibold tracking-tight">About Likeness Detector</h1>

      <p className="text-sm text-gray-600 leading-relaxed mt-3">
        Likeness Detector is a vision-language-model benchmark. Each item is a 5-option MCQ:
        a reference photograph plus 4 candidate faces (A–D) and a fifth option E meaning
        "none of the above". The model picks one. ~50% of items contain the actual person
        among the four candidates; ~50% don't, making E correct.
      </p>

      <h2 className="text-base font-semibold mt-6">Composite Likeness Score</h2>
      <p className="text-sm text-gray-600 leading-relaxed">
        We report two accuracy halves separately — accuracy when the correct person <em>is</em>
        present, and accuracy when they're <em>not</em>. The composite penalises systematic
        E-bias so a model that always (or never) picks E doesn't game the metric.
      </p>
      <pre className="text-xs bg-gray-50 p-3 rounded border border-gray-200 overflow-x-auto">
{`Composite = 0.5 · accuracy_present + 0.5 · accuracy_absent
          − 0.25 · |fp_E − fn_E|`}
      </pre>

      <h2 className="text-base font-semibold mt-6">Distractor calibration</h2>
      <p className="text-sm text-gray-600 leading-relaxed">
        Distractors are bucketed by ArcFace cosine similarity to the reference: <em>easy</em>
        (0–0.30), <em>medium</em> (0.30–0.50), <em>hard</em> (0.50–0.70), <em>extreme</em> (0.70+).
        Most synthetic distractors are mined from the SFHQ-T2I corpus; tier gaps are filled
        with Nano Banana 2 (via Fal AI) using identity-preserving inpainting prompts.
      </p>

      <h2 className="text-base font-semibold mt-6">Architecture</h2>
      <ul className="text-sm text-gray-600 space-y-1">
        <li><strong>Eval engine</strong>: Python 3.11 in conda env <code>eval</code>; async runner with per-sample atomic checkpoints, pause/resume/kill via on-disk control file.</li>
        <li><strong>Server</strong>: FastAPI on a single port — serves <code>/api/*</code> AND the built React bundle.</li>
        <li><strong>Frontend</strong>: React + Vite + Tailwind, served as a static bundle by the same FastAPI process.</li>
        <li><strong>Image generation</strong>: Nano Banana 2 (<code>fal-ai/nano-banana-2</code> + <code>edit</code>) for both base faces and identity-preserving variants.</li>
        <li><strong>Image storage</strong>: Azure Blob Storage; sample images served via Cloudflare CDN (cached 1y). The FastAPI <code>/api/samples/.../image/...</code> route 302-redirects to the CDN URL when present.</li>
        <li><strong>Similarity tiering</strong>: perceptual hash (16-bit) for v0; ArcFace via insightface lands in v1.1.</li>
      </ul>

      <h2 className="text-base font-semibold mt-6">Add a model</h2>
      <pre className="text-xs bg-gray-50 p-3 rounded border border-gray-200 overflow-x-auto">
{`# 1. cp .env.example .env && fill in keys
# 2. add a [models.foo] block to bench.toml
# 3. bench eval --model foo --benchmark likeness_v1`}
      </pre>

      <h2 className="text-base font-semibold mt-6">Build the dataset</h2>
      <pre className="text-xs bg-gray-50 p-3 rounded border border-gray-200 overflow-x-auto">
{`python scripts/build_dataset.py \\
    --n-pool 20 --n-samples 15 \\
    --max-cost-usd 8 --upload`}
      </pre>
      <p className="text-sm text-gray-600 mt-2">
        Each sample directory holds <code>base.png</code>, <code>option_a..d.png</code>,
        and a <code>meta.json</code> with the answer key + Azure CDN URLs.
      </p>

      <h2 className="text-base font-semibold mt-6">Add a test type</h2>
      <p className="text-sm text-gray-600">
        Subclass <code>bench.tasks.base.Task</code>, decorate <code>@register_task</code>, drop a
        new renderer under <code>web/src/components/task-types/</code>, and the leaderboard /
        practice / sample views all auto-dispatch.
      </p>
    </section>
  );
}
