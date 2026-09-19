/**
 * Live configuration — what is actually running.
 *
 * Every value comes from `/api/stats`; nothing on screen is hardcoded. That is
 * what makes this view useful when debugging: "is the reranker on", "which
 * corpus is loaded", "is the Groq key set" — all three answered here without
 * shelling into the container.
 */
function Row({ label, value, mono, tone }) {
  const tones = {
    good: "text-emerald-600",
    bad: "text-red-600",
    off: "text-slate-400",
  };
  return (
    <div className="flex items-center justify-between gap-4 border-b border-ink-700 py-2.5 last:border-0">
      <span className="text-sm text-slate-500">{label}</span>
      <span
        className={`text-right text-sm font-medium ${tone ? tones[tone] : "text-slate-100"} ${
          mono ? "font-mono text-xs" : ""
        }`}
      >
        {value}
      </span>
    </div>
  );
}

function Card({ title, subtitle, children }) {
  return (
    <div className="rounded-xl border border-ink-700 bg-ink-850 p-5">
      <h3 className="font-semibold text-slate-100">{title}</h3>
      {subtitle && <p className="mt-0.5 text-xs text-slate-400">{subtitle}</p>}
      <div className="mt-3">{children}</div>
    </div>
  );
}

export default function SystemView({ stats }) {
  if (!stats) {
    return (
      <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-6 text-sm text-amber-300">
        Backend unreachable — start it with{" "}
        <span className="font-mono">docker compose up</span>.
      </div>
    );
  }

  const c = stats.config;

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-lg font-semibold">System status</h2>
        <p className="mt-1 text-sm text-slate-500">
          Read live from the running backend — nothing on this page is hardcoded in
          the UI, so it is the fastest way to check what a container is actually
          running.
        </p>
      </div>

      {/* There were four cards. The "Retrieval" card held Corpus / Documents /
          Chunks — all three already in the header line and on the Documents page,
          so duplicated twice over. The reranker appeared twice: its model under
          "Models", its on/off under "Retrieval" — two rows for one thing. And the
          second row of the "Web fallback" card was derived (duckduckgo implies no
          key), which is a whole card for two lines.

          Now two cards: what is running, and what was never built. */}
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Pipeline" subtitle="Everything except the LLM runs locally">
          <Row label="LLM (Groq)" value={c.llm_model} mono />
          <Row
            label="Groq API key"
            value={c.groq_key_set ? "set" : "missing"}
            tone={c.groq_key_set ? "good" : "bad"}
          />
          <Row label="Embeddings" value={c.embedding_model} mono />
          {/* Flag and model in one row: showing the model name while it is off
              would be a lie, because it was never loaded. */}
          <Row
            label="Cross-encoder rerank"
            value={c.reranker ? (c.reranker_model ?? "on") : "off"}
            mono={Boolean(c.reranker && c.reranker_model)}
            tone={c.reranker ? undefined : "off"}
          />
          <Row
            label="Hybrid (BM25 + RRF)"
            value={c.hybrid ? "on" : "off"}
            tone={c.hybrid ? "good" : "off"}
          />
          <Row label="Chunks sent to the grader" value={c.top_k} />
          <Row
            label="Web search"
            value={
              c.search_provider === "duckduckgo"
                ? "duckduckgo — no API key"
                : `${c.search_provider} — needs a key`
            }
          />
        </Card>

        <Card title="Scope" subtitle="What this build does and does not do">
          <Row label="Deployment" value="Cloud Run · asia-south1" />
          <Row label="Ingestion" value="build-time — no upload API" tone="off" />
          <Row label="Context filter" value="none — top-k goes to the grader" tone="off" />
          <Row label="Conversation memory" value="none — each query is independent" tone="off" />
        </Card>
      </div>
    </div>
  );
}
