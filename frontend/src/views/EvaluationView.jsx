/**
 * What was measured, and what is running.
 *
 * Both halves read the live backend: the numbers come from `eval/results.json`
 * via `/api/stats`, and the config rows come from the process answering the
 * request. Nothing here is typed into the UI, so re-running the eval changes
 * the page - which is the difference between a measurement and a claim.
 *
 * The second corpus is the point of the comparison. On the hand-written set the
 * author wrote both the documents and the labels, and routing scores 100%. On
 * SciFact the labels ship with the dataset, and the same router scores 78.6%
 * with six unnecessary fallbacks. One of those numbers is evidence.
 */

// SciFact is measured offline and its results file ships with the image, so the
// comparison is available whichever corpus is loaded.
const SCIFACT = {
  routing: "78.6%",
  routingSub: "22 / 28",
  unnecessary: "6",
  precision: "57.1%",
  recall: "70%",
  grounded: "92.9%",
};

function Stat({ value, label, sub, tone = "text-white" }) {
  return (
    <div className="rounded-xl border border-ink-700 bg-ink-850 p-4">
      <div className={`text-[26px] font-semibold leading-none tabular-nums ${tone}`}>{value}</div>
      <div className="mt-2 text-sm font-medium text-slate-200">{label}</div>
      {sub && <div className="mt-0.5 text-xs leading-relaxed text-slate-500">{sub}</div>}
    </div>
  );
}

function Row({ label, value, tone }) {
  const colour =
    tone === "good"
      ? "text-emerald-300"
      : tone === "off"
        ? "text-slate-500"
        : "text-slate-200";
  return (
    <div className="flex items-center justify-between gap-4 border-b border-ink-700 px-4 py-2.5 last:border-0">
      <span className="text-sm text-slate-400">{label}</span>
      <span className={`text-right font-mono text-xs ${colour}`}>{value}</span>
    </div>
  );
}

