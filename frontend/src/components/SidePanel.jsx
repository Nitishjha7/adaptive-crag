import TraceTimeline from "./TraceTimeline.jsx";

/**
 * Chat ke saath ka right rail — sirf **is answer** ke baare me.
 *
 * Pehle yahan teen tabs the (Sources & Trace / System Info / Evaluation), par
 * ab wo dono sidebar me poore views hain. Ek hi cheez do jagah rakhna sirf
 * confusion deta hai — "Evaluation" click karne pe pata nahi chalta tha ki
 * sidebar wala chahiye tha ya panel wala. Isliye rail ab ek hi kaam karta hai.
 */
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

export default function SidePanel({ latest, llmNodes = [] }) {
  return (
    <div className="flex h-full flex-col gap-4">
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

            {/* Binary, 0.92 nahi. Grader ek word lautata hai; decimal dikhana
                precision gadhna hoga jo hai hi nahi. */}
            <Row label="Relevance Verdict">
              <span className="font-mono">{latest.relevance_score}</span>
            </Row>

            {/* Trace se gina jaata hai, hardcode nahi — yahi wo cost metric hai
                jispe "hamesha web search kyun nahi" wala argument khada hai. */}
            <Row label="LLM Calls">
              {
                latest.logs.filter((l) => llmNodes.includes(l.split(" ->")[0].trim()))
                  .length
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
        <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-indigo-900">
          {/* Emoji ki jagah SVG: emoji font har machine pe nahi hoti aur
              headless/Linux pe khaali box (tofu) ban jaata hai. */}
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
    </div>
  );
}
