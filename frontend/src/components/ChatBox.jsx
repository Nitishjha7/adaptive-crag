import { useState } from "react";

/**
 * Query input + fixed demo queries.
 *
 * Demo queries hardcoded hain jaan-boojh ke: ye backend/data/README.md wali
 * paanchon queries hain jinka expected route pata hai. Live demo me kuch bhi
 * type karke ummeed karna ki fallback trigger hoga — wahi galti hai jo demo
 * todti hai.
 */
const DEMO_QUERIES = [
  { q: "Why does chunk overlap matter when splitting documents?", route: "local" },
  { q: "Why is cosine similarity used for text embeddings instead of Euclidean distance?", route: "local" },
  { q: "What is the Model Context Protocol and what problem does it solve?", route: "web" },
  { q: "What is the current pricing of the Tavily search API?", route: "web" },
];

export default function ChatBox({ onSubmit, loading }) {
  const [question, setQuestion] = useState("");

  function submit(e) {
    e.preventDefault();
    const trimmed = question.trim();
    if (trimmed && !loading) onSubmit(trimmed);
  }

  function useDemo(q) {
    setQuestion(q);
    if (!loading) onSubmit(q);
  }

  return (
    <div className="space-y-3">
      <form onSubmit={submit} className="flex gap-2">
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask something..."
          disabled={loading}
          className="min-w-0 flex-1 rounded-lg border border-slate-700 bg-slate-900 px-4 py-2.5 text-slate-100 placeholder-slate-600 outline-none focus:border-slate-500 disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={loading || !question.trim()}
          className="shrink-0 rounded-lg bg-slate-100 px-5 py-2.5 text-sm font-medium text-slate-900 transition hover:bg-white disabled:cursor-not-allowed disabled:opacity-40"
        >
          {loading ? "Running..." : "Ask"}
        </button>
      </form>

      <div className="flex flex-wrap gap-2">
        {DEMO_QUERIES.map(({ q, route }) => (
          <button
            key={q}
            onClick={() => useDemo(q)}
            disabled={loading}
            title={`Expected route: ${route}`}
            className="rounded-full border border-slate-800 px-3 py-1 text-left text-xs text-slate-400 transition hover:border-slate-600 hover:text-slate-200 disabled:opacity-40"
          >
            <span
              className={route === "web" ? "text-sky-400" : "text-emerald-400"}
            >
              ●
            </span>{" "}
            {q.length > 52 ? q.slice(0, 52) + "..." : q}
          </button>
        ))}
      </div>
    </div>
  );
}