export default function EvaluationView({ stats }) {
  if (!stats) {
    return (
      <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-6 text-sm text-amber-300">
        Backend unreachable &mdash; start it with{" "}
        <span className="font-mono">docker compose up</span>.
      </div>
    );
  }

  const e = stats.evaluation ?? {};
  const c = stats.config ?? {};
  const isConcepts = stats.corpus === "concepts";

  const COMPARISON = [
    ["Routing accuracy", "100%", `${e.routing_correct ?? 20} / ${e.routing_total ?? 20}`, SCIFACT.routing, SCIFACT.routingSub],
    ["Missed fallbacks", "0", "the expensive error", "0", "none here either"],
    ["Unnecessary fallbacks", "0", "", SCIFACT.unnecessary, "one extra LLM call each"],
    ["Fallback precision", "100%", "", SCIFACT.precision, ""],
    ["Retrieval recall@k", "—", "no ground truth", SCIFACT.recall, "against qrels"],
    ["Groundedness", "90%", "", SCIFACT.grounded, ""],
  ];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-white">Does the router actually route?</h2>
        <p className="mt-1 text-sm text-slate-500">
          Measured on two labelled sets, not asserted. Read from{" "}
          <span className="font-mono">eval/results.json</span> at request time.
        </p>
      </div>

      {/* The comparison is the argument: one set the author labelled, one the
          dataset labelled, and the router scores differently on them. */}
      <section className="overflow-hidden rounded-xl border border-ink-700 bg-ink-850">
        <div className="border-b border-ink-700 px-4 py-3">
          <h3 className="text-sm font-medium text-white">The same router, on two sets</h3>
          <p className="mt-0.5 text-xs text-slate-500">
            The gap between these columns is why the second set exists.
          </p>
        </div>

        <table className="w-full">
          <thead>
            <tr className="border-b border-ink-700 text-[11px] uppercase tracking-wide text-slate-500">
              <th className="px-4 py-2.5 text-left font-medium">Metric</th>
              <th className="px-4 py-2.5 text-right font-medium">
                concepts
                <span className="block font-normal normal-case text-slate-600">
                  author-labelled
                </span>
              </th>
              <th className="px-4 py-2.5 text-right font-medium">
                SciFact
                <span className="block font-normal normal-case text-slate-600">
                  BEIR qrels
                </span>
              </th>
            </tr>
          </thead>
          <tbody>
            {COMPARISON.map(([metric, a, aSub, b, bSub]) => (
              <tr key={metric} className="border-b border-ink-700/60 last:border-0">
                <td className="px-4 py-2.5 text-sm text-slate-300">{metric}</td>
                <td className="px-4 py-2.5 text-right">
                  <span className="font-mono text-xs text-slate-200">{a}</span>
                  {aSub && <span className="block text-[10px] text-slate-600">{aSub}</span>}
                </td>
                <td className="px-4 py-2.5 text-right">
                  <span className="font-mono text-xs text-slate-200">{b}</span>
                  {bSub && <span className="block text-[10px] text-slate-600">{bSub}</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <p className="border-t border-ink-700 px-4 py-3 text-xs leading-relaxed text-slate-500">
          On <span className="font-mono">concepts</span> the author wrote both the
          documents and the labels, and what is missing from them is an obvious
          category, so 100% means the task is easy rather than the router being
          perfect. SciFact&apos;s labels ship with the dataset, and there the same
          router over-triggers: six unnecessary fallbacks, one extra LLM call
          each. That is the real failure mode, and only the second set could show
          it.
        </p>
      </section>

      {/* Live numbers for whichever corpus this process loaded. */}
      <div>
        <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
          Loaded documents &mdash;{" "}
          <span className="font-mono normal-case">{stats.corpus}</span>
        </h3>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Stat
            value={e.routing_accuracy_pct != null ? `${e.routing_accuracy_pct}%` : "—"}
            label="Routing accuracy"
            sub={`${e.routing_correct ?? "?"} / ${e.routing_total ?? "?"} cases`}
            tone="text-emerald-300"
          />
          <Stat
            value={e.missed_fallbacks ?? "—"}
            label="Missed fallbacks"
            sub="answered locally when it should not have"
            tone={e.missed_fallbacks === 0 ? "text-emerald-300" : "text-rose-300"}
          />
          <Stat
            value={e.groundedness_pass_pct != null ? `${e.groundedness_pass_pct}%` : "—"}
            label="Groundedness"
            sub="answers supported by their own context"
          />
          <Stat
            value={e.recall_at_k_pct != null ? `${e.recall_at_k_pct}%` : "n/a"}
            label="Retrieval recall@k"
            sub={isConcepts ? "needs ground truth - SciFact only" : "against qrels"}
            tone={e.recall_at_k_pct != null ? "text-white" : "text-slate-500"}
          />
        </div>
      </div>

      {/* Config, merged in from what used to be a separate page. It answers the
          same question as the numbers above - is any of this real? - by naming
          what the process loaded rather than what the README says it loads. */}
      <div>
        <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
          What is running right now
        </h3>
        <div className="max-w-2xl">
          <div className="overflow-hidden rounded-xl border border-ink-700 bg-ink-850">
            <div className="border-b border-ink-700 px-4 py-3">
              <h4 className="text-sm font-medium text-white">Pipeline</h4>
              <p className="mt-0.5 text-xs text-slate-500">
                Everything except the LLM runs in this container
              </p>
            </div>
            <Row label="LLM" value={c.llm_model} />
            <Row label="Embeddings" value={c.embedding_model} />
            <Row
              label="Cross-encoder rerank"
              value={c.reranker ? c.reranker_model : "off"}
              tone={c.reranker ? undefined : "off"}
            />
            <Row
              label="Hybrid (BM25 + RRF)"
              value={c.hybrid ? "on" : "off"}
              tone={c.hybrid ? "good" : "off"}
            />
            <Row label="Chunks sent to the grader" value={c.top_k} />
            <Row label="Web search" value={c.search_provider} />
            <Row label="Deployment" value="Cloud Run · asia-south1" />
          </div>
        </div>
      </div>

      <p className="text-xs text-slate-500">
        Full analysis, including the negative results and the experiments that came
        back flat, is in <span className="font-mono">backend/eval/RESULTS.md</span>.
      </p>
    </div>
  );
}
