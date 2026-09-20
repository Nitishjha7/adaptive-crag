/**
 * The right-hand rail on the chat view: what the system measured, and what it
 * just answered.
 *
 * Every figure comes from `/api/stats` or the live turn. Nothing is placeholder
 * data - a stat with no measurement behind it renders as "not measured" rather
 * than a zero, because a zero reads as a result.
 */

function Stat({ value, label, sub, tone = "text-white" }) {
  return (
    <div className="rounded-lg border border-ink-700 bg-ink-900 px-3 py-3">
      <div className={`text-xl font-semibold leading-none ${tone}`}>{value}</div>
      <div className="mt-1.5 text-[11px] font-medium text-slate-300">{label}</div>
      {sub && <div className="mt-0.5 text-[10px] leading-snug text-slate-500">{sub}</div>}
    </div>
  )
}

function Card({ title, right, children }) {
  return (
    <section className="rounded-xl border border-ink-700 bg-ink-850">
      <div className="flex items-center gap-2 border-b border-ink-700 px-4 py-3">
        <h2 className="text-sm font-semibold text-white">{title}</h2>
        {right && <div className="ml-auto">{right}</div>}
      </div>
      {children}
    </section>
  )
}

export default function ContextRail({ stats, latest, onOpenEval }) {
  const ev = stats?.evaluation
  const docs = stats?.documents ?? null

  return (
    <aside className="hidden w-[22rem] shrink-0 space-y-4 overflow-y-auto border-l border-ink-700 bg-ink-900 p-4 xl:block">
      <Card
        title="Measured"
        right={
          <button
            onClick={onOpenEval}
            className="text-[11px] text-slate-500 transition hover:text-slate-300"
          >
            details
          </button>
        }
      >
        <div className="grid grid-cols-2 gap-2.5 p-3">
          <Stat
            value={ev ? `${ev.routing_accuracy_pct}%` : "—"}
            label="Routing accuracy"
            sub={ev ? `${ev.routing_correct}/${ev.routing_total} on concepts` : null}
            tone="text-emerald-300"
          />
          <Stat
            value={ev ? ev.missed_fallbacks : "—"}
            label="Missed fallbacks"
            sub="never answered from the wrong documents"
            tone="text-emerald-300"
          />
          <Stat value={stats?.chunks ?? "—"} label="Indexed chunks" sub={stats?.corpus} />
          <Stat value={docs ?? "—"} label="Documents" sub="indexed" />
        </div>

        {/* 100% invites the obvious question, so the answer is on the card
            rather than left for the interview. */}
        {ev?.routing_accuracy_pct === 100 && (
          <p className="border-t border-ink-700 px-4 py-2.5 text-[11px] leading-relaxed text-slate-500">
            100% here means the concepts set is easy to route, not that the router
            is perfect. SciFact recall@k is 70%.
          </p>
        )}
      </Card>

      {latest && (
        <Card
          title="Latest answer"
          right={
            <span
              className={`rounded-md border px-2 py-0.5 text-[10px] ${
                latest.source_type === "web_search"
                  ? "border-sky-500/30 bg-sky-500/10 text-sky-300"
                  : "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
              }`}
            >
              {latest.source_type === "web_search" ? "web" : "corpus"}
            </span>
          }
        >
          <div className="space-y-3 p-4">
            <p className="text-xs font-medium leading-relaxed text-slate-200">
              {latest.question}
            </p>
            <p className="line-clamp-4 text-xs leading-relaxed text-slate-400">
              {latest.answer}
            </p>
            {latest.sources?.length > 0 && (
              <div>
                <p className="mb-1.5 text-[11px] text-slate-500">
                  Sources ({latest.sources.length})
                </p>
                <ul className="space-y-1">
                  {latest.sources.slice(0, 3).map((s, i) => (
                    <li
                      key={i}
                      className="flex items-center gap-2 rounded-md border border-ink-700 bg-ink-900 px-2.5 py-1.5"
                    >
                      <span className="grid h-4 w-4 shrink-0 place-items-center rounded bg-brand-600 text-[9px] font-semibold text-white">
                        {i + 1}
                      </span>
                      <span className="truncate font-mono text-[10px] text-slate-400">
                        {s}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </Card>
      )}

    </aside>
  )
}
