/** Left navigation rail.
 *
 * Nav items are only the ones that **actually show something**. Screens that do
 * not exist (document upload, settings) are marked `soon: true` and disabled —
 * a dead link that someone clicks during a demo is worse than no link.
 */
// `id` has to match App's `view` exactly. This used to say "evaluation" while
// App expected "eval" — the nav click did nothing at all, with no error. So both
// sides now use one vocabulary.
//
// "New chat" is not in this list: it is an **action**, not a tab. Styling them
// the same made two things look highlighted at once.
const NAV = [
  { id: "chat", label: "Chat", icon: ListIcon },
  { id: "documents", label: "Documents", icon: DocIcon },
  { id: "eval", label: "Evaluation", icon: ChartIcon },
  { id: "system", label: "System Status", icon: PulseIcon },
];

function ChatIcon(p) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" {...p}>
      <path d="M21 11.5a8.4 8.4 0 0 1-9 8.4 9.9 9.9 0 0 1-4-.8L3 21l1.9-4.6A8.4 8.4 0 0 1 12 3.1a8.4 8.4 0 0 1 9 8.4z" />
    </svg>
  );
}
function DocIcon(p) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" {...p}>
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <path d="M14 2v6h6" />
    </svg>
  );
}
function ChartIcon(p) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" {...p}>
      <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />
    </svg>
  );
}
function ListIcon(p) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" {...p}>
      <path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01" />
    </svg>
  );
}
function PulseIcon(p) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" {...p}>
      <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
    </svg>
  );
}

function relative(ts) {
  const mins = Math.round((Date.now() - ts) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.round(hrs / 24)}d ago`;
}

export default function Sidebar({
  active,
  onSelect,
  onNewChat,
  history = [],
  currentId,
  onOpen,
  onDelete,
}) {
  return (
    <aside className="hidden w-64 shrink-0 flex-col bg-[#0f1729] text-slate-300 lg:flex">
      <div className="flex items-center gap-2.5 px-4 pb-5 pt-5">
        <Logo className="h-7 w-7" />
        <div className="text-base font-semibold leading-none text-white">CRAG</div>
      </div>

      <div className="px-3 pb-3">
        <button
          onClick={onNewChat}
          // This used to be disabled on `!hasChat`, which was wrong: the button
          // has two jobs — clear the chat *and* return to the Chat view. Standing
          // on Documents or Evaluation with an empty chat, clicking it did
          // nothing at all. On an empty chat the clear is a harmless no-op, but
          // the view still lands where it should.
          className="flex w-full items-center justify-center gap-2 rounded-md bg-indigo-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-indigo-500"
        >
          <ChatIcon className="h-4 w-4" />
          New chat
        </button>
      </div>

      <nav className="space-y-0.5 px-3">
        {NAV.map(({ id, label, icon: Icon, soon }) => {
          const isActive = active === id;
          return (
            <button
              key={id}
              disabled={soon}
              onClick={() => onSelect(id)}
              title={soon ? "Not built — there is no upload API yet" : undefined}
              // The active tab must look **different** from the "New chat"
              // button. Both were solid indigo, so two things read as primary at
              // once and it was unclear which one was actionable.
              className={`flex w-full items-center gap-2.5 rounded-md px-3 py-1.5 text-sm transition ${
                isActive
                  ? "bg-white/10 font-medium text-white"
                  : soon
                    ? "cursor-not-allowed text-slate-600"
                    : "text-slate-400 hover:bg-white/5 hover:text-slate-200"
              }`}
            >
              <Icon className="h-4 w-4" />
              {label}
              {soon && <span className="ml-auto text-[10px] uppercase">soon</span>}
            </button>
          );
        })}
      </nav>

      {/* A promo card used to sit here ("RAG + Web Search / Smarter Answers").
          Marketing copy took up space in a dev tool and told you nothing. The
          space now holds something useful: past queries, with their route
          badge. */}
      <div className="mt-5 flex min-h-0 flex-1 flex-col px-3">
        <div className="flex items-center justify-between px-1 pb-1.5">
          <span className="text-[11px] font-medium uppercase tracking-wide text-slate-500">
            Recent
          </span>
          {history.length > 0 && (
            <span className="text-[10px] text-slate-600">{history.length}</span>
          )}
        </div>

        {history.length === 0 ? (
          <p className="px-1 text-xs leading-relaxed text-slate-600">
            Past queries appear here.
          </p>
        ) : (
          <ul className="-mr-1 min-h-0 flex-1 space-y-0.5 overflow-y-auto pr-1">
            {history.map((h) => (
              <li key={h.id} className="group relative">
                <button
                  onClick={() => onOpen(h)}
                  className={`w-full rounded-md py-1.5 pl-2 pr-7 text-left transition ${
                    h.id === currentId ? "bg-white/10" : "hover:bg-white/5"
                  }`}
                >
                  <div className="flex items-center gap-1.5">
                    {/* Route badge — one glance says whether that query took
                        the correction path. */}
                    <span
                      className={`h-1.5 w-1.5 shrink-0 rounded-full ${
                        h.route === "web_search" ? "bg-sky-400" : "bg-emerald-400"
                      }`}
                      title={h.route === "web_search" ? "Web fallback" : "Local documents"}
                    />
                    <span className="truncate text-[13px] text-slate-300">
                      {h.title}
                    </span>
                  </div>
                  <span className="ml-3 text-[10px] text-slate-600">
                    {relative(h.at)}
                  </span>
                </button>

                <button
                  onClick={() => onDelete(h.id)}
                  title="Remove"
                  className="absolute right-1 top-1.5 rounded p-1 text-slate-600 opacity-0 transition hover:text-slate-300 group-hover:opacity-100"
                >
                  <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M18 6 6 18M6 6l12 12" />
                  </svg>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* This line is deliberate. History is a **log**, not memory — the graph
          is stateless and a follow-up does not use the previous context. Without
          it the UI would be making a claim that is not true. */}
      <p className="border-t border-white/5 px-4 py-3 text-[10px] leading-relaxed text-slate-600">
        Stored in this browser only. Each query runs independently — history is a
        record, not conversation memory.
      </p>
    </aside>
  );
}

function Logo({ className = "h-9 w-9" }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden="true">
      <defs>
        <linearGradient id="crag-g" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#818cf8" />
          <stop offset="100%" stopColor="#6366f1" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="9" fill="url(#crag-g)" opacity="0.18" />
      <path d="M16 6 L26 25 H6 Z" fill="none" stroke="url(#crag-g)" strokeWidth="2.2" strokeLinejoin="round" />
      <path d="M16 13 L21 25 H11 Z" fill="url(#crag-g)" opacity="0.85" />
    </svg>
  );
}

export { Logo };
