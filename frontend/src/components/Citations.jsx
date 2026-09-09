/**
 * Answer kis source se bana — filenames (local) ya URLs (web).
 *
 * Badge batata hai *kaunsa route* liya; ye batata hai *kaunse documents* use
 * hue. Dono chahiye: badge ke bina route invisible hai, iske bina user verify
 * nahi kar sakta.
 */
function isUrl(s) {
  return s.startsWith("http://") || s.startsWith("https://");
}

/** URL se sirf domain — poora URL layout todta hai aur padhne me kuch deta nahi. */
function label(s) {
  if (!isUrl(s)) return s;
  try {
    return new URL(s).hostname.replace(/^www\./, "");
  } catch {
    return s;
  }
}

function FileIcon(p) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" {...p}>
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <path d="M14 2v6h6" />
    </svg>
  );
}

function LinkIcon(p) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" {...p}>
      <path d="M10 13a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1" />
      <path d="M14 11a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1" />
    </svg>
  );
}

export default function Citations({ sources, sourceType }) {
  if (!sources?.length) return null;
  const local = sourceType === "vector_db";

  return (
    <div>
      <div className="mb-2 text-xs font-medium text-slate-500">
        Sources ({sources.length})
      </div>
      <ul className="space-y-1.5">
        {sources.map((s) => (
          <li key={s} className="flex items-center gap-2 text-xs">
            {local ? (
              <>
                <FileIcon className="h-4 w-4 shrink-0 text-slate-400" />
                <span className="truncate font-mono text-slate-600" title={s}>
                  {s}
                </span>
                <span className="ml-auto shrink-0 rounded bg-emerald-50 px-1.5 py-0.5 text-[10px] font-medium text-emerald-700">
                  Local
                </span>
              </>
            ) : (
              <>
                <LinkIcon className="h-4 w-4 shrink-0 text-sky-400" />
                <a
                  href={s}
                  target="_blank"
                  // noreferrer bhi — warna target=_blank se khuli tab
                  // window.opener ke through wapas pahunch sakti hai.
                  rel="noopener noreferrer"
                  title={s}
                  className="truncate text-sky-600 underline decoration-sky-300 underline-offset-2 hover:text-sky-700"
                >
                  {label(s)}
                </a>
                <span className="ml-auto shrink-0 rounded bg-sky-50 px-1.5 py-0.5 text-[10px] font-medium text-sky-700">
                  Web
                </span>
              </>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
