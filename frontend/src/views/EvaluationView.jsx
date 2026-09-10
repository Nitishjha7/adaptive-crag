/**
 * Evaluation ka poora page.
 *
 * Pehle ye right rail me ek chhota tab tha aur usme sirf numbers the. Numbers
 * akele **misleading** hain: 20/20 dekh ke lagta hai router perfect hai, jabki
 * asli baat ye hai ki labelled task aasan hai. RESULTS.md yahi kehta hai, aur
 * dashboard ko usse ulta impression nahi dena chahiye.
 *
 * Isliye yahan har number ke saath uska caveat hai, aur do **negative results**
 * bhi utne hi prominently hain jitne accuracy — kyunki wahi is project ki asli
 * cheez hai.
 */
function Metric({ label, value, hint, tone = "slate", big }) {
  const tones = {
    slate: "text-slate-900",
    emerald: "text-emerald-600",
    amber: "text-amber-600",
  };
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className={`font-bold ${big ? "text-3xl" : "text-2xl"} ${tones[tone]}`}>
        {value}
      </div>
      <div className="mt-1 text-sm font-medium text-slate-700">{label}</div>
      {hint && <div className="mt-0.5 text-xs text-slate-400">{hint}</div>}
    </div>
  );
}

function Finding({ title, children, tone = "amber" }) {
  const styles =
    tone === "amber"
      ? "border-amber-200 bg-amber-50/60"
      : "border-slate-200 bg-slate-50";
  return (
    <div className={`rounded-xl border p-4 ${styles}`}>
      <h4 className="text-sm font-semibold text-slate-800">{title}</h4>
      <p className="mt-1.5 text-sm leading-relaxed text-slate-600">{children}</p>
    </div>
  );
}

export default function EvaluationView({ stats }) {
  const e = stats?.evaluation;

  if (!e) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-10 text-center">
        <h2 className="font-semibold text-slate-800">No evaluation results yet</h2>
        <p className="mx-auto mt-2 max-w-md text-sm text-slate-500">
          The routing eval hasn't been run for the{" "}
          <span className="font-mono">{stats?.corpus ?? "current"}</span> corpus. Run{" "}
          <span className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs">
            .\dev.ps1 eval
          </span>{" "}
          to measure it.
        </p>
        {/* "Measure nahi hua" aur "score zero hai" do alag baatein hain — UI ko
            kabhi zero nahi dikhana chahiye jab measurement hui hi na ho. */}
        <p className="mt-3 text-xs text-slate-400">
          Nothing is shown as 0 here on purpose — "not measured" and "scored zero"
          are different claims.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-lg font-semibold">Does the router actually route?</h2>
        <p className="mt-1 text-sm text-slate-500">
          Measured on a labelled set for the{" "}
          <span className="font-mono">{stats.corpus}</span> corpus — not asserted.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Metric
          big
          label="Routing accuracy"
          value={`${e.routing_correct}/${e.routing_total}`}
          hint={`${e.routing_accuracy_pct}% on the labelled set`}
        />
        <Metric
          big
          tone="emerald"
          label="Missed fallbacks"
          value={e.missed_fallbacks}
          hint="Answered locally when it shouldn't have"
        />
        <Metric
          label="Unnecessary fallbacks"
          value={e.unnecessary_fallbacks}
          hint="The cheap error — one extra web call"
        />
        <Metric
          label="Groundedness"
          value={`${e.groundedness_pass_pct}%`}
          hint="Answers supported by their context"
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Metric
          label="LLM calls (local)"
          value={e.llm_calls_local ?? "—"}
          hint="The fast, cheap path"
        />
        <Metric
          label="LLM calls (web)"
          value={e.llm_calls_web ?? "—"}
          hint="Correction costs one extra call"
        />
        <Metric
          label="Ambiguous cases"
          value={e.ambiguous_cases ?? "—"}
          hint="Corpus half-covers the topic"
        />
        <Metric
          label="Route stability"
          value={
            e.ambiguous_stability_pct != null ? `${e.ambiguous_stability_pct}%` : "—"
          }
          hint="Same question, repeated — same side?"
        />
      </div>

      {/* Sirf BEIR pe milta hai — wahan qrels batate hain ki sahi doc kaunsa tha.
          Concepts corpus pe ground truth hai hi nahi, isliye card hi nahi dikhta. */}
      {e.recall_at_k_pct != null && (
        <div className="grid gap-4 sm:grid-cols-2">
          <Metric
            big
            label="Retrieval recall@k"
            value={`${e.recall_at_k_pct}%`}
            hint="Was the gold document actually retrieved? (needs dataset qrels)"
          />
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-3">
        <Finding title="100% means the task is easy, not that the router is perfect">
          The corpus gap is categorical by design — concepts in, vendor/pricing/news
          out — so most web cases differ along an obvious axis. Ambiguous cases were
          added for the harder situation and are scored for <em>stability</em>, not
          correctness, because their labels are genuinely contestable.
        </Finding>

        <Finding title="Negative result: latency could not be measured">
          The cost argument rests on <strong>LLM call counts</strong>, not latency.
          Groq's throttling swamps the route difference — one run measured the local
          route slower than the web route, which is backwards. The first ordering was
          confounded and looked convincing.
        </Finding>

        <Finding title="Negative result: reranking changed nothing here">
          Hybrid search and cross-encoder reranking were A/B'd behind flags. Routing
          and stability were identical — yet 27 of 28 questions retrieved{" "}
          <em>different</em> chunks. On a small topically-clustered corpus the verdict
          follows topic, not ranking.
        </Finding>
      </div>

      <p className="text-xs text-slate-400">
        Full analysis, including both negative results, is in{" "}
        <span className="font-mono">backend/eval/RESULTS.md</span>.
      </p>
    </div>
  );
}
