import React, { useEffect, useState } from 'react';
import { CheckCircle, AlertCircle } from 'lucide-react';
import { api } from '../utils/api.js';
import EmptyState from '../components/shared/EmptyState.jsx';
import CompanyLogo from '../components/shared/CompanyLogo.jsx';

export default function ModelsPage() {
  const [models, setModels] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.models().then((d) => setModels(d.models)).catch((e) => setError(String(e)));
  }, []);

  if (error) return <EmptyState variant="error" title="Error" description={error} />;
  if (!models) return <EmptyState variant="loading" title="Loading models…" />;

  return (
    <section className="max-w-5xl mx-auto px-6 py-10">
      <h1 className="text-xl sm:text-2xl font-semibold tracking-tight mb-2">Models</h1>
      <p className="text-sm text-gray-500 mb-6">
        Configured in <code className="text-xs bg-gray-100 px-1 rounded">bench.toml</code>. Add an API key
        in <code className="text-xs bg-gray-100 px-1 rounded">.env</code> to enable a model.
      </p>
      <div className="border border-gray-200 rounded-lg overflow-hidden shadow-sm">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-gray-500">
            <tr>
              <th className="px-4 py-3 text-left">Model</th>
              <th className="px-4 py-3 text-left">Provider</th>
              <th className="px-4 py-3 text-right">$/1M in</th>
              <th className="px-4 py-3 text-right">$/1M out</th>
              <th className="px-4 py-3 text-center">Configured</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 bg-white">
            {models.map((m) => (
              <tr key={m.key}>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-3">
                    <CompanyLogo company={m.family} />
                    <div>
                      <div className="font-medium">{m.display}</div>
                      <div className="text-xs text-gray-500 font-mono">{m.model_id}</div>
                    </div>
                  </div>
                </td>
                <td className="px-4 py-3 text-xs text-gray-500">{m.provider}</td>
                <td className="px-4 py-3 text-right font-mono text-xs">${m.price_per_1m_input.toFixed(2)}</td>
                <td className="px-4 py-3 text-right font-mono text-xs">${m.price_per_1m_output.toFixed(2)}</td>
                <td className="px-4 py-3 text-center">
                  {m.configured ? (
                    <CheckCircle size={16} className="inline text-emerald-500" />
                  ) : (
                    <AlertCircle size={16} className="inline text-gray-300" />
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
