import { useEffect, useRef, useState } from "react";

import Message from "./components/Message.jsx";
import Sidebar, { Logo } from "./components/Sidebar.jsx";
import SidePanel from "./components/SidePanel.jsx";
import StatCards from "./components/StatCards.jsx";
import DocumentsView from "./views/DocumentsView.jsx";
import EvaluationView from "./views/EvaluationView.jsx";
import SystemView from "./views/SystemView.jsx";
import useHistory from "./useHistory.js";

/** Fixed demo queries — `backend/data/README.md` wali, expected route ke saath.
 *  Live demo me kuch bhi type karke ummeed karna ki fallback trigger hoga, wahi
 *  galti demo todti hai. */
const SUGGESTIONS = [
  { q: "Why does chunk overlap matter when splitting documents?", route: "local" },
  { q: "Why is cosine similarity used instead of Euclidean distance?", route: "local" },
  { q: "What is the Model Context Protocol?", route: "web" },
  { q: "What is the current pricing of the Tavily search API?", route: "web" },
];

const LLM_NODES = [
  "grade_documents",
  "transform_query",
  "generate",
  "validate_guardrails",
];

/** Empty-state card explaining one of the two routes. */
function RouteHint({ tone, title, body }) {
  const styles =
    tone === "emerald"
      ? "border-emerald-200 bg-emerald-50/60 text-emerald-900"
      : "border-sky-200 bg-sky-50/60 text-sky-900";
  const dot = tone === "emerald" ? "bg-emerald-500" : "bg-sky-500";

  return (
    <div className={`rounded-lg border px-4 py-3 text-left ${styles}`}>
      <div className="flex items-center gap-2 text-sm font-medium">
        <span className={`h-2 w-2 rounded-full ${dot}`} />
        {title}
      </div>
      <p className="mt-1 text-xs opacity-80">{body}</p>
    </div>
  );
}

