import TraceTimeline from "./TraceTimeline.jsx";

/** Right rail: response details + trace, system config, and eval numbers. */
const TABS = [
  { id: "trace", label: "Sources & Trace" },
  { id: "system", label: "System Info" },
  { id: "eval", label: "Evaluation" },
];

function Row({ label, children }) {
  return (
    <div className="flex items-center justify-between gap-3 py-1.5 text-sm">
      <span className="text-slate-500">{label}</span>
      <span className="text-right font-medium text-slate-800">{children}</span>
    </div>
  );
}

function Card({ title, children }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <h3 className="mb-2 text-sm font-semibold text-slate-800">{title}</h3>
      {children}
    </div>
  );
}

export default function SidePanel({ tab, onTab, latest, stats, llmNodes = [] }) {
  return (
    <div className="flex h-full flex-col gap-4">
      <div className="flex gap-1 rounded-xl border border-slate-200 bg-white p-1">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => onTab(t.id)}
            className={`flex-1 rounded-lg px-2 py-2 text-xs font-medium transition ${
              tab === t.id
                ? "bg-indigo-50 text-indigo-700"
                : "text-slate-500 hover:bg-slate-50"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "trace" && (
        <>
          <Card title="Response Details">
            {latest ? (
              <>
                <Row label="Route Taken">
                  <span
                    className={`rounded-md px-2 py-0.5 text-xs ${
                      latest.source_type === "vector_db"
                        ? "bg-emerald-50 text-emerald-700"
                        : "bg-sky-50 text-sky-700"
                    }`}
                  >
                    {latest.source_type === "vector_db" ? "Local Documents" : "Web Fallback"}
                  </span>
                </Row>
                {/* Binary, 0.92 nahi. Grader ek word lautata hai; decimal
                    dikhana precision gadhna hoga jo hai hi nahi. */}
                <Row label="Relevance Verdict">
                  <span className="font-mono">{latest.relevance_score}</span>
                </Row>
                {/* Trace se gina jaata hai, hardcode nahi — yahi wo cost metric
                    hai jispe "hamesha web search kyun nahi" wala argument khada
                    hai, aur eval bhi isi ko report karta hai (local 3 vs web 4). */}
                <Row label="LLM Calls">
                  {
                    latest.logs.filter((l) =>
                      llmNodes.includes(l.split(" ->")[0].trim())
                    ).length
                  }
                </Row>
                <Row label="Response Time">{(latest.elapsed_ms / 1000).toFixed(1)}s</Row>
              </>
            ) : (
              <p className="text-sm text-slate-400">Ask something to see the trace.</p>
            )}
          </Card>

          {latest && (
            <Card title="Trace">
              <TraceTimeline logs={latest.logs} sourceType={latest.source_type} />
            </Card>
          )}

          <div className="rounded-xl border border-indigo-100 bg-indigo-50/50 p-4">
            {/* Emoji ki jagah SVG: emoji font har machine pe nahi hoti aur
                headless/Linux pe khaali box (tofu) ban jaata hai. */}
            <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-indigo-900">
              <svg
                viewBox="0 0 24 24"
                className="h-4 w-4"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.8"
                aria-hidden="true"
              >
                <path d="M9 18h6M10 22h4" />
                <path d="M12 2a7 7 0 0 0-4 12.7V17h8v-2.3A7 7 0 0 0 12 2z" />
              </svg>
              How CRAG works
            </h3>
            <ol className="list-inside list-decimal space-y-1 text-xs leading-relaxed text-indigo-900/80">
              <li>Retrieve candidates from the vector DB and BM25, then rerank</li>
              <li>Grade whether they actually answer the question</li>
              <li>If insufficient → rewrite the query and search the web</li>
              <li>Generate an answer only from the surviving context</li>
              <li>Validate groundedness and redact PII</li>
            </ol>
          </div>
        </>
      )}

      {tab === "system" && (
        <Card title="Configuration">
          {stats ? (
            <>
              <Row label="LLM">
                <span className="font-mono text-xs">{stats.config.llm_model}</span>
              </Row>
              <Row label="Embeddings">
                <span className="font-mono text-xs">{stats.config.embedding_model}</span>
              </Row>
              <Row label="Reranker">
                <span className="font-mono text-xs">
                  {stats.config.reranker_model ?? "off"}
                </span>
              </Row>
              <Row label="Hybrid (BM25)">{stats.config.hybrid ? "on" : "off"}</Row>
              <Row label="Search provider">{stats.config.search_provider}</Row>
              <Row label="Top K">{stats.config.top_k}</Row>
              <Row label="Corpus">
                <span className="font-mono text-xs">{stats.corpus}</span>
              </Row>
              <Row label="Documents">{stats.documents ?? "—"}</Row>
              <Row label="Chunks">{stats.chunks}</Row>
              <Row label="Groq key">
                <span className={stats.config.groq_key_set ? "text-emerald-600" : "text-red-600"}>
                  {stats.config.groq_key_set ? "set" : "missing"}
                </span>
              </Row>
            </>
          ) : (
            <p className="text-sm text-slate-400">Loading…</p>
          )}
        </Card>
      )}

      {tab === "eval" && (
        <Card title="Routing Evaluation">
          {stats?.evaluation ? (
            <>
              <Row label="Routing accuracy">
                {stats.evaluation.routing_correct}/{stats.evaluation.routing_total} (
                {stats.evaluation.routing_accuracy_pct}%)
              </Row>
              <Row label="Missed fallbacks">{stats.evaluation.missed_fallbacks}</Row>
              <Row label="Unnecessary fallbacks">{stats.evaluation.unnecessary_fallbacks}</Row>
              <Row label="Groundedness">{stats.evaluation.groundedness_pass_pct}%</Row>
              {/* Sirf BEIR pe milta hai — wahan qrels batate hain ki sahi doc
                  kaunsa tha. Concepts corpus pe ground truth hai hi nahi, isliye
                  row hi nahi dikhti (0% dikhana jhooth hoga). */}
              {stats.evaluation.recall_at_k_pct != null && (
                <Row label="Retrieval recall@k">
                  {stats.evaluation.recall_at_k_pct}%
                </Row>
              )}
              <Row label="LLM calls (local / web)">
                {stats.evaluation.llm_calls_local} / {stats.evaluation.llm_calls_web}
              </Row>
              <Row label="Ambiguous cases">{stats.evaluation.ambiguous_cases}</Row>
              <Row label="Route stability">
                {stats.evaluation.ambiguous_stability_pct ?? "—"}
                {stats.evaluation.ambiguous_stability_pct != null && "%"}
              </Row>

              {/* Ye caveat number ke saath hi rehna chahiye. 100% ka matlab hai
                  labelled task aasan hai, router perfect nahi — RESULTS.md yahi
                  baat karta hai, aur dashboard ko usse ulta impression nahi dena. */}
              <p className="mt-3 border-t border-slate-100 pt-3 text-xs leading-relaxed text-slate-500">
                100% means the labelled task is easy, not that the router is perfect —
                the corpus gap is categorical by design. Full analysis and two negative
                results are in <span className="font-mono">eval/RESULTS.md</span>.
              </p>
            </>
          ) : (
            <p className="text-sm text-slate-400">
              No eval results yet. Run <span className="font-mono">.\dev.ps1 eval</span>.
            </p>
          )}
        </Card>
      )}
    </div>
  );
}
