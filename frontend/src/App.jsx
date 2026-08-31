import { useState } from "react";

import ChatBox from "./components/ChatBox.jsx";
import RelevancePill from "./components/RelevancePill.jsx";
import SourceBadge from "./components/SourceBadge.jsx";
import TraceViewer from "./components/TraceViewer.jsx";

export default function App() {
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  async function ask(question) {
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      // Relative path — dev me Vite proxy, production me Nginx handle karta hai.
      const res = await fetch("/api/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });

      if (!res.ok) {
        // Backend ka asli message dikhate hain (missing key, rate limit) —
        // generic "something went wrong" se debug karna namumkin hota hai.
        const body = await res.text();
        throw new Error(`HTTP ${res.status} — ${body.slice(0, 300)}`);
      }

      setResult({ ...(await res.json()), question });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto max-w-3xl px-4 py-10">
        <header className="mb-8">
          <h1 className="text-2xl font-semibold">Adaptive CRAG</h1>
          <p className="mt-1 text-sm text-slate-400">
            Self-correcting RAG — grades its own retrieval, and falls back to live
            web search only when the local context can't answer.
          </p>
        </header>

        <ChatBox onSubmit={ask} loading={loading} />

        {loading && (
          <p className="mt-8 animate-pulse text-sm text-slate-500">
            retrieve → grade → ...
          </p>
        )}

        {error && (
          <div className="mt-8 rounded-lg border border-red-900/50 bg-red-950/30 p-4">
            <p className="text-sm font-medium text-red-300">Request failed</p>
            <p className="mt-1 break-words font-mono text-xs text-red-400/80">
              {error}
            </p>
          </div>
        )}

        {result && (
          <div className="mt-8 space-y-4">
            <div className="flex flex-wrap items-center gap-2">
              <SourceBadge sourceType={result.source_type} />
              <RelevancePill score={result.relevance_score} />
              <span className="text-xs text-slate-600">{result.elapsed_ms} ms</span>
            </div>

            <div className="rounded-lg border border-slate-800 bg-slate-900/50 p-4">
              <p className="whitespace-pre-wrap leading-relaxed text-slate-200">
                {result.answer}
              </p>
            </div>

            {/* Rewritten query sirf fallback path pe hoti hai. Ise dikhana
                "system ne khud query badli" wala point sabse saaf dikhata hai. */}
            {result.transformed_query && (
              <div className="rounded-lg border border-sky-900/40 bg-sky-950/20 p-3">
                <span className="text-xs uppercase tracking-wider text-sky-500/70">
                  Rewritten for search
                </span>
                <p className="mt-1 font-mono text-sm text-sky-300">
                  {result.transformed_query}
                </p>
              </div>
            )}

            <TraceViewer logs={result.logs} />
          </div>
        )}
      </div>
    </div>
  );
}
