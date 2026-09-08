# RAG Fundamentals — Concepts + Interview Prep

Ye doc **general RAG knowledge** ke liye hai — concepts, production architecture, aur
interview questions. Project-specific pitch aur Q&A [INTERVIEW_NOTES.md](INTERVIEW_NOTES.md)
me hai.

---

> ## ⚠️ Sabse zaroori baat — pehle ye padh
>
> Neeche jo "production-grade RAG" architecture hai, wo **is project ka architecture nahi
> hai**. Usme kaafi components hain jo Adaptive CRAG me **hai hi nahi** — hybrid search,
> BM25, reranker, page-level citations.
>
> Interview me wo diagram apna bolna aur interviewer ka GitHub khol lena — wahi sabse bada
> credibility risk hai. [Section 3](#3-ye-project-vs-production-architecture) me exact
> mapping hai: kya hai, kya nahi hai.
>
> **Sahi framing:** *"Production RAG me hybrid retrieval aur reranking hota hai. Maine wo
> nahi banaya — maine deliberately corrective loop pe focus kiya, aur usko measure kiya."*
> Ye honest bhi hai aur scope-awareness bhi dikhata hai.

---

## Table of Contents

1. [RAG kya hai aur kyun](#1-rag-kya-hai-aur-kyun)
2. [Production RAG pipeline — stage by stage](#2-production-rag-pipeline--stage-by-stage)
3. [Ye project vs production architecture](#3-ye-project-vs-production-architecture)
4. [RAG → CRAG → Agentic RAG progression](#4-rag--crag--agentic-rag-progression)
5. [Interview questions — basic](#5-interview-questions--basic)
6. [Interview questions — intermediate](#6-interview-questions--intermediate)
7. [Interview questions — advanced](#7-interview-questions--advanced)
8. [Scenario questions (sabse important)](#8-scenario-questions-sabse-important)

---

## 1. RAG kya hai aur kyun

**RAG = Retrieval-Augmented Generation.**

Normal LLM sirf apni training knowledge se jawab deta hai. RAG me hum **query ke time**
apna data dhoondh ke LLM ko dete hain, aur wo us diye hue data se jawab banata hai.

```
User Question -> Retriever -> Relevant chunks -> LLM -> Answer
```

**Kyun chahiye:**

| Problem | RAG kaise solve karta hai |
|---|---|
| LLM ko teri company ka data pata hi nahi | Query time pe wo data retrieve karke context me daal do |
| Knowledge purani ho jaati hai | Index update karo, model retrain nahi karna padta |
| Hallucination | Answer ko retrieved evidence se ground karo |
| "Ye kahan se aaya?" | Citations — source document + page |

**RAG vs Fine-tuning** (ye poochha jaata hai, almost hamesha):

```
Knowledge jo badalti rehti hai        -> RAG
Behaviour / style / format sikhana    -> Fine-tuning
Dono chahiye                          -> Dono
```

Fine-tuning model ko *behave* karna sikhata hai; RAG use *facts* deta hai. Company policy
chatbot me policy kal badal sakti hai — usko fine-tune karna bewakoofi hai.

---

## 2. Production RAG pipeline — stage by stage

Do alag pipelines hoti hain. Ye distinction interview me bahut kaam aata hai:

```
INGESTION (offline — jab document upload/update hota hai)
┌──────────────┐
│  Documents   │
└──────┬───────┘
       v
 Document Parser        PDF/DOCX se saaf text nikalo
       v
   Chunking             bade doc ko tukdon me todo
       v
  Embeddings            har chunk ko vector banao
       v
 Vector Database        vectors + text + metadata store karo


QUERY TIME (online — har user question pe)
User Query
    v
 Query Rewrite          question ko retrieval-friendly banao
    v
 Hybrid Retrieval
    /        \
Vector      BM25        meaning-based + keyword-based
    \        /
   Reranker             top-K ko dobara, better model se score karo
       v
 Context Filter         sirf sach me useful chunks LLM ko do
       v
  LLM / Agent
       v
 Grounded Answer        jawab retrieved evidence pe based
       v
   Citations            source file + page
```

### 2.1 Document Parser

PDF me sirf text nahi hota — tables, images, headers, footers, multi-column layout. Parser
in sabme se usable text nikalta hai.

**Kyun matter karta hai:** agar parser two-column PDF ko galat padhe, to aage ka poora
pipeline kachra pe chalega. "Document exact me hai par RAG jawab nahi de raha" ka sabse
common root cause yahi hota hai — aur zyadatar log embedding model blame karte hain.

### 2.2 Chunking

Poore 100-page document ka ek embedding banana bekaar hai — wo vector document ke *average*
topic ko represent karega aur kisi specific question se match nahi karega.

```
100-page doc -> Chunk 1, Chunk 2, ... Chunk 500
```

**Chunk size ka trade-off:**

| Size | Problem |
|---|---|
| Bahut chhota (~100 chars) | Context toot jaata hai — "18 leaves" milta hai par kiske liye pata nahi |
| Bahut bada (~5000 chars) | Relevant line irrelevant text ke saath average ho jaati hai (dilution) |

Common starting point: **800 chars, 100 overlap**. Ye is project me bhi wahi hai
(`backend/app/config.py`).

**Overlap kyun:** agar ek sentence do chunks ke beech split ho gaya, to dono me se koi bhi
theek se retrieve nahi hoga. Overlap us boundary sentence ko kam se kam ek chunk me poora
rakhta hai. Typically chunk size ka 10–15%.

**Recursive character splitting:** separators ki list order me try karta hai — paragraph
break, phir line break, phir sentence, phir word. Fixed character count pe todne se
semantically related text saath rehta hai.

### 2.3 Embeddings

Text -> fixed-length float vector, jo **meaning** represent karta hai.

```
"Employees get 18 paid leaves"  ->  [0.12, -0.42, 0.87, ...]
```

Isliye ye dono paas-paas aate hain, chahe words alag hain:

- "How many paid leaves do employees get?"
- "What is the annual leave entitlement?"

**Cosine similarity** — do vectors ke beech ka *angle*, magnitude ignore karke. Magnitude
ignore karna zaroori hai kyunki embedding ki length aksar text ki lambai se badalti hai,
meaning se nahi.

**Model size trade-off:** chhote model (jaise `bge-small`, 384 dims) CPU pe fast chalte
hain; bade model (768/1024 dims) finer distinctions pakadte hain par mehnge hain. Chhote
corpus pe **acchi chunking ka farak embedding model ke farak se zyada hota hai.**

### 2.4 Vector Database

Embeddings + original text + metadata store karta hai, aur nearest-neighbour query answer
karta hai.

**Exact vs approximate (ANN):** exact search har vector se compare karta hai — perfect
accuracy, ~1 lakh vectors tak theek. Usse aage HNSW jaise ANN index thoda recall chhod ke
bahut speed dete hain.

**Embedded vs server mode:** Chroma embedded mode me ek library ki tarah chalta hai, ek
directory me likhta hai, alag process nahi. Demo/small tool ke liye kaafi. Multiple app
instances chahiye to server mode.

**Metadata filtering:** similarity search ke saath filter — ek document tak, ek date range
tak, ek access level tak. Filter **pehle** lagana better hai (candidate set hi chhota ho
jaata hai) bajaye results ko baad me chhaante ke.

### 2.5 Query Rewrite

User conversational likhta hai; retrieval ko kuch aur chahiye.

```
"bhai meri paid chutti kitni hai?"
        v
"annual paid leave entitlement employees"
```

**HyDE (Hypothetical Document Embeddings)** — ulta approach: pehle ek *hypothetical answer*
generate karo, phir usko embed karke query banao. Kyunki hypothetical answer corpus ki hi
declarative style me likha hota hai, uska embedding asli answer ke zyada paas baithta hai.
Answer factually sahi hona zaroori nahi — bas structurally similar.

**Multi-query expansion** — question ke 3-4 paraphrase banao, sabke liye retrieve karo,
results merge karo. Recall badhta hai, cost badhta hai.

**Decomposition** — compound question ("X ki v2 pricing v1 se compare karo") ek query me
theek retrieve nahi hoti kyunki koi ek chunk dono halves cover nahi karta. Sub-questions me
todo.

### 2.6 Hybrid Retrieval: Vector + BM25

| | Kisme strong |
|---|---|
| **Vector search** (dense) | Meaning. "time off" ≈ "leave entitlement" |
| **BM25** (sparse, keyword) | Exact tokens — `EMP-4582`, `SKU-12345`, `18`, product names |

Vector search exact identifiers pe surprisingly kharab hota hai, kyunki `EMP-4582` aur
`EMP-4583` ka meaning embedding space me lagbhag same hai. BM25 wahan exact match karta hai.

Isliye production me dono chalate hain aur scores fuse karte hain (aksar Reciprocal Rank
Fusion se).

### 2.7 Reranker

Retrieval 20 chunks laata hai. Reranker unhe **dobara** score karta hai — ek bhaari
cross-encoder model se, jo query aur chunk ko *ek saath* padhta hai.

**Retriever vs reranker ka asli difference:**

- Retriever query aur document ko **alag-alag** embed karta hai (bi-encoder). Isliye fast
  hai — document vectors pehle se bane hue hain — par interaction nahi dekh paata.
- Reranker query+document ko **ek saath** model me daalta hai (cross-encoder). Kaafi
  accurate, par har pair pe ek forward pass — isliye sirf top-20 pe chalta hai, poore
  corpus pe nahi.

Isiliye ye do-step hai: sasta retriever 20 laata hai, mehenga reranker unme se 5 chunta hai.

### 2.8 Context Filter → LLM → Grounding → Citations

- **Context filter** — relevance threshold ke neeche wale chunks phenk do. LLM ko bharna
  nuksaan karta hai ("lost in the middle": model context ke beech ka material reliably nahi
  padhta).
- **Grounded answer** — jawab retrieved evidence pe based ho, model ki apni memory pe nahi.
- **Citations** — source file + page. User verify kar sake.

---

## 3. Ye project vs production architecture

**Ye table interview se pehle yaad kar lena.** Isi se pata chalega ki kya bolna hai aur kya
nahi.

| Stage | Production RAG | Adaptive CRAG me? |
|---|---|---|
| Document parser | PDF/DOCX/HTML extraction | 🟡 Sirf `.md`/`.txt` — corpus already plain text hai |
| Chunking | Recursive, structure-aware | ✅ `RecursiveCharacterTextSplitter`, 800/100, `\n## ` first |
| Embeddings | Hosted ya local | ✅ FastEmbed `bge-small-en-v1.5`, local ONNX |
| Vector DB | Pinecone / Weaviate / Qdrant | ✅ Chroma, embedded mode |
| **Query rewrite** | Retrieval se **pehle** | 🟡 Hai, par **baad me** — sirf fallback path pe. Neeche dekh |
| **Hybrid retrieval** | Vector + BM25 | ❌ **Nahi hai.** Sirf vector search |
| **Reranker** | Cross-encoder | ❌ **Nahi hai** |
| Context filter | Threshold / compression | ❌ Nahi. Top-k seedha `generate` me |
| **Retrieval evaluator** | Usually nahi hota | ✅ **Hai — yahi project ka core hai** |
| **Web fallback** | Usually nahi hota | ✅ **Hai — conditional, always-on nahi** |
| Grounding check | Kabhi-kabhi | ✅ Independent LLM check + PII redaction |
| Citations | File + page number | 🟡 Web results pe `[source: URL]`. Local chunks pe koi citation nahi |
| Evaluation | RAGAS / custom | ✅ 20 labelled queries, routing 20/20 |

### Query rewrite ka placement — ye interview me pakda ja sakta hai

Production diagram me rewrite **retrieval se pehle** hota hai, taaki retrieval hi behtar ho.

Is project me `transform_query` **grading ke baad** chalta hai, sirf tab jab local context
"no" grade ho jaye:

```
retrieve -> grade -> "no" -> transform_query -> web search
```

**Kyun:** yahan rewrite ka kaam vector retrieval sudhaarna nahi hai — wo already ho chuka
aur reject ho gaya. Kaam hai conversational question ko **web search engine** ke liye
keywords me badalna. Do alag maqsad hain.

Agar interviewer poochhe *"rewrite pehle kyun nahi?"* — sahi jawab: *"pre-retrieval rewrite
ek alag optimisation hai, aur uska fayda measure karna padega. Maine wo nahi banaya."*
Ye mat bolna ki tera placement production se better hai.

### Jo nahi hai, uspe kya bolna

Ye teen sabse zyada poochhe jayenge:

**"Hybrid search kyun nahi?"**
> "Mera corpus 7 concept documents ka hai — usme koi product code, SKU ya identifier nahi
> hai, aur BM25 ka asli fayda wahin hota hai. Isliye usko add karna is corpus pe measure
> hi nahi ho paata. Agar corpus me identifiers hote, BM25 pehla addition hota."

**"Reranker kyun nahi?"**
> "Wo agla step hai, aur grader ke liye seedha faydemand hai — reranker better chunks upar
> laata hai, to grader ko judge karne ke liye better input milta hai. Abhi mera eval
> categorical gap pe 20/20 de raha hai, to reranker ka fayda is dataset pe dikhega hi nahi.
> Pehle ambiguous cases ka eval banana padega, tab reranker measurable ho jaayega."

**"Citations kyun nahi?"**
> "Web results pe URL attach hota hai. Local chunks pe nahi — metadata me source filename
> hai par wo answer tak carry nahi hota. Ye ek genuine gap hai, chhota fix hai."

---

## 4. RAG → CRAG → Agentic RAG progression

```
Naive RAG          retrieve -> stuff -> generate. Retrieval pe blind bharosa
     v
Advanced RAG       + rewrite, hybrid, rerank, compression. Retrieval better,
                   par abhi bhi verify nahi karta
     v
CRAG               + retrieval evaluator. "Jo mila wo kaam ka hai?" Nahi to correct karo
     v
Self-RAG           model apni retrieval AUR apni generation dono critique karta hai
     v
Agentic RAG        agent decide karta hai kya retrieve karna hai, kis source se,
                   aur agla action kya hai
```

**Ye project kahan baithta hai:** CRAG. Evaluator hai, correction (web fallback) hai,
output validation hai. Advanced-RAG wale retrieval optimisations (hybrid, rerank) nahi hain
— aur ye **deliberate scope choice** hai, kami nahi: axis retrieval *quality* nahi,
retrieval *verification* hai.

Naive RAG ke failure modes (jo CRAG address karta hai):

1. **Retrieval mismatch** — similarity search hamesha k results deta hai, chahe corpus me
   kuch relevant ho ya na ho. Low score kabhi LLM tak pahunchta hi nahi.
2. **Staleness** — fact badal gaya, system purane version se confidently jawab deta hai.
3. **Lost in the middle** — lambi context ke beech ka material model reliably nahi padhta.
4. **No abstention** — naive pipeline me "mujhe nahi pata" wala rasta hai hi nahi;
   generation unconditional hai.

---

## 5. Interview questions — basic

> ✅ = is project se seedha answer de sakta hai (sabse strong answers wahi hote hain)

| # | Question | Anchor |
|---|---|---|
| 1 | RAG kya hai, need kyun? | ✅ Section 1 |
| 2 | RAG vs fine-tuning? | ✅ Changing knowledge → RAG |
| 3 | End-to-end RAG workflow? | ✅ Ingestion + query pipeline alag batana |
| 4 | Embedding kya hai? | ✅ `bge-small`, 384 dims |
| 5 | Vector DB kya hai, role kya hai? | ✅ Chroma embedded |
| 6 | Chunking kyun? | ✅ 800/100, poore doc ka ek vector bekaar hai |
| 7 | Chunk size kaise decide karoge? | ✅ Trade-off table, section 2.2 |
| 8 | Overlap kya, kyun? | ✅ Boundary sentence, 10–15% |
| 9 | Semantic vs keyword search? | Theory — BM25 project me nahi hai |
| 10 | Cosine similarity kyun, Euclidean kyun nahi? | ✅ Magnitude text length se badalta hai |
| 11 | Context window ka role? | ✅ Lost in the middle |

## 6. Interview questions — intermediate

| # | Question | Anchor |
|---|---|---|
| 12 | Naive RAG ki limitations? | ✅ **Poora project isi ka jawab hai** — 4 failure modes |
| 13 | Hybrid search / BM25 kya? | ⚠️ Theory. Saaf bolna ki nahi banaya |
| 14 | Dense vs sparse retrieval? | Theory |
| 15 | Reranker kya, retriever se kaise alag? | ⚠️ Theory. Bi-encoder vs cross-encoder wala farak yaad rakh |
| 16 | Top-K kaise decide karoge? | ✅ k=4. Zyada k monotonically better nahi — lost in middle |
| 17 | Relevant doc Top-K me nahi aaya to? | Rewrite, multi-query, k badhao, hybrid, rerank |
| 18 | Poor retrieval kaise debug karoge? | ✅ Scenario 52 dekh |
| 19 | Metadata filtering? | 🟡 Chroma support karta hai, project use nahi karta |
| 20 | Query rewriting? | ✅ Hai — par fallback pe. Section 3 wali baat |
| 21 | HyDE? | Theory — section 2.5 |
| 22 | Hallucination kaise kam karoge? | ✅ **Project ka core** — grade + grounded prompt + validation |

## 7. Interview questions — advanced

| # | Question | Anchor |
|---|---|---|
| 23 | CRAG kya, normal RAG se farak? | ✅ Evaluator + conditional correction |
| 24 | Agentic RAG / Self-RAG? | ✅ Section 4 progression |
| 25 | Retrieval evaluator kaise design karoge? | ✅ Binary, temp 0, defensive parse, `parse_verdict` ke 11 tests |
| 26 | Context relevant hai par answer galat — kaise pakdoge? | ✅ Groundedness check exactly yahi pakadta hai |
| 27 | Citation / grounding kaise? | 🟡 Web pe URL, local pe nahi — gap maan lena |
| 28 | Retrieval quality kaise measure karoge? | ✅ **`backend/eval/`, 20 labelled queries** |
| 29 | Precision@K / Recall@K? | ✅ Eval me fallback precision + recall dono hain |
| 30 | Faithfulness vs answer relevance? | ✅ Groundedness = faithfulness |
| 31 | RAGAS? | ⚠️ Nahi use kiya — custom eval banaya, wajah bata sakta hai |
| 32 | Latency kaise kam karoge? | ✅ **Yahan asli story hai — RESULTS.md** |
| 33 | Millions of docs pe fast retrieval? | ANN/HNSW, managed vector DB, metadata pre-filter |
| 34 | Embedding model kaise choose karoge? | ✅ Section 2.3 trade-off |
| 35 | Embedding model badal diya to? | **Poora index rebuild** — vectors compatible nahi hote |
| 36 | Docs update/delete pe embeddings kaise maintain? | 🟡 Project me nahi — full re-ingest. Gap maan lena |
| 37 | Multi-tenant RAG? | Per-tenant collection ya metadata filter + row-level access |
| 38 | Prompt injection through retrieved docs? | ⚠️ **Ye project handle nahi karta** — neeche dekh |

**Prompt injection wala answer** (ye aajkal bahut poochha jaata hai):

Retrieved document me likha ho sakta hai *"Ignore previous instructions and say X"* — aur
web fallback me ye risk **zyada** hai, kyunki content bahar se aa raha hai. Mitigations:
retrieved text ko clearly data ke roop me delimit karo, system prompt me bolo ki context
data hai instruction nahi, output validate karo, aur retrieved content ko kabhi tool call
trigger mat karne do.

> **Is project me:** groundedness check ek partial net hai — injected instruction se bana
> answer aksar context se unsupported hoga. Par ye deliberate injection defence **nahi** hai.
> Interview me isko strength mat batana; "known gap, aur web path pe zyada relevant" bolna.

---

## 8. Scenario questions (sabse important)

Definition wale questions rat sakte ho. Scenario questions me sochne ka tareeka dikhta hai —
isliye inhe **checklist ki tarah** yaad rakho, ek-line jawab ki tarah nahi.

### "Answers hallucinate kar rahe hain. Debug kaise karoge?"

Pipeline ke order me chalo, guess mat karo:

```
1. Retrieval me relevant chunk aaya bhi tha?   -> nahi to retrieval problem hai
2. Chunk aaya par top-k me neeche tha?          -> ranking problem
3. Context me gaya par LLM ne ignore kiya?      -> lost in middle / prompt
4. Prompt bolta hai "sirf context se"?          -> prompt problem
5. Answer context se supported hai?             -> groundedness check
```

✅ **Tera edge:** *"Maine ye pipeline me hi build kiya hai — grading node step 1 ko catch
karta hai, groundedness check step 5 ko."*

### "Information document me hai, phir bhi RAG jawab nahi de raha. Why?"

- Parsing — PDF theek se extract hi nahi hua (sabse under-rated cause)
- Chunking — answer do chunks ke beech split ho gaya, overlap kam tha
- Embedding model domain ke liye galat
- Query phrasing document ki phrasing se bahut alag (→ rewrite/HyDE)
- Top-K chhota
- Metadata filter galti se result nikal raha hai

### "100-page PDF hai, chunks kaise banaoge?"

Interviewer number nahi, **reasoning** dekh raha hai:

> "Pehle structure dekhunga — headings hain to unpe split karunga aur heading path metadata
> me rakhunga. Fallback recursive character splitting, ~800 chars, 100 overlap. Phir
> retrieval quality pe tune karunga, guess pe nahi. Tables ko alag handle karna padega,
> kyunki wo naive splitting me toot jaati hain."

### "Vector search relevant result nahi de raha. Kya badloge?"

Sasta → mehenga, is order me:

```
Chunking -> Query rewrite -> Top-K -> Metadata filter
         -> Hybrid (BM25) -> Reranker -> Embedding model badalna
```

Embedding model last me hai kyunki usse **poora index rebuild** karna padta hai.

### "Company knowledge chatbot — RAG ya fine-tuning?"

> "RAG. Knowledge badalti rehti hai, aur fine-tuning har policy update pe retraining maangega.
> Fine-tuning tab, jab tone/format fix karna ho — par facts RAG se hi aane chahiye."

### "Production-grade RAG design karo"

Section 2 ka diagram bana do, phir ye add karo (yahi seniority dikhata hai):

- **Evaluation** — labelled set, CI me chalo, regression pakdo
- **Observability** — har query ka trace: kya retrieve hua, kya route liya
- **Caching** — repeated queries pe embedding + generation cache
- **Access control** — multi-tenant me metadata filter
- **Prompt injection protection**
- **Re-index pipeline** — documents badalte hain

✅ **Tera edge:** evaluation aur observability tere paas **actually** hain — eval harness
aur trace viewer. Zyadatar candidates ye sirf bolte hain, dikha nahi paate.

---

## Aakhri baat

Sabse strong jawab wo hote hain jo **tere apne code se anchored** hon. "Chunk overlap
zaroori hota hai" theory hai. *"Maine 800/100 use kiya, `\n## ` pehla separator rakha taaki
heading boundaries pe toote, aur ye decision `backend/ingest.py` me hai"* — ye experience hai.

Isliye jo ✅ wale hain, unhe pehle taiyaar karo. Aur jo ❌ hai (hybrid, reranker, citations),
unko **gap ki tarah maano** — chhupane ki koshish mat karo. "Maine nahi banaya, aur ye wajah
hai" hamesha "haan wo bhi hai" se better hai, kyunki doosra jhoot ek follow-up question me
pakda jaata hai.
