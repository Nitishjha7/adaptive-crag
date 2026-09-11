import { useEffect, useState } from "react";

/**
 * Kya kya index me hai.
 *
 * Ye view isliye zaroori hai ki poore project ka faisla — "local context kaafi
 * hai ya nahi" — is list par khada hai. Wo dikhaye bina grader ka verdict ek
 * black box lagta hai; list dikhne ke baad user khud dekh sakta hai ki fallback
 * kyun trigger hua.
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
      <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-sm text-red-700">
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

      {/* Ye baat sabse zaroori hai aur isliye list ke upar hai: gap jaan-boojh ke
          hai. Iske bina koi soch sakta hai ki corpus adhoora hai. */}
      {isConcepts && (
        <div className="rounded-xl border border-amber-200 bg-amber-50/60 p-4">
          <h4 className="text-sm font-semibold text-slate-800">
            This corpus has a deliberate hole in it
          </h4>
          <p className="mt-1.5 text-sm leading-relaxed text-slate-600">
            No vendor pricing, no product names, no recent releases — so questions
            about live facts <em>have</em> to fall back to the web. Without a known
            gap the correction path could only fire by luck, and a demo that depends
            on luck is not a demo.
          </p>
        </div>
      )}

      <ul className="divide-y divide-slate-100 overflow-hidden rounded-xl border border-slate-200 bg-white">
        {data.documents.map((d) => (
          <li key={d.id} className="flex items-center gap-3 px-4 py-3">
            <FileIcon className="h-4 w-4 shrink-0 text-slate-400" />
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm font-medium capitalize text-slate-800">
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
