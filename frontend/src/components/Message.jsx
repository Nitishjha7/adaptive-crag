import { useState } from "react";

import Citations from "./Citations.jsx";
import TraceTimeline, { chain, llmCalls } from "./TraceTimeline.jsx";

/** One turn in the conversation.
 *
 * An assistant message carries **its whole path** with it — badge, chain,
 * trace, sources. All of that used to live in a right rail that showed only the
 * *last* answer, and half of it duplicated what Message already displayed.
 * Scrolling back in a demo to say "this one graded no, this one yes" was simply
 * not possible. Now every answer stands on its own.
 */
function CopyButton({ text }) {
  return (
    <button
      onClick={() => navigator.clipboard?.writeText(text)}
      title="Copy answer"
      className="rounded-md p-1.5 text-slate-400 transition hover:bg-ink-800 hover:text-slate-400"
    >
      <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.8">
        <rect x="9" y="9" width="13" height="13" rx="2" />
        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
      </svg>
    </button>
  );
}

function SourceBadgeInline({ sourceType }) {
  const local = sourceType === "vector_db";
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium ${
        local ? "bg-emerald-500/10 text-emerald-300" : "bg-sky-500/10 text-sky-300"
      }`}
    >
      {local ? (
        <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M20 6 9 17l-5-5" />
        </svg>
      ) : (
        <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="9" />
          <path d="M3 12h18M12 3a15 15 0 0 1 0 18a15 15 0 0 1 0-18z" />
        </svg>
      )}
      {local ? "Answered from documents" : "Answered from web search"}
    </span>
  );
}

/**
 * One line for the route and its cost, with the full trace a click away.
 *
 * The cost line names both paths. "3 calls" on its own says
 * nothing; "3, and the fallback would cost 4" is the trade-off the whole case
 * for conditional routing rests on.
 */
function TraceStrip({ logs, elapsedMs }) {
  const [open, setOpen] = useState(false);
  if (!logs?.length) return null;

  const steps = chain(logs);
  const calls = llmCalls(logs);
  const wentWeb = steps.some((s) => s.text === "web search");

  return (
    <div className="border-t border-ink-700">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full flex-wrap items-center gap-x-1.5 gap-y-1 px-4 py-2.5 text-left transition hover:bg-ink-900"
      >
        <svg
          viewBox="0 0 24 24"
          className={`h-3 w-3 shrink-0 text-slate-400 transition-transform ${open ? "rotate-90" : ""}`}
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          aria-hidden="true"
        >
          <path d="m9 6 6 6-6 6" />
        </svg>

        {steps.map((s, i) => (
          <span key={i} className="flex items-center gap-1.5">
            {i > 0 && <span className="text-slate-300">/</span>}
            <span
              className={`font-mono text-[11px] ${
                s.verdict === "no"
                  ? "font-semibold text-sky-600"
                  : s.verdict === "yes"
                    ? "font-semibold text-emerald-600"
                    : "text-slate-500"
              }`}
            >
              {s.text}
            </span>
          </span>
        ))}

        <span className="ml-auto pl-2 font-mono text-[11px] text-slate-400">
          {calls} LLM {calls === 1 ? "call" : "calls"}
          {!wentWeb && " (fallback would cost 4)"} · {(elapsedMs / 1000).toFixed(1)}s
        </span>
      </button>

      {open && (
        <div className="px-4 pb-4 pt-1">
          <TraceTimeline logs={logs} />
        </div>
      )}
    </div>
  );
}

export default function Message({ turn }) {
  if (turn.role === "user") {
    return (
      <div className="flex items-start justify-end gap-3">
        <div className="max-w-[78%] rounded-2xl rounded-tr-sm bg-brand-600 px-4 py-2.5 text-white">
          {turn.text}
        </div>
        <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-ink-700 text-slate-500">
          <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8">
            <circle cx="12" cy="8" r="4" />
            <path d="M4 21a8 8 0 0 1 16 0" />
          </svg>
        </div>
      </div>
    );
  }

  if (turn.role === "error") {
    return (
      <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-4">
        <p className="text-sm font-medium text-rose-300">Request failed</p>
        <p className="mt-1 break-words font-mono text-xs text-red-500">{turn.text}</p>
      </div>
    );
  }

  return (
    <div className="flex items-start gap-3">
      <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-brand-500/15">
        <svg viewBox="0 0 32 32" className="h-6 w-6">
          <path d="M16 7 L25 24 H7 Z" fill="none" stroke="#6366f1" strokeWidth="2.4" strokeLinejoin="round" />
          <path d="M16 14 L20.5 24 H11.5 Z" fill="#6366f1" />
        </svg>
      </div>

      <div className="min-w-0 flex-1 rounded-2xl rounded-tl-sm border border-ink-700 bg-ink-850">
        <div className="flex items-center justify-between gap-2 px-4 pt-3">
          <SourceBadgeInline sourceType={turn.source_type} />
          <CopyButton text={turn.text} />
        </div>

        <p className="whitespace-pre-wrap px-4 py-3 leading-relaxed text-slate-200">
          {turn.text}
        </p>

        {/* The rewritten query only exists on the fallback path. Showing it is
            the clearest way to make the point that the system changed the
            query itself. */}
        {turn.transformed_query && (
          <div className="mx-4 mb-3 flex gap-2 rounded-lg bg-sky-500/10 px-3 py-2 text-xs text-sky-800">
            <svg
              viewBox="0 0 24 24"
              className="mt-0.5 h-3.5 w-3.5 shrink-0"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              aria-hidden="true"
            >
              <circle cx="11" cy="11" r="7" />
              <path d="m20 20-3.5-3.5" />
            </svg>
            <span>
              Rewritten for search:{" "}
              <span className="font-mono">{turn.transformed_query}</span>
            </span>
          </div>
        )}

        {turn.sources?.length > 0 && (
          <div className="border-t border-ink-700 px-4 py-3">
            <Citations sources={turn.sources} sourceType={turn.source_type} />
          </div>
        )}

        <TraceStrip logs={turn.logs} elapsedMs={turn.elapsed_ms} />
      </div>
    </div>
  );
}
