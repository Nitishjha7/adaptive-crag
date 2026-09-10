/** Left navigation rail.
 *
 * Nav items sirf wo hain jo **sach me kuch dikhate hain**. Jo screens abhi nahi
 * hain (Documents upload, Settings) unhe `soon: true` mark kiya hai aur wo
 * disabled hain — ek dead link daal ke demo me uspe click ho jaana usse bura hai.
 */
// `id` seedha SidePanel ke tab id se match karna chahiye. Pehle yahan
// "evaluation" tha jabki panel "eval" expect karta hai — nav click kuch karta
// hi nahi tha, bina kisi error ke. Isliye ab dono jagah ek hi vocabulary hai.
//
// "New Chat" is list me nahi hai: wo ek **action** hai, tab nahi. Dono ko ek
// jaisa style dene se do items ek saath highlighted dikhte the.
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

export default function Sidebar({ active, onSelect, onNewChat, hasChat }) {
  return (
    <aside className="hidden w-64 shrink-0 flex-col bg-[#0f1729] text-slate-300 lg:flex">
      <div className="flex items-center gap-3 px-6 pb-6 pt-7">
        <Logo />
        <div>
          <div className="text-xl font-bold leading-none text-white">CRAG</div>
          <div className="mt-1 text-[11px] text-slate-400">Verify. Adapt. Answer.</div>
        </div>
      </div>

      <div className="px-3 pb-4">
        <button
          onClick={onNewChat}
          disabled={!hasChat}
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-indigo-600 px-3 py-2.5 text-sm font-medium text-white transition hover:bg-indigo-500 disabled:cursor-default disabled:opacity-50"
        >
          <ChatIcon className="h-[18px] w-[18px]" />
          New Chat
        </button>
      </div>

      <nav className="space-y-1 px-3">
        {NAV.map(({ id, label, icon: Icon, soon }) => {
          const isActive = active === id;
          return (
            <button
              key={id}
              disabled={soon}
              onClick={() => onSelect(id)}
              title={soon ? "Not built — there is no upload API yet" : undefined}
              // Active tab ka style "New Chat" button se **alag** hona chahiye.
              // Pehle dono solid indigo the, to do cheezein ek saath primary
              // dikhti thi aur samajh nahi aata tha kaunsi actionable hai.
              className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition ${
                isActive
                  ? "bg-white/10 font-medium text-white ring-1 ring-inset ring-white/15"
                  : soon
                    ? "cursor-not-allowed text-slate-600"
                    : "text-slate-400 hover:bg-white/5 hover:text-slate-200"
              }`}
            >
              <Icon className="h-[18px] w-[18px]" />
              {label}
              {soon && <span className="ml-auto text-[10px] uppercase">soon</span>}
            </button>
          );
        })}
      </nav>

      {/* Promo card `mt-auto` se neeche chipak jaata hai — pehle nav ke bilkul
          neeche tha aur uske aage ek bada khaali gap dikhta tha. */}
      <div className="mt-auto space-y-4 px-4 pb-5 pt-8">
        <div className="overflow-hidden rounded-xl bg-gradient-to-b from-indigo-950/80 to-slate-900 p-4 ring-1 ring-white/10">
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

        <div className="px-2 text-[11px] text-slate-500">
          <p className="italic leading-relaxed">
            “Grade the context before you trust it.”
          </p>
          <div className="mt-2">v0.9.0</div>
        </div>
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
