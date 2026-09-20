import { useRef, useState } from "react";

/**
 * Drag-and-drop for the visitor's own documents.
 *
 * Once anything is uploaded the chat answers from it instead of the built-in
 * corpus, and the banner says so - otherwise a question answered from a fresh
 * PDF looks identical to one answered from the shipped documents, and the
 * demo's whole point is that you can see which source was used.
 */
export default function UploadPanel({ uploads, compact = false }) {
  const [dragging, setDragging] = useState(false);
  const input = useRef(null);

  async function take(fileList) {
    const file = fileList?.[0];
    if (!file) return;
    try {
      await uploads.upload(file);
    } catch {
      // The hook already surfaced the message; nothing to add here.
    }
  }

  if (compact && uploads.files.length) {
    return (
      <div
        className={`flex flex-wrap items-center gap-2 rounded-lg border px-3 py-2 ${
          uploads.active
            ? "border-brand-500/30 bg-brand-500/10"
            : "border-ink-700 bg-ink-900"
        }`}
      >
        <span
          className={`text-xs font-medium ${
            uploads.active ? "text-brand-400" : "text-slate-500"
          }`}
        >
          {uploads.active
            ? `Answering from your ${uploads.files.length === 1 ? "document" : "documents"}`
            : "Your documents are switched off"}
        </span>
        <span className="font-mono text-[11px] text-slate-400">
          {uploads.files.map((f) => f.id).join(", ")}
        </span>
        <button
          onClick={() => uploads.setActive(!uploads.active)}
          className="ml-auto text-[11px] text-slate-500 transition hover:text-slate-300"
        >
          {uploads.active ? "use built-in instead" : "use my documents"}
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          take(e.dataTransfer.files);
        }}
        onClick={() => input.current?.click()}
        className={`cursor-pointer rounded-xl border border-dashed px-4 py-6 text-center transition ${
          dragging
            ? "border-brand-500 bg-brand-500/10"
            : "border-ink-600 bg-ink-900/60 hover:border-ink-600 hover:bg-ink-800/60"
        }`}
      >
        <input
          ref={input}
          type="file"
          accept=".pdf,.md,.txt"
          className="hidden"
          onChange={(e) => {
            take(e.target.files);
            e.target.value = "";
          }}
        />

        {uploads.busy ? (
          <div className="flex items-center justify-center gap-2.5">
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-brand-500/30 border-t-brand-400" />
            <span className="text-sm text-slate-300">
              Parsing and embedding&hellip;
            </span>
          </div>
        ) : (
          <>
            <p className="text-sm font-medium text-slate-200">
              Drop a PDF here to ask questions about it
            </p>
            <p className="mt-1 text-xs text-slate-500">
              Up to 400 pages. Nothing leaves this browser session.
            </p>
          </>
        )}
      </div>

      {uploads.error && (
        <p className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-300">
          {uploads.error}
        </p>
      )}

      {uploads.files.length > 0 && (
        <>
          <ul className="divide-y divide-ink-700/60 overflow-hidden rounded-lg border border-ink-700 bg-ink-850">
            {uploads.files.map((f) => (
              <li key={f.id} className="flex items-center gap-3 px-3 py-2">
                <span className="min-w-0 flex-1 truncate font-mono text-[11px] text-slate-300">
                  {f.id}
                </span>
                {f.chunks != null && (
                  <span className="shrink-0 rounded border border-ink-700 bg-ink-900 px-1.5 py-0.5 font-mono text-[10px] text-slate-500">
                    {f.chunks} chunks
                  </span>
                )}
              </li>
            ))}
          </ul>

          {/* Two separate actions, because they are different intentions:
              switching off keeps the file indexed, removing deletes it. */}
          <div className="flex items-center gap-3 text-[11px]">
            <button
              onClick={() => uploads.setActive(!uploads.active)}
              className="text-slate-400 transition hover:text-slate-200"
            >
              {uploads.active ? "Use the built-in documents instead" : "Use my documents"}
            </button>
            <button
              onClick={uploads.remove}
              className="ml-auto text-slate-500 transition hover:text-rose-300"
            >
              Remove
            </button>
          </div>
        </>
      )}
    </div>
  );
}