export default function App() {
  const [turns, setTurns] = useState([]);
  const [stats, setStats] = useState(null);
  const [loadingStats, setLoadingStats] = useState(true);
  const [busy, setBusy] = useState(false);
  // Sidebar **poora main view** switch karta hai. Pehle wo sirf right rail ka
  // ek chhota tab badalta tha, to "Evaluation" click karne pe lagta tha kuch
  // hua hi nahi — aur wo tab aksar scroll ke neeche hota tha.
  const [view, setView] = useState("chat");
  const [draft, setDraft] = useState("");
  // Har conversation ki apni id — history usi pe update hoti hai, warna ek hi
  // chat ke do turns do alag entries ban jaate.
  const [chatId, setChatId] = useState(() => Date.now().toString(36));
  const history = useHistory();
  const endRef = useRef(null);

  useEffect(() => {
    fetch("/api/stats")
      .then((r) => (r.ok ? r.json() : null))
      .then(setStats)
      .catch(() => setStats(null))
      .finally(() => setLoadingStats(false));
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns, busy]);

  const latest = [...turns].reverse().find((t) => t.role === "assistant");

  async function ask(question) {
    if (!question.trim() || busy) return;
    setDraft("");
    setBusy(true);
    setTurns((t) => [...t, { role: "user", text: question, at: Date.now() }]);

    try {
      // Relative path — dev me Vite proxy, production me Nginx handle karta hai.
      const res = await fetch("/api/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });

      if (!res.ok) {
        // Backend ka asli message dikhate hain (missing key, rate limit) —
        // generic "something went wrong" se debug karna namumkin hota hai.
        const body = await res.text();
        throw new Error(`HTTP ${res.status} — ${body.slice(0, 300)}`);
      }

      const data = await res.json();
      setTurns((t) => {
        const next = [
          ...t,
          { role: "assistant", text: data.answer, at: Date.now(), ...data },
        ];
        // Answer aane ke baad record karo, sawaal ke baad nahi — warna ek
        // adhoori entry (bina route ke) history me baith jaati.
        history.record(chatId, next);
        return next;
      });
    } catch (err) {
      setTurns((t) => [...t, { role: "error", text: err.message, at: Date.now() }]);
    } finally {
      setBusy(false);
    }
  }

  function newChat() {
    setTurns([]);
    setChatId(Date.now().toString(36));
    setView("chat");
  }

  function openPast(entry) {
    setTurns(entry.turns);
    setChatId(entry.id);
    setView("chat");
  }

  return (
    <div className="flex h-screen bg-slate-50 text-slate-900">
      <Sidebar
        active={view}
        hasChat={turns.length > 0}
        onSelect={setView}
        onNewChat={newChat}
        history={history.items}
        currentId={chatId}
        onOpen={openPast}
        onDelete={history.remove}
      />

      <main className="flex min-w-0 flex-1 flex-col overflow-y-auto">
        <header className="flex flex-wrap items-center gap-3 px-6 pb-3 pt-5">
          <div className="min-w-0 flex-1">
            <h1 className="flex items-center gap-2 text-lg font-semibold tracking-tight">
              <span className="lg:hidden">
                <Logo className="h-6 w-6" />
              </span>
              Adaptive Corrective RAG
            </h1>
            {/* Config header me hai, tagline nahi — dekhne wale ko sabse pehle
                ye jaanna hota hai ki kis corpus aur kis model pe chal raha hai. */}
            <p className="mt-0.5 font-mono text-xs text-slate-400">
              {stats
                ? `${stats.corpus} · ${stats.chunks} chunks · ${stats.config.llm_model}`
                : "connecting…"}
            </p>
          </div>

          <span
            className={`inline-flex items-center gap-2 rounded-md border px-2.5 py-1 text-xs ${
              stats
                ? "border-slate-200 bg-white text-slate-600"
                : "border-amber-200 bg-amber-50 text-amber-700"
            }`}
          >
            <span
              className={`h-1.5 w-1.5 rounded-full ${stats ? "bg-emerald-500" : "bg-amber-500"}`}
            />
            {stats ? "online" : "backend unreachable"}
          </span>

          <a
            href="https://github.com/Nitishjha7/adaptive-crag"
            target="_blank"
            rel="noopener noreferrer"
            title="Source"
            className="inline-flex items-center gap-1.5 rounded-md border border-slate-200 bg-white px-2.5 py-1 text-xs text-slate-600 transition hover:bg-slate-50"
          >
            <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="currentColor">
              <path d="M12 .5A11.5 11.5 0 0 0 .5 12a11.5 11.5 0 0 0 7.9 10.9c.6.1.8-.2.8-.6v-2c-3.2.7-3.9-1.5-3.9-1.5-.5-1.4-1.3-1.7-1.3-1.7-1-.7.1-.7.1-.7 1.1.1 1.7 1.2 1.7 1.2 1 1.7 2.7 1.2 3.4.9.1-.7.4-1.2.7-1.5-2.6-.3-5.3-1.3-5.3-5.7 0-1.3.5-2.3 1.2-3.1-.1-.3-.5-1.5.1-3.1 0 0 1-.3 3.2 1.2a11 11 0 0 1 5.8 0C17.1 4.7 18 5 18 5c.6 1.6.2 2.8.1 3.1.8.8 1.2 1.8 1.2 3.1 0 4.4-2.7 5.4-5.3 5.7.4.4.8 1.1.8 2.2v3.3c0 .4.2.7.8.6A11.5 11.5 0 0 0 23.5 12 11.5 11.5 0 0 0 12 .5z" />
            </svg>
            GitHub
          </a>
        </header>

        <div className="px-6">
          <StatCards stats={stats} loading={loadingStats} />
        </div>

        {view !== "chat" && (
          <div className="p-6">
            {view === "eval" && <EvaluationView stats={stats} />}
            {view === "documents" && <DocumentsView stats={stats} />}
            {view === "system" && <SystemView stats={stats} />}
          </div>
        )}

        <div
          className={`grid min-h-0 flex-1 grid-cols-1 gap-4 p-6 xl:grid-cols-[minmax(0,1fr)_360px] ${
            view === "chat" ? "" : "hidden"
          }`}
        >
          <section className="flex min-h-[26rem] flex-col rounded-xl border border-slate-200 bg-white">
            <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
              <div>
                <h2 className="font-semibold">Chat with CRAG</h2>
                <p className="text-sm text-slate-500">
                  Ask about the indexed documents, or anything current.
                </p>
              </div>
              {turns.length > 0 && (
                <button
                  onClick={newChat}
                  className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-600 transition hover:bg-slate-50"
                >
                  Clear Chat
                </button>
              )}
            </div>

            <div className="flex-1 space-y-5 overflow-y-auto px-5 py-5">
              {/* Khaali chat ek bada blank void tha. Ab wahi jagah batati hai ki
                  system karta kya hai — aur dono routes ka farak pehle hi dikha
                  deti hai, jo poore project ka point hai. */}
              {turns.length === 0 && !busy && (
                <div className="flex h-full flex-col items-center justify-center px-6 text-center">
                  <svg viewBox="0 0 32 32" className="h-12 w-12 opacity-70">
                    <path
                      d="M16 5 L27 26 H5 Z"
                      fill="none"
                      stroke="#6366f1"
                      strokeWidth="2"
                      strokeLinejoin="round"
                    />
                    <path d="M16 13 L21 26 H11 Z" fill="#6366f1" opacity="0.85" />
                  </svg>

                  <h3 className="mt-4 font-semibold text-slate-700">
                    Ask anything — it decides where to look
                  </h3>
                  <p className="mt-1 max-w-md text-sm text-slate-500">
                    Every question is graded before it is answered. If the indexed
                    documents genuinely cover it, you get a local answer. If they
                    don't, the system rewrites the query and searches the web.
                  </p>

                  <div className="mt-6 grid gap-3 sm:grid-cols-2">
                    <RouteHint
                      tone="emerald"
                      title="Local Documents"
                      body="Graded sufficient — no web call, 3 LLM calls."
                    />
                    <RouteHint
                      tone="sky"
                      title="Web Fallback"
                      body="Graded insufficient — query rewritten, then searched."
                    />
                  </div>

                  <p className="mt-6 text-xs text-slate-400">
                    Pick one of the four below — two of each.
                  </p>
                </div>
              )}

              {turns.map((t, i) => (
                <Message key={i} turn={t} />
              ))}

              {busy && (
                <div className="flex items-center gap-2 text-sm text-slate-400">
                  <span className="h-2 w-2 animate-pulse rounded-full bg-indigo-500" />
                  retrieve → grade → …
                </div>
              )}
              <div ref={endRef} />
            </div>

            <div className="border-t border-slate-100 px-5 py-4">
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  ask(draft);
                }}
                className="flex gap-2"
              >
                <input
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  disabled={busy}
                  placeholder="Ask a question about your documents or anything on the web…"
                  className="min-w-0 flex-1 rounded-xl border border-slate-200 bg-slate-50 px-4 py-2.5 outline-none transition focus:border-indigo-300 focus:bg-white disabled:opacity-60"
                />
                <button
                  type="submit"
                  disabled={busy || !draft.trim()}
                  className="shrink-0 rounded-xl bg-indigo-600 px-4 py-2.5 text-white transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  <svg
                    viewBox="0 0 24 24"
                    className="h-5 w-5"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.8"
                  >
                    <path d="m22 2-7 20-4-9-9-4z" />
                  </svg>
                </button>
              </form>

              <div className="mt-3 flex flex-wrap items-center gap-2">
                <span className="text-xs text-slate-400">Try asking:</span>
                {SUGGESTIONS.map(({ q, route }) => (
                  <button
                    key={q}
                    disabled={busy}
                    onClick={() => ask(q)}
                    title={`Expected route: ${route}`}
                    className="rounded-full border border-slate-200 px-3 py-1 text-xs text-slate-600 transition hover:border-slate-300 hover:bg-slate-50 disabled:opacity-40"
                  >
                    <span className={route === "web" ? "text-sky-500" : "text-emerald-500"}>
                      ●
                    </span>{" "}
                    {q.length > 40 ? q.slice(0, 40) + "…" : q}
                  </button>
                ))}
              </div>
            </div>
          </section>

          <aside className="min-w-0">
            <SidePanel latest={latest} llmNodes={LLM_NODES} />
          </aside>
        </div>
      </main>
    </div>
  );
}
