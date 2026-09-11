import { useCallback, useEffect, useState } from "react";

/**
 * Past queries ka local log.
 *
 * **This is NOT conversation memory, and the distinction matters.** The graph
 * is stateless: there is no checkpointer, and `CRAGState` is rebuilt from
 * `initial_state()` on every request. A follow-up question does **not** use the
 * previous turn's context.
 *
 * So this is only a record — what was asked, which route it took, what the trace
 * was. That earns its place in a demo: a local-route and a web-route answer can
 * sit side by side without re-running either. But the UI must never suggest the
 * system remembers anything.
 *
 * `localStorage` because the backend has no users, no sessions and no database.
 * Server-side history would need all three, and that is not this project's axis.
 */
const KEY = "crag.history.v1";
// Old entries are trimmed: this is a demo log, not an archive, and
// localStorage has a ~5MB quota.
const MAX = 20;

function load() {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    // Private mode / storage disabled / corrupt JSON — history ek convenience
    // convenience; breaking the app over it would be wrong.
    return [];
  }
}

function save(items) {
  try {
    localStorage.setItem(KEY, JSON.stringify(items));
  } catch {
    /* quota bhar gaya ya storage band — chup-chaap chhod do */
  }
}

export default function useHistory() {
  const [items, setItems] = useState(load);

  useEffect(() => {
    save(items);
  }, [items]);

  /** Ek poori conversation record karo (ya usi id pe update karo). */
  const record = useCallback((id, turns) => {
    const firstUser = turns.find((t) => t.role === "user");
    if (!firstUser) return;

    const answer = turns.find((t) => t.role === "assistant");
    const entry = {
      id,
      title: firstUser.text,
      at: Date.now(),
      // The badge shows in the sidebar, so one glance says whether that query
      // took the correction path.
      route: answer?.source_type ?? null,
      turns,
    };

    setItems((prev) => [entry, ...prev.filter((e) => e.id !== id)].slice(0, MAX));
  }, []);

  const remove = useCallback((id) => {
    setItems((prev) => prev.filter((e) => e.id !== id));
  }, []);

  const clear = useCallback(() => setItems([]), []);

  return { items, record, remove, clear };
}
