/**
 * Live configuration — kya sach me chal raha hai.
 *
 * Har value `/api/stats` se aati hai, screen pe kuch hardcoded nahi. Isi wajah
 * se ye view debugging me sabse kaam ka hai: "reranker on hai ya nahi", "kaunsa
 * corpus load hai", "Groq key set hai ya nahi" — teeno sawaal yahin dikh jaate
 * hain, container ke andar ghuse bina.
 */
function Row({ label, value, mono, tone }) {
  const tones = {
    good: "text-emerald-600",
    bad: "text-red-600",
    off: "text-slate-400",
  };
  return (
    <div className="flex items-center justify-between gap-4 border-b border-slate-100 py-2.5 last:border-0">
      <span className="text-sm text-slate-500">{label}</span>
      <span
        className={`text-right text-sm font-medium ${tone ? tones[tone] : "text-slate-800"} ${
          mono ? "font-mono text-xs" : ""
        }`}
      >
        {value}
      </span>
    </div>
  );
}

function Card({ title, subtitle, children }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <h3 className="font-semibold text-slate-800">{title}</h3>
      {subtitle && <p className="mt-0.5 text-xs text-slate-400">{subtitle}</p>}
      <div className="mt-3">{children}</div>
    </div>
  );
}

export default function SystemView({ stats }) {
  if (!stats) {
    return (
      <div className="rounded-xl border border-amber-200 bg-amber-50 p-6 text-sm text-amber-800">
        Backend unreachable — start it with{" "}
        <span className="font-mono">docker compose up</span>.
      </div>
    );
  }

  const c = stats.config;

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-lg font-semibold">System status</h2>
        <p className="mt-1 text-sm text-slate-500">
          Read live from the running backend — nothing on this page is hardcoded in
          the UI, so it is the fastest way to check what a container is actually
          running.
        </p>
      </div>

      {/* Pehle yahan chaar cards the. "Retrieval" card me Corpus / Documents /
          Chunks the — teeno header line me aur Documents page pe pehle se hain,
          yaani do jagah dobara. Reranker do baar likha tha: model "Models" me,
          on/off "Retrieval" me — ek hi cheez ke do rows. Aur "Web fallback"
          card ki doosri row derived thi (provider duckduckgo hai to key nahi
          chahiye), yaani ek poora card do lines ke liye.

          Ab do cards: kya chal raha hai, aur kya banaya hi nahi. */}
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Pipeline" subtitle="Everything except the LLM runs locally">
          <Row label="LLM (Groq)" value={c.llm_model} mono />
          <Row
            label="Groq API key"
            value={c.groq_key_set ? "set" : "missing"}
            tone={c.groq_key_set ? "good" : "bad"}
          />
          <Row label="Embeddings" value={c.embedding_model} mono />
          {/* Flag aur model ek hi row me: off hone pe model ka naam dikhana
              jhooth hai, kyunki wo load hi nahi hua. */}
          <Row
            label="Cross-encoder rerank"
            value={c.reranker ? (c.reranker_model ?? "on") : "off"}
            mono={Boolean(c.reranker && c.reranker_model)}
            tone={c.reranker ? undefined : "off"}
          />
          <Row
            label="Hybrid (BM25 + RRF)"
            value={c.hybrid ? "on" : "off"}
            tone={c.hybrid ? "good" : "off"}
          />
          <Row label="Chunks sent to the grader" value={c.top_k} />
          <Row
            label="Web search"
            value={
              c.search_provider === "duckduckgo"
                ? "duckduckgo — no API key"
                : `${c.search_provider} — needs a key`
            }
          />
        </Card>

        <Card title="Not built" subtitle="Stated here rather than hidden">
          <Row label="Deployment" value="not deployed" tone="off" />
          <Row label="Document upload API" value="none — ingestion is offline" tone="off" />
          <Row label="Context filter" value="none — top-k goes straight to the grader" tone="off" />
          <Row label="Prompt-injection defence" value="none" tone="off" />
          <Row label="Conversation memory" value="none — every query is independent" tone="off" />
        </Card>
      </div>
    </div>
  );
}
