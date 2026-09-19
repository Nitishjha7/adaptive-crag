import { useEffect, useState } from "react";

/**
 * What is in the index.
 *
 * This view matters because the project's central decision — "is the local
 * context sufficient?" — rests on this list. Without showing it, the grader's
 * verdict looks like a black box; with it, anyone can see for themselves why the
 * fallback fired.
 */
function FileIcon(p) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" {...p}>
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <path d="M14 2v6h6" />
    </svg>
  );
}

function formatBytes(n) {
  if (n == null) return null;
  return n < 1024 ? `${n} B` : `${(n / 1024).toFixed(1)} KB`;
}

export default function DocumentsView({ stats }) {
  const [data, setData] = useState(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    fetch("/api/documents")
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then(setData)
      .catch(() => setFailed(true));
  }, []);

  if (failed) {
    return (
      <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-6 text-sm text-rose-300">
        Could not load the document list — is the backend running?
      </div>
    );
  }

  if (!data) {
    return <div className="animate-pulse text-sm text-slate-400">Loading documents…</div>;
  }

  const isConcepts = data.corpus === "concepts";

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-lg font-semibold">Knowledge base</h2>
        <p className="mt-1 text-sm text-slate-500">
          {data.total ?? data.documents.length} document
          {(data.total ?? data.documents.length) === 1 ? "" : "s"} ·{" "}
          {stats?.chunks ?? "?"} chunks · corpus{" "}
          <span className="font-mono">{data.corpus}</span>
        </p>
      </div>

      {/* Each corpus is shown with its **purpose**, which matters more than the
          list itself. Only concepts had a note before; SciFact dropped 500
          abstracts on the page with no framing, which read as data for its own
          sake. The two corpora exist for different reasons, and that reason is
          the thing worth saying. */}
      {isConcepts ? (
        <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4">
          <h4 className="text-sm font-semibold text-slate-100">
            This corpus has a deliberate hole in it
          </h4>
          <p className="mt-1.5 text-sm leading-relaxed text-slate-400">
            No vendor pricing, no product names, no recent releases — so questions
            about live facts <em>have</em> to fall back to the web. Without a known
            gap the correction path could only fire by luck, and a demo that depends
            on luck is not a demo.
          </p>
        </div>
      ) : (
        <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4">
          <h4 className="text-sm font-semibold text-slate-100">
            This corpus exists because the other one had no ground truth
          </h4>
          <p className="mt-1.5 text-sm leading-relaxed text-slate-400">
            SciFact is a BEIR benchmark, so it ships{" "}
            <span className="font-mono">qrels</span> — expert judgements of which
            abstract answers which claim. That makes retrieval{" "}
            <em>measurable</em> instead of merely plausible. On the hand-written
            corpus routing sat at 100% and no retrieval change could be justified;
            here the score has room to move.
          </p>
        </div>
      )}

      <ul className="divide-y divide-ink-700 overflow-hidden rounded-xl border border-ink-700 bg-ink-850">
        {data.documents.map((d) => (
          <li key={d.id} className="flex items-center gap-3 px-4 py-3">
            <FileIcon className="h-4 w-4 shrink-0 text-slate-400" />
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm font-medium capitalize text-slate-100">
                {d.title || d.id}
              </div>
              <div className="truncate font-mono text-xs text-slate-400">{d.id}</div>
            </div>
            {formatBytes(d.bytes) && (
              <span className="shrink-0 text-xs text-slate-400">
                {formatBytes(d.bytes)}
              </span>
            )}
          </li>
        ))}
      </ul>

      {data.truncated && (
        <p className="text-xs text-slate-400">
          Showing the first {data.documents.length} of {data.total}.
        </p>
      )}

    </div>
  );
}
