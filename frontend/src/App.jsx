import { useEffect, useRef, useState } from "react";

import Message from "./components/Message.jsx";
import Sidebar, { Logo } from "./components/Sidebar.jsx";
import SidePanel from "./components/SidePanel.jsx";
import StatCards from "./components/StatCards.jsx";

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
  const [tab, setTab] = useState("trace");
  const [draft, setDraft] = useState("");
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
      setTurns((t) => [
        ...t,
        { role: "assistant", text: data.answer, at: Date.now(), ...data },
      ]);
    } catch (err) {
      setTurns((t) => [...t, { role: "error", text: err.message, at: Date.now() }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex h-screen bg-slate-50 text-slate-900">
      <Sidebar
        active={tab}
        hasChat={turns.length > 0}
        onSelect={setTab}
        onNewChat={() => setTurns([])}
      />

      <main className="flex min-w-0 flex-1 flex-col overflow-y-auto">
        <header className="flex flex-wrap items-center gap-3 px-6 pb-4 pt-6">
          <div className="min-w-0 flex-1">
            <h1 className="flex items-center gap-2 text-2xl font-bold italic tracking-tight">
              <span className="lg:hidden">
                <Logo className="h-7 w-7" />
              </span>
              Adaptive Corrective RAG{" "}
              <span className="not-italic text-indigo-600">(CRAG)</span>
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              Self-grading RAG with web search fallback — grounded answers from your
              documents, or the live web when they fall short.
            </p>
          </div>

          <span
            className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm ${
              stats
                ? "border-slate-200 bg-white text-slate-700"
                : "border-amber-200 bg-amber-50 text-amber-700"
            }`}
          >
            <span
              className={`h-2 w-2 rounded-full ${stats ? "bg-emerald-500" : "bg-amber-500"}`}
            />
            {stats ? "System Online" : "Backend unreachable"}
          </span>

          <a
            href="https://github.com/Nitishjha7/adaptive-crag"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-700 transition hover:bg-slate-50"
          >
            <svg viewBox="0 0 24 24" className="h-4 w-4" fill="currentColor">
              <path d="M12 .5A11.5 11.5 0 0 0 .5 12a11.5 11.5 0 0 0 7.9 10.9c.6.1.8-.2.8-.6v-2c-3.2.7-3.9-1.5-3.9-1.5-.5-1.4-1.3-1.7-1.3-1.7-1-.7.1-.7.1-.7 1.1.1 1.7 1.2 1.7 1.2 1 1.7 2.7 1.2 3.4.9.1-.7.4-1.2.7-1.5-2.6-.3-5.3-1.3-5.3-5.7 0-1.3.5-2.3 1.2-3.1-.1-.3-.5-1.5.1-3.1 0 0 1-.3 3.2 1.2a11 11 0 0 1 5.8 0C17.1 4.7 18 5 18 5c.6 1.6.2 2.8.1 3.1.8.8 1.2 1.8 1.2 3.1 0 4.4-2.7 5.4-5.3 5.7.4.4.8 1.1.8 2.2v3.3c0 .4.2.7.8.6A11.5 11.5 0 0 0 23.5 12 11.5 11.5 0 0 0 12 .5z" />
            </svg>
            GitHub
          </a>
        </header>

        <div className="px-6">
          <StatCards stats={stats} loading={loadingStats} />
        </div>

        <div className="grid min-h-0 flex-1 grid-cols-1 gap-4 p-6 xl:grid-cols-[minmax(0,1fr)_360px]">
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
                  onClick={() => setTurns([])}
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
            <SidePanel
              tab={tab}
              onTab={setTab}
              latest={latest}
              stats={stats}
              llmNodes={LLM_NODES}
            />
          </aside>
        </div>
      </main>
    </div>
  );
}
