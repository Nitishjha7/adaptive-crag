import { useCallback, useEffect, useState } from "react";

/**
 * Past queries ka local log.
 *
 * **Ye conversation memory NAHI hai — aur ye farak zaroori hai.** Graph
 * stateless hai: koi checkpointer nahi, aur `CRAGState` har request pe
 * `initial_state()` se naya banta hai. Follow-up question pichhle turn ka
 * context **use nahi karta**.
 *
 * To ye sirf ek record hai — kya poochha gaya, kaunsa route mila, kya trace
 * tha. Demo me ye asli kaam ka hai: ek local-route aur ek web-route answer
 * saath rakh ke farak dikhaya ja sakta hai bina dobara chalaye. Par UI ko
 * kabhi ye impression nahi dena chahiye ki system pichhli baat yaad rakhta hai.
 *
 * `localStorage` isliye ki backend pe koi user, session ya DB hai hi nahi.
 * Server-side history ke liye pehle wo teeno chahiye — aur wo is project ka
 * axis nahi hai.
 */
const KEY = "crag.history.v1";
// Purani entries chhaant dete hain: ye ek demo log hai, archive nahi, aur
// localStorage ka quota ~5MB hota hai.
const MAX = 20;

function load() {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    // Private mode / storage disabled / corrupt JSON — history ek convenience
    // hai, uske liye app todna galat hai.
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
      // Badge sidebar me dikhta hai — ek nazar me pata chal jaata hai ki us
      // query pe correction path chala tha ya nahi.
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
