/**
 * Node-by-node execution timeline - the most honest part of the UI.
 *
 * Every backend node appends one line to `logs` (an additive reducer). Those
 * lines become this timeline, so you can see what the system decided:
 * retrieve -> grade: no -> rewrite -> web search -> generate -> validate.
 *
 * **No per-step timestamps** — the backend emits no per-node timing, and
 * printing "10:24:03" would be inventing a number. The total `elapsed_ms` is
 * real, so that is what is shown.
 */
const LABELS = {
  retrieve: ["Retrieve", "Hybrid search + rerank"],
  grade_documents: ["Grade", "Is this context sufficient?"],
  transform_query: ["Rewrite query", "Conversational -> keywords"],
  web_search_fallback: ["Web search", "Local context was insufficient"],
  generate: ["Generate", "Grounded in retrieved context"],
  validate_guardrails: ["Validate", "Groundedness + PII check"],
};

/** Short names for the chain — the whole path has to fit on one line. */
const SHORT = {
  retrieve: "retrieve",
  grade_documents: "grade",
  transform_query: "rewrite",
  web_search_fallback: "web search",
  generate: "generate",
  validate_guardrails: "validate",
};

/** These four nodes make an LLM call; retrieve and web_search do not. */
const LLM_NODES = ["grade_documents", "transform_query", "generate", "validate_guardrails"];

export function parse(line) {
  const node = line.split(" ->")[0].trim();
  const detail = line.slice(node.length).replace(/^\s*->\s*/, "");
  return { node, detail };
}

/**
 * How many LLM calls it took — counted from the trace, never hardcoded.
 * This is the number the "why not always search the web" argument rests on.
 */
export function llmCalls(logs = []) {
  return logs.filter((l) => LLM_NODES.includes(parse(l).node)).length;
}

/**
 * The route on one line: `retrieve -> grade: no -> rewrite -> web search -> generate`.
 * The grade verdict appears inline, because that is the project's turning point.
 */
export function chain(logs = []) {
  return logs
    .map(parse)
    .filter((s) => SHORT[s.node])
    .map((s) => {
      if (s.node !== "grade_documents") return { text: SHORT[s.node] };
      const verdict = s.detail.trim().split(/\s+/)[0];
      return { text: `grade: ${verdict}`, verdict };
    });
}

function Tick({ state }) {
  if (state === "skipped") {
    return <span className="mt-1 block h-4 w-4 shrink-0 rounded-full border-2 border-ink-700" />;
  }
  const failed = state === "failed";
  return (
    <span
      className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full ${
        failed ? "bg-red-500" : "bg-emerald-500"
      }`}
    >
      <svg viewBox="0 0 24 24" className="h-3 w-3" fill="none" stroke="#fff" strokeWidth="3.5">
        {failed ? <path d="M18 6 6 18M6 6l12 12" /> : <path d="M20 6 9 17l-5-5" />}
      </svg>
    </span>
  );
}

export default function TraceTimeline({ logs }) {
  if (!logs?.length) return null;

  const steps = logs.map(parse);
  const ranWeb = steps.some((s) => s.node === "web_search_fallback");

  // On the local route web search *never ran*. Showing it as a greyed-out step
  // is what makes clear that the fallback is conditional, not the default.
  const rows = [...steps];
  if (!ranWeb) {
    const at = rows.findIndex((s) => s.node === "generate");
    rows.splice(at < 0 ? rows.length : at, 0, {
      node: "web_search_fallback",
      detail: "",
      skipped: true,
    });
  }

  return (
    <ol className="space-y-0">
      {rows.map((s, i) => {
        const [title, hint] = LABELS[s.node] || [s.node, ""];
        const failed = s.detail.includes("FAILED");
        const state = s.skipped ? "skipped" : failed ? "failed" : "done";
        const last = i === rows.length - 1;

        return (
          <li key={i} className="relative flex gap-3 pb-3.5 last:pb-0">
            {!last && <span className="absolute left-2 top-5 h-full w-px bg-ink-700" />}
            <Tick state={state} />
            <div className="min-w-0 flex-1">
              <div
                className={`text-sm font-medium ${
                  s.skipped ? "text-slate-400" : failed ? "text-red-600" : "text-slate-100"
                }`}
              >
                {title}
                {s.skipped && " (skipped)"}
              </div>
              <div className="break-words font-mono text-xs text-slate-400">
                {s.skipped ? "local docs were sufficient" : s.detail || hint}
              </div>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
