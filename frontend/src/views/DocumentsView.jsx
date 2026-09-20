import { useEffect, useState } from "react";

import UploadPanel from "../components/UploadPanel.jsx";

/**
 * The documents the system can answer from, and the place to add your own.
 *
 * This page exists because the project's central decision - "is what we
 * retrieved good enough?" - only makes sense if you can see what was available
 * to retrieve. A grader saying `no` looks arbitrary until you can check that
 * the answer genuinely was not in these files.
 *
 * Chunk counts rather than byte sizes: the chunk is the unit the retriever
 * scores, so it is the number that explains a retrieval result. A file size
 * explains nothing.
 */

function FileIcon(p) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" {...p}>
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <path d="M14 2v6h6" />
    </svg>
  );
}

/**
 * One row, expandable to the document's text.
 *
 * Reading the source matters here specifically: the grader's `no` is the
 * project's central decision, and it can only be checked by someone who can see
 * what the grader saw. Fetched on open rather than up front, so listing seven
 * files does not pull seven documents nobody asked for.
 */
function DocRow({ doc, corpus }) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState(null);
  const [failed, setFailed] = useState(false);

  function toggle() {
    const next = !open;
    setOpen(next);
    if (next && text === null && !failed) {
      const q = corpus ? `?corpus=${encodeURIComponent(corpus)}` : "";
      fetch(`/api/documents/${encodeURIComponent(doc.id)}${q}`)
        .then((r) => (r.ok ? r.json() : Promise.reject()))
        .then((d) => setText(d.text))
        .catch(() => setFailed(true));
    }
  }

  return (
    <li>
      <button
        onClick={toggle}
        className="flex w-full items-center gap-3 px-4 py-3 text-left transition hover:bg-ink-800/60"
      >
        <FileIcon className="h-4 w-4 shrink-0 text-slate-500" />
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm capitalize text-slate-200">
            {doc.title || doc.id}
          </span>
          <span className="block truncate font-mono text-[11px] text-slate-500">
            {doc.id}
          </span>
        </span>
        {doc.chunks != null && (
          <span className="shrink-0 rounded-md border border-ink-700 bg-ink-900 px-2 py-0.5 font-mono text-[11px] text-slate-400">
            {doc.chunks} chunk{doc.chunks === 1 ? "" : "s"}
          </span>
        )}
        <span
          className={`shrink-0 text-slate-600 transition ${open ? "rotate-90" : ""}`}
          aria-hidden="true"
        >
          &rsaquo;
        </span>
      </button>

      {open && (
        <pre className="max-h-80 overflow-auto whitespace-pre-wrap border-t border-ink-700 bg-ink-900 px-4 py-3 text-[11px] leading-relaxed text-slate-400">
          {failed ? "Could not read this document." : (text ?? "Loading…")}
        </pre>
      )}
    </li>
  );
}

function DocList({ documents, empty, corpus }) {
  if (!documents?.length) {
    return (
      <p className="rounded-xl border border-dashed border-ink-700 px-4 py-6 text-center text-xs text-slate-500">
        {empty}
      </p>
    );
  }
  return (
    <ul className="divide-y divide-ink-700/60 overflow-hidden rounded-xl border border-ink-700 bg-ink-850">
      {documents.map((d) => (
        <DocRow key={d.id} doc={d} corpus={corpus} />
      ))}
    </ul>
  );
}

export default function DocumentsView({ stats, uploads }) {
  const [builtIn, setBuiltIn] = useState(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    fetch("/api/documents")
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then(setBuiltIn)
      .catch(() => setFailed(true));
  }, []);

  if (failed) {
    return (
      <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-6 text-sm text-amber-300">
        Backend unreachable &mdash; start it with{" "}
        <span className="font-mono">docker compose up</span>.
      </div>
    );
  }

  // "in use" has to follow what the chat actually queries, which is the corpus
  // the hook exposes - not merely whether a file was ever uploaded.
  const usingUploads = Boolean(uploads?.corpus);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-white">Documents</h2>
        <p className="mt-1 text-sm text-slate-500">
          What questions are answered from. Anything not in here has to come from
          the web.
        </p>
      </div>

      {/* Upload first: it is the only thing on this page a visitor can act on,
          and it is what decides which of the two lists below is in use. */}
      <section className="space-y-3">
        <div className="flex items-baseline gap-2">
          <h3 className="text-sm font-medium text-white">Your documents</h3>
          {usingUploads && (
            <span className="rounded-md border border-brand-500/30 bg-brand-500/10 px-2 py-0.5 text-[11px] text-brand-400">
              in use
            </span>
          )}
        </div>
        {uploads && <UploadPanel uploads={uploads} />}
      </section>

      <section className="space-y-3">
        <div className="flex items-baseline gap-2">
          <h3 className="text-sm font-medium text-white">Built in</h3>
          {!usingUploads && (
            <span className="rounded-md border border-brand-500/30 bg-brand-500/10 px-2 py-0.5 text-[11px] text-brand-400">
              in use
            </span>
          )}
          <span className="ml-auto text-xs text-slate-500">
            {builtIn?.documents?.length ?? "—"} files ·{" "}
            {stats?.chunks ?? "—"} chunks
          </span>
        </div>

        {/* The gap is the point: without a known hole the correction path could
            only fire by luck, and a demo that depends on luck is not a demo. */}
        <p className="rounded-xl border border-ink-700 bg-ink-900/60 px-4 py-3 text-xs leading-relaxed text-slate-400">
          These seven cover RAG and agent concepts only. No pricing, no product
          names, no recent releases, so anything about live facts has to come from
          the web.
        </p>

        <DocList
          documents={builtIn?.documents}
          corpus=""
          empty={builtIn ? "No documents indexed." : "Loading…"}
        />
      </section>
    </div>
  );
}
