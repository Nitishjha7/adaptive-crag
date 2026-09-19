/**
 * The whole Evaluation page.
 *
 * Numbers on their own are **misleading**: 20/20 reads as a perfect router when
 * the real point is that the labelled task is easy. So every number carries its
 * caveat, and the negative results sit as prominently as the accuracy.
 *
 * Trimmed twice. There were **nine** metric cards: three said the same thing
 * (routing accuracy = total - missed - unnecessary, so missed and unnecessary
 * are its *breakdown*, not its peers), two were not measurements at all (LLM
 * calls are the fixed cost of each path, and now appear in every chat trace),
 * and "Ambiguous cases" was not a result — it was Route stability's denominator.
 *
 * Then the three prose cards below. They read as generated, for a clear reason:
 * all three had the same shape — bold title plus ~40 words — and all three
 * *described* their data instead of *showing* it. "27 of 28 questions retrieved
 * different chunks" disappears inside a sentence; in a table it is the
 * punchline. Each block now carries its own real numbers.
 */
function Metric({ label, value, hint, tone = "slate", big }) {
  const tones = {
    slate: "text-white",
    emerald: "text-emerald-600",
    amber: "text-amber-600",
  };
  return (
    <div className="rounded-xl border border-ink-700 bg-ink-850 p-4">
      <div className={`font-bold ${big ? "text-3xl" : "text-2xl"} ${tones[tone]}`}>
        {value}
      </div>
      <div className="mt-1 text-sm font-medium text-slate-200">{label}</div>
      {hint && <div className="mt-0.5 text-xs text-slate-400">{hint}</div>}
    </div>
  );
}

/** One experiment: the question, its **data**, then the conclusion. */
function Experiment({ question, children, footnote }) {
  return (
    <div className="rounded-xl border border-ink-700 bg-ink-850 p-5">
      <h4 className="text-sm font-semibold text-slate-100">{question}</h4>
      <div className="mt-3">{children}</div>
      {footnote && (
        <p className="mt-3 border-t border-ink-700 pt-3 text-sm leading-relaxed text-slate-400">
          {footnote}
        </p>
      )}
    </div>
  );
}

/** Before/after — three columns. */
function Compare({ head = ["", "before", "after"], rows }) {
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-xs uppercase tracking-wide text-slate-400">
          <th className="pb-1.5 text-left font-medium">{head[0]}</th>
          <th className="pb-1.5 text-right font-medium">{head[1]}</th>
          <th className="pb-1.5 text-right font-medium">{head[2]}</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.label} className="border-t border-ink-700">
            <td className="py-1.5 text-slate-400">{r.label}</td>
            <td className="py-1.5 text-right font-mono text-slate-500">{r.before}</td>
            <td
              className={`py-1.5 text-right font-mono ${
                r.moved ? "font-semibold text-emerald-600" : "text-slate-200"
              }`}
            >
              {r.after}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** Label -> count. The `punch` row is the one that matters. */
