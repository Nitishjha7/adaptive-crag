/**
 * Answer kis source se bana — filenames (local path) ya URLs (web path).
 *
 * Badge batata hai *kaunsa route* liya gaya; ye batata hai *kaunse documents*
 * use hue. Dono chahiye: badge ke bina route invisible hai, iske bina user
 * verify nahi kar sakta.
 *
 * Web URLs clickable hain, local filenames nahi — wo container ke andar ki
 * files hain, unka koi URL nahi hai.
 */
function isUrl(source) {
  return source.startsWith("http://") || source.startsWith("https://");
}

/** URL se sirf domain — poora URL layout todta hai aur padhne me kuch deta nahi. */
function label(source) {
  if (!isUrl(source)) return source;
  try {
    return new URL(source).hostname.replace(/^www\./, "");
  } catch {
    return source;
  }
}

export default function Citations({ sources }) {
  if (!sources?.length) return null;

  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/50 p-4">
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
        Sources
      </h3>

      <ul className="space-y-1">
        {sources.map((source) => (
          <li key={source} className="font-mono text-xs">
            {isUrl(source) ? (
              <a
                href={source}
                target="_blank"
                // noreferrer bhi — warna target=_blank se khuli tab
                // window.opener ke through wapas pahunch sakti hai.
                rel="noopener noreferrer"
                title={source}
                className="text-sky-400 underline decoration-sky-400/30 underline-offset-2 hover:text-sky-300"
              >
                {label(source)}
              </a>
            ) : (
              <span className="text-slate-400">{source}</span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
