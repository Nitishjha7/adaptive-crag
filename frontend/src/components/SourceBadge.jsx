/**
 * Answer kahan se aaya — Local Vector DB ya Live Web Fallback.
 *
 * Ye UI ka sabse zaroori element hai. Iske bina dono routes bilkul ek jaise
 * dikhte hain, aur poore project ka point (system ne khud decide kiya kahan
 * se jawab laana hai) invisible ho jaata hai.
 */
const STYLES = {
  vector_db: {
    label: "Local Vector DB",
    className: "bg-emerald-500/10 text-emerald-300 ring-emerald-500/30",
    dot: "bg-emerald-400",
  },
  web_search: {
    label: "Live Web Fallback",
    className: "bg-sky-500/10 text-sky-300 ring-sky-500/30",
    dot: "bg-sky-400",
  },
};

export default function SourceBadge({ sourceType }) {
  const style = STYLES[sourceType];
  if (!style) return null;

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset ${style.className}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${style.dot}`} />
      {style.label}
    </span>
  );
}
