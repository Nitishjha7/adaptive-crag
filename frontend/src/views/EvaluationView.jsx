/**
 * Evaluation ka poora page.
 *
 * Numbers akele **misleading** hain: 20/20 dekh ke lagta hai router perfect
 * hai, jabki asli baat ye hai ki labelled task aasan hai. Isliye har number ke
 * saath uska caveat hai, aur negative results utne hi prominently hain jitni
 * accuracy.
 *
 * Do baar chhaanta gaya hai. Pehle **nau** metric cards the: teen ek hi baat
 * keh rahe the (routing accuracy = total - missed - unnecessary, to missed aur
 * unnecessary uska *breakdown* hain, peers nahi), do measurement the hi nahi
 * (LLM calls dono paths ki fixed keemat hai, aur ab har chat trace me dikhti
 * hai), aur "Ambiguous cases" result nahi — Route stability ka denominator tha.
 *
 * Phir neeche ke teen prose cards. Wo "AI se likhwaya hua" lagte the, aur
 * wajah saaf thi: teeno ek hi shakl ke — bold title + ~40 shabd — aur teeno
 * apna data *bata* rahe the, *dikha* nahi rahe the. "27 of 28 questions
 * retrieved different chunks" ek jumle me dab jaata hai; table me wahi
 * punchline ban jaata hai. Ab har block apna asli number rakhta hai.
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

/** Ek experiment: sawaal, uska **data**, phir nateeja. */
function Experiment({ question, children, footnote }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <h4 className="text-sm font-semibold text-slate-800">{question}</h4>
      <div className="mt-3">{children}</div>
      {footnote && (
        <p className="mt-3 border-t border-slate-100 pt-3 text-sm leading-relaxed text-slate-600">
          {footnote}
        </p>
      )}
    </div>
  );
}

/** Before/after — teen column. */
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
          <tr key={r.label} className="border-t border-slate-100">
            <td className="py-1.5 text-slate-600">{r.label}</td>
            <td className="py-1.5 text-right font-mono text-slate-500">{r.before}</td>
            <td
              className={`py-1.5 text-right font-mono ${
                r.moved ? "font-semibold text-emerald-600" : "text-slate-700"
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

/** Label -> ginti. `punch` wali row hi asli baat hoti hai. */
function Counts({ rows }) {
  return (
    <table className="w-full text-sm">
      <tbody>
        {rows.map((r) => (
          <tr key={r.label} className="border-t border-slate-100 first:border-0">
            <td
              className={`py-1.5 ${
                r.punch ? "font-medium text-slate-800" : "text-slate-600"
              }`}
            >
              {r.label}
            </td>
            <td
              className={`py-1.5 text-right font-mono ${
                r.punch ? "text-base font-bold text-slate-900" : "text-slate-500"
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
 * Test set kisne banaya — page ka sabse zaroori jumla.
 *
 * Concepts pe labels khud author ne lagaye hain, aur wahi single-author bias
 * hai jo RESULTS.md maanta hai. SciFact pe local cases dataset ke qrels se
 * aate hain, to wahan author ki raay shaamil hi nahi. Ye farak chhupane wali
 * cheez nahi — yahi batata hai kis number pe kitna bharosa karna hai.
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
 * Experiments corpus ke saath badalte hain — aur ye zaroori hai.
 *
 * Pehle ye cards hardcoded the aur sirf `concepts` ki baat karte the.
 * `CORPUS=scifact` pe UI SciFact ke numbers dikhata par neeche likha rehta
 * "reranking changed nothing" — us corpus pe **galat**. Dashboard ka apna hi
 * rule hai ki jo measure nahi hua wo claim mat karo; ulta claim to bilkul nahi.
 *
 * Saare numbers `backend/eval/RESULTS.md` se hain, haath se koi nahi gadha.
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
      <div className="rounded-xl border border-slate-200 bg-white p-10 text-center">
        <h2 className="font-semibold text-slate-800">No evaluation results yet</h2>
        <p className="mx-auto mt-2 max-w-md text-sm text-slate-500">
          The routing eval hasn&apos;t been run for the{" "}
          <span className="font-mono">{stats?.corpus ?? "current"}</span> corpus. Run{" "}
          <span className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs">
            .\dev.ps1 eval
          </span>{" "}
          to measure it.
        </p>
        {/* "Measure nahi hua" aur "score zero hai" do alag baatein hain — UI ko
            kabhi zero nahi dikhana chahiye jab measurement hui hi na ho. */}
        <p className="mt-3 text-xs text-slate-400">
          Nothing is shown as 0 here on purpose — &quot;not measured&quot; and &quot;scored
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

      <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
        <h4 className="text-sm font-semibold text-slate-800">Who labelled this set</h4>
        <p className="mt-1.5 text-sm leading-relaxed text-slate-600">
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

        {/* Missed aur unnecessary accuracy ke peers nahi, uska breakdown hain —
            teen barabar cards me dikhane se lagta tha teen alag nataije hain.
            Asli baat dono ka **farak** hai: ek mehnga, ek sasta. */}
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <div className="text-sm font-medium text-slate-700">Where the errors are</div>
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
                <span className="font-medium text-slate-700">missed fallbacks</span> —
                answered locally when it should not have. The expensive error: a confident
                answer built on the wrong context.
              </span>
            </div>
            <div className="flex items-baseline gap-3">
              <span className="w-8 shrink-0 text-right text-2xl font-bold text-slate-900">
                {e.unnecessary_fallbacks}
              </span>
              <span className="text-xs leading-snug text-slate-500">
                <span className="font-medium text-slate-700">unnecessary fallbacks</span> —
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

        {/* Sirf BEIR pe milta hai — wahan qrels batate hain ki sahi doc kaunsa
            tha. Concepts pe ground truth hai hi nahi, isliye card hi nahi. */}
        {e.recall_at_k_pct != null && (
          <Metric
            label="Retrieval recall@k"
            value={`${e.recall_at_k_pct}%`}
            hint="Was the gold document actually retrieved?"
          />
        )}

        {/* Groundedness kehti hai "answer apne context se match karta hai".
            Ye kehta hai "answer **sahi** tha". Do alag baatein hain: galat
            context se bana galat answer groundedness pass kar sakta hai. */}
        {e.answer_verdict_pct != null && (
          <Metric
            label="Answer correctness"
            value={`${e.answer_verdict_pct}%`}
            hint={`Did the answer reach the dataset's own verdict? (${e.answer_verdict_checked} labelled cases)`}
          />
        )}

        {/* Ambiguous cases na hon to stability ka matlab hi nahi — pehle yahan
            khaali "—" wala card baitha rehta tha. */}
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
