import { useEffect, useRef, useState } from "react";

import Message from "./components/Message.jsx";
import Sidebar, { Logo } from "./components/Sidebar.jsx";
import DocumentsView from "./views/DocumentsView.jsx";
import EvaluationView from "./views/EvaluationView.jsx";
import SystemView from "./views/SystemView.jsx";
import useHistory from "./useHistory.js";

/** Fixed demo queries with their expected route. Typing something at random in
 *  a live demo and hoping the fallback fires is the mistake that breaks demos.
 *
 *  **They change with the corpus.** These used to be the concepts ones,
 *  hardcoded. Under `CORPUS=scifact` the "Why does chunk overlap matter" chip
 *  showed a green (local) dot while that document does not exist in that corpus
 *  — it actually routed to the web. The chip contradicted its own demo.
 *
 *  The SciFact queries come from `eval/results_scifact.json`: these are the
 *  cases that routed local in that run *and* retrieved their gold document.
 *  They are claims rather than questions — SciFact is claim verification. */
const SUGGESTIONS_BY_CORPUS = {
  concepts: [
    { q: "Why does chunk overlap matter when splitting documents?", route: "local" },
    { q: "Why is cosine similarity used instead of Euclidean distance?", route: "local" },
    { q: "What is the Model Context Protocol?", route: "web" },
    { q: "What is the current pricing of the Tavily search API?", route: "web" },
  ],
  scifact: [
    { q: "ALDH1 expression is associated with poorer prognosis in breast cancer.", route: "local" },
    { q: "Febrile seizures reduce the threshold for development of epilepsy.", route: "local" },
    { q: "What is the current pricing of the Groq API per million tokens?", route: "web" },
    { q: "Which chat models are available on Groq today?", route: "web" },
  ],
};

/**
 * The view lives in the URL hash, not only in React state.
 *
 * `view` used to be a plain useState. Open Evaluation, refresh, and the app
 * silently back to Chat — no error, just lost work. The browser's back button
 * did nothing either, and there was no way to send someone a link to a page.
 *
 * Hash rather than path: a hash never reaches the server, so Nginx needs no
 * SPA-fallback rule. With path routing, refreshing on `/eval` would 404, because
 * no such file exists.
 */
const VIEWS = ["chat", "documents", "eval", "system"];

function viewFromHash() {
  const v = window.location.hash.replace(/^#\/?/, "");
  return VIEWS.includes(v) ? v : "chat";
}

export default function App() {
  const [turns, setTurns] = useState([]);
  const [stats, setStats] = useState(null);
  const [busy, setBusy] = useState(false);
  // The sidebar switches the **whole main view**. It used to change a small tab
  // inside the right rail, so clicking "Evaluation" looked like nothing had
  // happened — and that tab was often below the fold.
  // First render from the hash, or Chat flashes for a frame and then jumps.
  const [view, setView] = useState(viewFromHash);
  const [draft, setDraft] = useState("");
  // Each conversation has its own id; history updates on it, otherwise two
  // turns of the same chat would become two separate history entries.
  const [chatId, setChatId] = useState(() => Date.now().toString(36));
  const history = useHistory();
  const endRef = useRef(null);

  useEffect(() => {
    fetch("/api/stats")
      .then((r) => (r.ok ? r.json() : null))
      .then(setStats)
      .catch(() => setStats(null));
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns, busy]);

  // View -> URL. `chat` is the default, so its hash stays empty — otherwise
  // "#chat" sticks to the landing URL for no reason.
  //
  // `pushState`, not `replaceState`: replace fixes refresh but creates no
  // history entry, so the back button cannot move between views. For nav clicks,
  // creating a history entry is the correct behaviour.
  useEffect(() => {
    const want = view === "chat" ? "" : `#${view}`;
    if (window.location.hash !== want) {
      window.history.pushState(null, "", want || window.location.pathname);
    }
  }, [view]);

  // URL -> view. Listen to `popstate`, not `hashchange`: back/forward over
  // pushState navigation fires popstate, and a hash change fires it too, so one
  // listener covers both cases.
  useEffect(() => {
    const onPop = () => setView(viewFromHash());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  async function ask(question) {
    if (!question.trim() || busy) return;
    setDraft("");
    setBusy(true);
    setTurns((t) => [...t, { role: "user", text: question, at: Date.now() }]);

    try {
      // Relative path — Vite proxies it in dev, Nginx in production.
      const res = await fetch("/api/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });

      if (!res.ok) {
        // Show the backend's real message (missing key, rate limit). A generic
        // "something went wrong" makes debugging impossible.
        const body = await res.text();
        throw new Error(`HTTP ${res.status} — ${body.slice(0, 300)}`);
      }

      const data = await res.json();
      setTurns((t) => {
        const next = [
          ...t,
          { role: "assistant", text: data.answer, at: Date.now(), ...data },
        ];
        // Record after the answer arrives, not after the question — otherwise a
        // half-finished entry with no route sits in the history.
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
            {/* Config in the header rather than a tagline — the first thing a
                viewer wants is which corpus and which model this is running. */}
            <p className="mt-0.5 font-mono text-xs text-slate-400">
              {stats
                ? `${stats.corpus} · ${stats.chunks} chunks · ${stats.config.llm_model}`
                : "connecting…"}
            </p>
          </div>

          {/* Saying "online" when the backend is up says nothing — the header
              line already comes from the backend, which is the proof. Saying so
              when it is down does matter, so this only renders then. */}
          {!stats && (
            <span className="inline-flex items-center gap-2 rounded-md border border-amber-200 bg-amber-50 px-2.5 py-1 text-xs text-amber-700">
              <span className="h-1.5 w-1.5 rounded-full bg-amber-500" />
              backend unreachable
            </span>
          )}

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

        {view !== "chat" && (
          <div className="p-6">
            {view === "eval" && <EvaluationView stats={stats} />}
            {view === "documents" && <DocumentsView stats={stats} />}
            {view === "system" && <SystemView stats={stats} />}
          </div>
        )}

        <div
          className={`flex min-h-0 flex-1 flex-col p-6 ${
            view === "chat" ? "" : "hidden"
          }`}
        >
          {/* Rail hatne ke baad chat poori chaudai le rahi thi — 1400px ki line
              is not readable. The column is capped at a reading width. */}
          <section
            className={`mx-auto flex w-full max-w-4xl flex-col rounded-xl border border-slate-200 bg-white ${
              turns.length || busy ? "min-h-[26rem] flex-1" : ""
            }`}
          >
            <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
              <h2 className="font-semibold">Chat</h2>
              {turns.length > 0 && (
                <button
                  onClick={newChat}
                  className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-600 transition hover:bg-slate-50"
                >
                  Clear chat
                </button>
              )}
            </div>

            <div
              className={`space-y-5 overflow-y-auto px-5 ${
                turns.length || busy ? "flex-1 py-5" : "pt-5"
              }`}
            >
              {/* There used to be a lecture here — explainer cards for both
                  routes and "pick one of the four below". All of that is already
                  in the chips below and in each answer's trace; saying it twice
                  is what made the UI feel padded and generated. */}
              {turns.length === 0 && !busy && (
                <p className="text-sm leading-relaxed text-slate-400">
                  Every question is graded before it is answered. Ask one, then open
                  the trace under the answer to see which way it went.
                </p>
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
                {(SUGGESTIONS_BY_CORPUS[stats?.corpus] ??
                  SUGGESTIONS_BY_CORPUS.concepts).map(({ q, route }) => (
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
        </div>
      </main>
    </div>
  );
}
