import Citations from "./Citations.jsx";

/** One turn in the conversation.
 *
 * Assistant messages carry the badge that is the entire point of the project:
 * did this answer come from the local corpus, or did the system decide the
 * corpus was insufficient and go to the web?
 */
function CopyButton({ text }) {
  return (
    <button
      onClick={() => navigator.clipboard?.writeText(text)}
      title="Copy answer"
      className="rounded-md p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600"
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
        local ? "bg-emerald-50 text-emerald-700" : "bg-sky-50 text-sky-700"
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
      {local ? "Answered from Documents" : "Answered from Web Search"}
    </span>
  );
}

export default function Message({ turn }) {
  const time = new Date(turn.at).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });

  if (turn.role === "user") {
    return (
      <div className="flex items-start justify-end gap-3">
        <div className="max-w-[78%]">
          <div className="rounded-2xl rounded-tr-sm bg-indigo-600 px-4 py-2.5 text-white">
            {turn.text}
          </div>
          <div className="mt-1 text-right text-[11px] text-slate-400">{time}</div>
        </div>
        <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-slate-200 text-slate-500">
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
      <div className="rounded-xl border border-red-200 bg-red-50 p-4">
        <p className="text-sm font-medium text-red-700">Request failed</p>
        <p className="mt-1 break-words font-mono text-xs text-red-500">{turn.text}</p>
      </div>
    );
  }

  return (
    <div className="flex items-start gap-3">
      <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-indigo-100">
        <svg viewBox="0 0 32 32" className="h-6 w-6">
          <path d="M16 7 L25 24 H7 Z" fill="none" stroke="#6366f1" strokeWidth="2.4" strokeLinejoin="round" />
          <path d="M16 14 L20.5 24 H11.5 Z" fill="#6366f1" />
        </svg>
      </div>

      <div className="min-w-0 flex-1 rounded-2xl rounded-tl-sm border border-slate-200 bg-white">
        <div className="flex items-center justify-between gap-2 px-4 pt-3">
          <SourceBadgeInline sourceType={turn.source_type} />
          <CopyButton text={turn.text} />
        </div>

        <p className="whitespace-pre-wrap px-4 py-3 leading-relaxed text-slate-700">
          {turn.text}
        </p>

        {/* Rewritten query sirf fallback path pe hoti hai. Ise dikhana wo point
            sabse saaf banata hai ki system ne khud query badli. */}
        {turn.transformed_query && (
          <div className="mx-4 mb-3 flex gap-2 rounded-lg bg-sky-50 px-3 py-2 text-xs text-sky-800">
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

        <div className="flex items-center gap-3 px-4 pb-3 text-[11px] text-slate-400">
          <span>{time}</span>
          <span>·</span>
          <span>{turn.elapsed_ms} ms</span>
          <span>·</span>
          <span>grade: {turn.relevance_score}</span>
        </div>

        {turn.sources?.length > 0 && (
          <div className="border-t border-slate-100 px-4 py-3">
            <Citations sources={turn.sources} sourceType={turn.source_type} />
          </div>
        )}
      </div>
    </div>
  );
}
