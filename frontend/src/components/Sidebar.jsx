/** Left navigation rail.
 *
 * Nav items sirf wo hain jo **sach me kuch dikhate hain**. Jo screens abhi nahi
 * hain (Documents upload, Settings) unhe `soon: true` mark kiya hai aur wo
 * disabled hain — ek dead link daal ke demo me uspe click ho jaana usse bura hai.
 */
const NAV = [
  { id: "chat", label: "New Chat", icon: ChatIcon },
  { id: "evaluation", label: "Evaluation", icon: ChartIcon },
  { id: "system", label: "System Status", icon: PulseIcon },
  { id: "documents", label: "Documents", icon: DocIcon, soon: true },
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
function PulseIcon(p) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" {...p}>
      <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
    </svg>
  );
}

export default function Sidebar({ active, onSelect, onNewChat }) {
  return (
    <aside className="hidden w-64 shrink-0 flex-col bg-[#0f1729] text-slate-300 lg:flex">
      <div className="flex items-center gap-3 px-6 pb-6 pt-7">
        <Logo />
        <div>
          <div className="text-xl font-bold leading-none text-white">CRAG</div>
          <div className="mt-1 text-[11px] text-slate-400">Verify. Adapt. Answer.</div>
        </div>
      </div>

      <nav className="space-y-1 px-3">
        {NAV.map(({ id, label, icon: Icon, soon }) => {
          const isActive = active === id;
          return (
            <button
              key={id}
              disabled={soon}
              onClick={() => (id === "chat" ? onNewChat() : onSelect(id))}
              title={soon ? "Not built — there is no upload API yet" : undefined}
              className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition ${
                isActive
                  ? "bg-indigo-600 font-medium text-white"
                  : soon
                    ? "cursor-not-allowed text-slate-600"
                    : "text-slate-300 hover:bg-white/5"
              }`}
            >
              <Icon className="h-[18px] w-[18px]" />
              {label}
              {soon && <span className="ml-auto text-[10px] uppercase">soon</span>}
            </button>
          );
        })}
      </nav>

      <div className="mx-4 mt-8 overflow-hidden rounded-xl bg-gradient-to-b from-indigo-950/80 to-slate-900 p-4 ring-1 ring-white/10">
        <div className="text-sm font-semibold leading-snug text-white">
          RAG + Web Search
          <br />
          Smarter Answers
        </div>
        <p className="mt-2 text-xs leading-relaxed text-slate-400">
          Self-grading. Self-correcting. Only searches the web when the local
          context genuinely can't answer.
        </p>
      </div>

      <div className="mt-auto px-6 pb-6 pt-8 text-[11px] text-slate-500">
        <p className="italic leading-relaxed">
          “Grade the context before you trust it.”
        </p>
        <div className="mt-3">v0.9.0</div>
      </div>
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