function Counts({ rows }) {
  return (
    <table className="w-full text-sm">
      <tbody>
        {rows.map((r) => (
          <tr key={r.label} className="border-t border-ink-700 first:border-0">
            <td
              className={`py-1.5 ${
                r.punch ? "font-medium text-slate-100" : "text-slate-400"
              }`}
            >
              {r.label}
            </td>
            <td
              className={`py-1.5 text-right font-mono ${
                r.punch ? "text-base font-bold text-white" : "text-slate-500"
              }`}
            >
              {r.value}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/**
 * Who built the test set — the most important sentence on the page.
 *
 * On concepts the labels are the author's own, which is the single-author bias
 * RESULTS.md admits to. On SciFact the local cases come from the dataset's
 * qrels, so no author judgement is involved. This difference is not something to
 * hide — it is what tells you how much to trust each number.
 */
const LABELLING = {
  concepts: (
    <>
      20 routing cases <strong>hand-labelled by me</strong>, plus 8 ambiguous ones
      scored only for stability. Two things follow. The bias is real — the same person
      who chose where the corpus gap is also decided which side each question belongs
      on. And the task is easier than the score suggests: the gap is categorical
      (concepts in, vendor/pricing/news out), so most web cases differ along an obvious
      axis. <strong>100% means the task is easy, not that the router is perfect.</strong>
    </>
  ),
  scifact: (
    <>
      20 local cases come from SciFact&apos;s own{" "}
      <span className="font-mono">qrels</span> — the dataset says which abstract
      supports which claim, so no author judgement is involved. The 8 web cases are
      hand-written (live pricing, current limits): the easy half, and labelled as such.
    </>
  ),
};

/**
 * The experiments change with the corpus, and that matters.
 *
 * These cards used to be hardcoded and only talked about `concepts`. Under
 * `CORPUS=scifact` the UI showed SciFact's numbers with "reranking changed
 * nothing" written underneath — **wrong** on that corpus. The dashboard's own
 * rule is not to claim what was not measured, let alone claim the opposite.
 *
 * Every number here comes from `backend/eval/RESULTS.md`. None were invented.
 */
const EXPERIMENTS = {
  concepts: [
    {
      question: "Does hybrid search + reranking change the routing decision?",
      table: (
        <Counts
          rows={[
            { label: "Identical chunks, identical order", value: "0" },
            { label: "Same chunks, reordered", value: "1" },
            { label: "Different chunks retrieved", value: "27" },
            { label: "Routing decisions that changed", value: "0", punch: true },
          ]}
        />
      ),
      footnote: (
        <>
          Retrieval genuinely changed on 27 of 28 questions — and not one verdict moved.{" "}
          <span className="font-mono">grade_documents</span> concatenates all four chunks
          into a single prompt, so <em>ordering is invisible to it</em>; reranking can
          only matter by changing membership, and on 22 chunks membership rarely crosses
          a topic boundary. The honest conclusion is that this eval cannot show a benefit
          — which is not the same as there being none.
        </>
      ),
    },
    {
      question: "Is the local route measurably faster?",
      table: (
        <Compare
          head={["ordering", "local", "web"]}
          rows={[
            { label: "Run 1 — cases in file order", before: "13.7s", after: "18.5s" },
            { label: "Run 2 — interleaved", before: "16.2s", after: "14.9s" },
          ]}
        />
      ),
      footnote: (
        <>
          Run 1 looked like a clean win, and it was an artifact: local cases ran first, so
          Groq&apos;s throttling landed entirely in their bucket. Interleaved, the web path
          comes out <em>faster</em> — impossible, since it does strictly more work. Both
          numbers are noise, so no latency figure appears anywhere on this page. The cost
          argument rests on LLM call counts, which are exact by construction.
        </>
      ),
    },
  ],
  scifact: [
    {
      question: "The same A/B, on a corpus that has ground truth",
      table: (
        <Compare
          head={["", "vector only", "hybrid + rerank"]}
          rows={[
            { label: "Routing accuracy", before: "75.0%", after: "78.6%", moved: true },
            { label: "Retrieval recall@k", before: "65.0%", after: "70.0%", moved: true },
            { label: "Unnecessary fallbacks", before: "7", after: "6", moved: true },
            { label: "Missed fallbacks", before: "0", after: "0" },
          ]}
        />
      ),
      footnote: (
        <>
          Everything moved the right way, and exactly <strong>one case</strong> changed:
          #10, whose gold document went missed → retrieved and whose route followed web →
          local. So +5pp recall is one document out of twenty. The mechanism is real and
          now instrumented end to end; the magnitude is well inside noise, and calling it
          an improvement would need the full 5k corpus and 300-query set.
        </>
      ),
    },
    {
      question: "Where did the routing errors actually come from?",
      table: (
        <Compare
          head={["gold document", "cases", "routed correctly"]}
          rows={[
            { label: "Retrieved", before: "13", after: "13 / 13", moved: true },
            { label: "Missed", before: "7", after: "0 / 7" },
          ]}
        />
      ),
      footnote: (
        <>
          The correlation is perfect, which means{" "}
          <strong>the grader made zero independent errors</strong>. Every routing failure
          was a retrieval miss the grader detected correctly — it read four chunks that
          did not contain the answer and said so. So 78.6% understates the grader:
          conditional on what it was given, it was right every time. The bottleneck here
          is retrieval, not grading.
        </>
      ),
    },
  ],
};

export default function EvaluationView({ stats }) {
  const e = stats?.evaluation;

  if (!e) {
    return (
      <div className="rounded-xl border border-ink-700 bg-ink-850 p-10 text-center">
        <h2 className="font-semibold text-slate-100">No evaluation results yet</h2>
        <p className="mx-auto mt-2 max-w-md text-sm text-slate-500">
          The routing eval hasn&apos;t been run for the{" "}
          <span className="font-mono">{stats?.corpus ?? "current"}</span> corpus. Run{" "}
          <span className="rounded bg-ink-800 px-1.5 py-0.5 font-mono text-xs">
            .\dev.ps1 eval
          </span>{" "}
          to measure it.
        </p>
        {/* "Not measured" and "scored zero" are different claims — the UI must
            never show a zero when no measurement happened. */}
        <p className="mt-3 text-xs text-slate-400">
          Nothing is shown as 0 here: &quot;not measured&quot; and &quot;scored
          zero&quot; are different claims.
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

      <div className="rounded-xl border border-ink-700 bg-ink-900 p-4">
        <h4 className="text-sm font-semibold text-slate-100">Who labelled this set</h4>
        <p className="mt-1.5 text-sm leading-relaxed text-slate-400">
          {LABELLING[stats.corpus] ?? LABELLING.concepts}
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.35fr)]">
        <Metric
          big
          label="Routing accuracy"
          value={`${e.routing_correct}/${e.routing_total}`}
          hint={`${e.routing_accuracy_pct}% on the labelled set`}
        />

        {/* Missed and unnecessary are not peers of accuracy, they are its
            breakdown — three equal cards made them look like three separate
            results. The real point is the **difference**: one is expensive, one
            is cheap. */}
        <div className="rounded-xl border border-ink-700 bg-ink-850 p-4">
          <div className="text-sm font-medium text-slate-200">Where the errors are</div>
          <div className="mt-3 space-y-2.5">
            <div className="flex items-baseline gap-3">
              <span
                className={`w-8 shrink-0 text-right text-2xl font-bold ${
                  e.missed_fallbacks ? "text-red-600" : "text-emerald-600"
                }`}
              >
                {e.missed_fallbacks}
              </span>
              <span className="text-xs leading-snug text-slate-500">
                <span className="font-medium text-slate-200">missed fallbacks</span> —
                answered locally when it should not have. The expensive error: a confident
                answer built on the wrong context.
              </span>
            </div>
            <div className="flex items-baseline gap-3">
              <span className="w-8 shrink-0 text-right text-2xl font-bold text-white">
                {e.unnecessary_fallbacks}
              </span>
              <span className="text-xs leading-snug text-slate-500">
                <span className="font-medium text-slate-200">unnecessary fallbacks</span> —
                searched the web when local docs would have done. Costs one extra LLM
                call; the answer is still right.
              </span>
            </div>
          </div>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <Metric
          label="Groundedness"
          value={`${e.groundedness_pass_pct}%`}
          hint="Answers supported by their own retrieved context"
        />

        {/* Only available on BEIR, where qrels say which document was correct.
            The concepts corpus has no ground truth, so no card. */}
        {e.recall_at_k_pct != null && (
          <Metric
            label="Retrieval recall@k"
            value={`${e.recall_at_k_pct}%`}
            hint="Was the gold document actually retrieved?"
          />
        )}

        {/* Groundedness says "the answer matches its context". This says "the
            answer was **right**". Two different claims: a wrong answer built
            from the wrong context can pass groundedness. */}
        {e.answer_verdict_pct != null && (
          <Metric
            label="Answer correctness"
            value={`${e.answer_verdict_pct}%`}
            hint={`Did the answer reach the dataset's own verdict? (${e.answer_verdict_checked} labelled cases)`}
          />
        )}

        {/* With no ambiguous cases, stability means nothing — an empty "—" card
            used to sit here. */}
        {e.ambiguous_cases > 0 && (
          <Metric
            label="Route stability"
            value={
              e.ambiguous_stability_pct != null
                ? `${Math.round(
                    (e.ambiguous_stability_pct / 100) * e.ambiguous_cases,
                  )}/${e.ambiguous_cases}`
                : "—"
            }
            hint="Ambiguous questions, asked twice — same side both times?"
          />
        )}
      </div>

      <div>
        <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
          What was tested, and what came back
        </h3>
        <div className="mt-3 grid gap-4 lg:grid-cols-2">
          {(EXPERIMENTS[stats.corpus] ?? EXPERIMENTS.concepts).map((x) => (
            <Experiment key={x.question} question={x.question} footnote={x.footnote}>
              {x.table}
            </Experiment>
          ))}
        </div>
      </div>

      <p className="text-xs text-slate-400">
        Full analysis, including the negative results, is in{" "}
        <span className="font-mono">backend/eval/RESULTS.md</span>.
      </p>
    </div>
  );
}
