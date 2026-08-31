/**
 * Node-by-node execution timeline — UI ka sabse impressive hissa.
 *
 * Backend ka har node `logs` me ek line append karta hai (additive reducer).
 * Yahan wahi lines timeline banti hain, to dikhta hai ki system ne kya socha:
 * retrieve -> grade: no -> transform -> web search -> generate -> validate.
 *
 * Isi se system black box nahi rehta. Interview me answer se zyada ye trace
 * dikhana kaam karta hai.
 */

// Correction path wale nodes highlight hote hain — wahi CRAG ka asli USP hai.
const CORRECTION_NODES = new Set(["transform_query", "web_search_fallback"]);

function nodeName(line) {
  return line.split(" ->")[0].trim();
}

export default function TraceViewer({ logs }) {
  if (!logs?.length) return null;

  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/50 p-4">
      <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
        Execution trace
      </h3>

      <ol className="space-y-0">
        {logs.map((line, i) => {
          const name = nodeName(line);
          const detail = line.slice(name.length).replace(/^\s*->\s*/, "");
          const isCorrection = CORRECTION_NODES.has(name);
          const isLast = i === logs.length - 1;

          return (
            <li key={i} className="relative flex gap-3 pb-4 last:pb-0">
              {/* connector line — aakhri node pe nahi */}
              {!isLast && (
                <span className="absolute left-[5px] top-3 h-full w-px bg-slate-700" />
              )}

              <span
                className={`relative mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full ring-4 ring-slate-950 ${
                  isCorrection ? "bg-sky-400" : "bg-slate-500"
                }`}
              />

              <div className="min-w-0 flex-1">
                <div
                  className={`font-mono text-sm ${
                    isCorrection ? "text-sky-300" : "text-slate-300"
                  }`}
                >
                  {name}
                </div>
                {detail && (
                  <div className="break-words font-mono text-xs text-slate-500">
                    {detail}
                  </div>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
