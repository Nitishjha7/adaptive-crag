/** Top dashboard strip.
 *
 * Har number `/api/stats` se aata hai — corpus files gine jaate hain, chunks
 * Chroma se, routing numbers `eval/results.json` se jo asli eval run ne likhi.
 * **Koi value hardcode nahi hai.**
 *
 * Eval kabhi chala hi na ho to routing cards "not measured" dikhate hain,
 * `0` nahi — wo do bilkul alag baatein hain aur ek eval dashboard ka pehla
 * kaam hi ye hai ki galat impression na de.
 */
const CARDS = [
  {
    key: "documents",
    label: "Documents",
    sub: "Ingested in knowledge base",
    tone: "indigo",
    icon: (p) => (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" {...p}>
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <path d="M14 2v6h6" />
      </svg>
    ),
  },
  {
    key: "chunks",
    label: "Chunks",
    sub: "Indexed in ChromaDB",
    tone: "violet",
    icon: (p) => (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" {...p}>
        <path d="M21 16V8l-9-5-9 5v8l9 5 9-5z" />
        <path d="M3.3 7.3 12 12l8.7-4.7M12 22V12" />
      </svg>
    ),
  },
  {
    key: "routing",
    label: "Routing Accuracy",
    sub: "On labelled test set",
    tone: "emerald",
    icon: (p) => (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" {...p}>
        <circle cx="12" cy="12" r="9" />
        <circle cx="12" cy="12" r="4" />
      </svg>
    ),
  },
  {
    key: "missed",
    label: "Missed Fallbacks",
    sub: "Answered locally when it shouldn't have",
    tone: "amber",
    icon: (p) => (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" {...p}>
        <path d="M13 2 3 14h9l-1 8 10-12h-9z" />
      </svg>
    ),
  },
];

const TONES = {
  indigo: "bg-indigo-50 text-indigo-600",
  violet: "bg-violet-50 text-violet-600",
  emerald: "bg-emerald-50 text-emerald-600",
  amber: "bg-amber-50 text-amber-600",
};

function valueFor(key, stats) {
  if (!stats) return "—";
  const e = stats.evaluation;
  switch (key) {
    case "documents":
      // BEIR pe backend `null` bhejta hai — wahan "documents" filesystem files
      // nahi, corpus ke abstracts hain, aur 7 dikhana jhooth hoga.
      return stats.documents ?? "—";
    case "chunks":
      return stats.chunks ?? "—";
    case "routing":
      return e ? `${e.routing_correct}/${e.routing_total}` : "not run";
    case "missed":
      return e ? e.missed_fallbacks : "not run";
    default:
      return "—";
  }
}

export default function StatCards({ stats, loading }) {
  return (
    <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
      {CARDS.map(({ key, label, sub, tone, icon: Icon }) => {
        const value = valueFor(key, stats);
        const unmeasured = value === "not run";
        return (
          <div
            key={key}
            className="flex items-start gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm"
          >
            <span className={`rounded-lg p-2 ${TONES[tone]}`}>
              <Icon className="h-5 w-5" />
            </span>
            <div className="min-w-0">
              <div
                className={`text-2xl font-bold leading-tight ${
                  loading
                    ? "animate-pulse text-slate-300"
                    : unmeasured
                      ? "text-base font-medium text-slate-400"
                      : "text-slate-900"
                }`}
              >
                {loading ? "··" : value}
              </div>
              <div className="text-sm font-medium text-slate-700">{label}</div>
              <div className="truncate text-xs text-slate-400" title={sub}>
                {unmeasured ? "Run .\dev.ps1 eval to measure" : sub}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
