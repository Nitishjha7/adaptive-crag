/**
 * Node-by-node execution timeline — UI ka sabse asli hissa.
 *
 * Backend ka har node `logs` me ek line append karta hai (additive reducer).
 * Yahan wahi lines timeline banti hain, to dikhta hai ki system ne kya socha:
 * retrieve -> grade: no -> rewrite -> web search -> generate -> validate.
 *
 * **Per-step timestamps nahi dikhate** — backend per-node timing emit nahi
 * karta, aur "10:24:03" chhaap dena number gadhna hoga. Total `elapsed_ms`
 * asli hai, wo dikhta hai.
 */
const LABELS = {
  retrieve: ["Retrieve", "Hybrid search + rerank"],
  grade_documents: ["Grade", "Is this context sufficient?"],
  transform_query: ["Rewrite query", "Conversational -> keywords"],
  web_search_fallback: ["Web search", "Local context was insufficient"],
  generate: ["Generate", "Grounded in retrieved context"],
  validate_guardrails: ["Validate", "Groundedness + PII check"],
};

/** Chain me chhote naam — ek line me poora rasta dikhana hai. */
const SHORT = {
  retrieve: "retrieve",
  grade_documents: "grade",
  transform_query: "rewrite",
  web_search_fallback: "web search",
  generate: "generate",
  validate_guardrails: "validate",
};

/** Ye chaar node LLM call karte hain; retrieve aur web_search nahi. */
const LLM_NODES = ["grade_documents", "transform_query", "generate", "validate_guardrails"];

export function parse(line) {
  const node = line.split(" ->")[0].trim();
  const detail = line.slice(node.length).replace(/^\s*->\s*/, "");
  return { node, detail };
}

/**
 * Kitne LLM call lage — trace se gine jaate hain, hardcode nahi.
 * Yahi wo number hai jispe "hamesha web search kyun nahi" wala argument khada hai.
 */
export function llmCalls(logs = []) {
  return logs.filter((l) => LLM_NODES.includes(parse(l).node)).length;
}

/**
 * Ek line ka rasta: `retrieve -> grade: no -> rewrite -> web search -> generate`.
 * Grade ka verdict chain me hi dikhta hai, kyunki wahi poore project ka mod hai.
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
    return <span className="mt-1 block h-4 w-4 shrink-0 rounded-full border-2 border-slate-200" />;
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

  // Local route pe web search *chala hi nahi* — usko greyed step ki tarah
  // dikhana hi wo baat saaf karta hai ki fallback conditional hai, default nahi.
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
            {!last && <span className="absolute left-2 top-5 h-full w-px bg-slate-200" />}
            <Tick state={state} />
            <div className="min-w-0 flex-1">
              <div
                className={`text-sm font-medium ${
                  s.skipped ? "text-slate-400" : failed ? "text-red-600" : "text-slate-800"
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
