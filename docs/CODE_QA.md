# Code Q&A — apne hi code ko defend karne ke liye

Ye doc [BUILD_PLAN.md](BUILD_PLAN.md) ke **"Nitish ka Part"** ke liye hai.

Code ban chuka hai. Wo tere naam se jaayega. Interviewer code padhega nahi — wo
tujhse poochhega *"ye line aise kyun likhi"*. Jo sawaal yahan hain, wahi wahan
aayenge, kyunki ye code ke **faisle** hain — lines nahi.

**Kaise use karna hai:** sawaal padho, jawab **dekhe bina** bolo. Jahan atke,
wahi tera kamzor point — usi pe interviewer bhi atkayega. Jawab yaad mat karo;
har jawab me **kyun** likha hai, wahi samajhna hai. Interviewer follow-up
poochhega, aur ratta wahin toot jaata hai.

Har sawaal ke saath file aur line di hai — jawab padhne se pehle **code kholo**.

---

## 1. `grade_documents.py` — grader

[backend/app/nodes/grade_documents.py](../backend/app/nodes/grade_documents.py)

### Q1. Binary `yes`/`no` kyun? Cosine similarity score pe threshold laga dete, ek LLM call hi bach jaata.

Score ko **threshold chahiye** — 0.7 pe kaato ya 0.75 pe? Wo har corpus pe alag
hota hai aur tune karna padta hai. Binary verdict deterministic hai aur
samjhaya ja sakta hai: koi tuned constant nahi jo kal badalna pade.

Aur similarity score wo sawaal poochhta hi nahi jo poochhna hai. Cosine
similarity kehti hai *"ye text query se kitna milta-julta hai"*, jabki sawaal ye
hai *"is text me jawab hai kya"*. Ek document topically bahut close ho sakta hai
aur phir bhi jawab na rakhta ho — wahi naive RAG ka failure mode hai.

LLM se decimal maangna aur bhi bura hota: model calibrated probability deta hi
nahi. `0.87` chhapna **fake precision** hoti, aur is project ka usool hai ki jo
number naapa nahi gaya wo dikhaya nahi jaata.

### Q2. `parse_verdict` me `yes` ka check pehle rakh doon to kya tootega?

[grade_documents.py:44-47](../backend/app/nodes/grade_documents.py#L44-L47)

Model kabhi `"no, because the documents mention yes..."` jaisa jawab de sakta
hai. `yes` pehle check karoge to wo substring mil jaayega aur verdict **ulta**
nikal aayega — "no" wale case ko "yes" padh liya.

Ulta order safe hai: `"yes"` string kabhi `"no"` ke andar nahi milti.

Isi ka doosra hissa: jab kuch samajh na aaye to default **`no`** hai, `yes`
nahi. Wajah asymmetry hai — galat `no` ka kharcha ek extra web call hai; galat
`yes` ka matlab hai reject kiye hue context se answer banana, yaani
hallucination. Sasti galti chuni hai.

### Q3. Grader ka `temperature` 0.7 kar doon to?

[grade_documents.py:61-63](../backend/app/nodes/grade_documents.py#L61-L63)

**Routing non-deterministic ho jaayega** — ek hi sawaal kabhi local jaayega
kabhi web. Teen cheezein tootengi:

1. **Demo** — chip pe click karo, har baar alag route
2. **Debugging** — bug reproduce hi nahi hoga
3. **Eval** — routing accuracy ka matlab khatam. Do run me alag number aayega
   aur pata nahi chalega ki code badla ya sirf sampling

Generation me thoda randomness chalta hai. **Decision me nahi.**

### Q4. `documents` khaali ho to LLM call kyun nahi karte?

[grade_documents.py:54-59](../backend/app/nodes/grade_documents.py#L54-L59)

Grade karne ko kuch hai hi nahi — khaali context bhej ke poochhna ki "kya isme
jawab hai" ek bekar call hai jiska jawab pehle se pata hai. Seedha `no` lauta
dete hain, aur fallback chal jaata hai.

Ye sirf optimisation nahi: agar khaali documents pe model galti se `yes` bol
deta, to `generate` bina kisi context ke answer banata.

### Q5. Grader ko chaaron chunks ek saath dete ho ya ek-ek karke?

[grade_documents.py:67](../backend/app/nodes/grade_documents.py#L67) — `"\n\n---\n\n".join(documents)`

Ek saath, ek hi call me. Per-chunk grading zyada granular hota (pata chalta
kaunsa chunk kaam ka hai) par **k guna zyada LLM calls** lagti — aur is project
ka poora cost argument call counts pe khada hai.

**Iska ek asli natija hai jo eval me nikla:** grader chunks ko concatenate karta
hai, to **ordering uske liye invisible hai**. Isiliye reranking — jo ordering
sudharta hai — routing pe koi asar nahi dikha paya. Wo `RESULTS.md` ka negative
result hai, aur uski wajah exactly yahi line hai.

---

## 2. `build_graph.py` — conditional edge

[backend/app/graph/build_graph.py](../backend/app/graph/build_graph.py)

### Q6. Chain se kaam ho jaata, graph kyun?

Kyunki `grade_documents` ke baad kaunsa node chalega ye **compile time pe fixed
nahi hai** — runtime pe state padh ke decide hota hai. Ek linear chain ye express
kar hi nahi sakti; usme har step ka agla step pehle se likha hota hai.

Yahi "Adaptive" ka matlab hai: rasta har query pe alag ban sakta hai.

### Q7. `decide_to_generate` itna khaali kyun hai? Ek line me kya faisla ho raha hai?

[build_graph.py:30-41](../backend/app/graph/build_graph.py#L30-L41)

**Jaan-boojh ke khaali hai.** Saara faisla `grade_documents` me hota hai; yahan
sirf uska result padha jaata hai.

Wajah: grading logic aur routing logic alag rehne se dono **alag-alag test** ho
sakte hain. Router ka test bina kisi LLM ke chal jaata hai — bas state me
`relevance_score` set karo aur dekho kaunsi string aati hai. Agar grading yahin
hoti to router test ko mock LLM chahiye hota.

### Q8. Iska default `transform_query` kyun hai, `generate` kyun nahi?

[build_graph.py:41](../backend/app/graph/build_graph.py#L41)

```python
return "generate" if state.get("relevance_score") == "yes" else "transform_query"
```

Sirf **exact `"yes"`** pe generate hota hai. Baaki sab — `"no"`, khaali string,
missing key, koi unexpected value — fallback pe jaata hai.

Wahi asymmetry phir se: agar `relevance_score` kisi bug ki wajah se khaali reh
gaya, to safe direction correction path hai, na ki unverified context pe answer
bol dena.

### Q9. Do alag `generate` node kyun nahi — ek local ke liye, ek web ke liye?

[build_graph.py:68-70](../backend/app/graph/build_graph.py#L68-L70)

Kyunki `generate` sirf `state["documents"]` padhta hai. Usko pata hi nahi hona
chahiye ki context kahan se aaya — wahi ek acha contract hai. Do nodes hote to
dono me wahi prompt aur wahi logic duplicate hoti, aur dono ko sath me badalna
padta.

Dono branches `generate` pe merge hote hain; source ka farak `source_type` field
rakhti hai, jo sirf UI ke badge aur eval ke liye hai.

---

## 3. `web_search_fallback.py` — correction path

[backend/app/nodes/web_search_fallback.py](../backend/app/nodes/web_search_fallback.py)

### Q10. **(Sabse zyada poochha jaane wala)** Web snippets ko local docs ke saath merge kyun nahi karte? Zyada context to behtar hota hai na?

[web_search_fallback.py:61-66](../backend/app/nodes/web_search_fallback.py#L61-L66)

**Nahi.** Local docs abhi-abhi `"no"` grade ho chuke hain — grader ne kaha ki
inme jawab nahi hai. Unhe context me rakhna:

1. Ache web context ko **dilute** karta hai
2. Wahi hallucination risk **wapas laata hai** jise hatane ke liye grading step
   banaya hi gaya tha

Poora grading step bekar ho jaata agar reject kiya hua material phir bhi prompt
me chala jaata. Isliye `documents` **replace** hota hai, append nahi.

Ye itna central hai ki iska apna test hai — `test_routing.py` me assert karta hai
ki fallback ke baad local docs context me nahi bache.

### Q11. `sources` bhi replace karte ho. Kyun?

[web_search_fallback.py:54-56](../backend/app/nodes/web_search_fallback.py#L54-L56)

Warna UI ek **web-sourced answer ke neeche local filenames cite** kar deta. Wo
user se jhooth hai — jawab un files se bana hi nahi.

Search fail hone wale path me bhi `sources: []` hai, usi wajah se.

### Q12. `except Exception` itna broad kyun? Ye to bad practice hai.

[web_search_fallback.py:48-59](../backend/app/nodes/web_search_fallback.py#L48-L59)

Yahan deliberate hai, aur comment me likha hai. Search fail hona **recoverable**
hai — rate limit, network, missing key, teeno ho sakte hain aur teeno pe sahi
behaviour ek hi hai.

Crash karne se poora request 500 ho jaata aur demo ruk jaata. Iske bajaye khaali
documents laut jaate hain, aur `generate` saaf keh deta hai ki context nahi
mila. Log me exception type aur message dono jaate hain, to debugging nahi
marti.

**Farak ye hai ki fail karna chup-chaap nahi hai** — trace me `FAILED` dikhta
hai, aur UI us step ko laal tick ke saath dikhati hai.

### Q13. URL snippet ke text me bhi hai aur `sources` list me bhi. Duplicate nahi hai?

[web_search_fallback.py:22-38](../backend/app/nodes/web_search_fallback.py#L22-L38)

Nahi — dono alag consumer ke liye hain. Text wala URL **LLM ke liye** hai taaki
wo answer me inline cite kar sake. List wala **UI ke liye** hai, structured
citations ke liye. Text se hata do to inline citation mar jaati hai.

---

## 4. `crag_state.py` — state design

[backend/app/schemas/crag_state.py](../backend/app/schemas/crag_state.py)

### Q14. **(Sabse gehra sawaal)** `logs` pe reducer hai, `documents` pe nahi. Kyun?

[crag_state.py:72](../backend/app/schemas/crag_state.py#L72)

```python
logs: Annotated[List[str], operator.add]
```

`logs` **additive** hai — har node ek line append karta hai. Kisi node ko ye
jaanne ki zaroorat nahi ki usse pehle kya chala, aur poora execution trace muft
me ban jaata hai. Wahi trace UI me dikhta hai.

`documents` **overwrite** hai (default behaviour, koi reducer nahi) — aur ye
poore project ka sabse important design decision hai. Agar yahan bhi
`operator.add` hota, to `web_search_fallback` ke snippets local docs ke saath
**jud** jaate. Wahi Q10 wali galti, sirf ab ek line ke reducer ki wajah se —
chup-chaap, bina kisi node ka code badle.

**Yaani ek Annotated line poore correction step ko bekar kar sakti hai.**

`sources` bhi isi wajah se overwrite hai.

### Q15. `initial_state()` alag function kyun hai? Har jagah dict bana lete.

[crag_state.py:76-92](../backend/app/schemas/crag_state.py#L76-L92)

`logs` ka additive reducer **list par** kaam karta hai — `None` pe crash karega.
To use `[]` se initialise karna hi padta hai. Wo ek jagah likhna, har call site
pe nahi, yaani ek hi jagah galti ho sakti hai.

Doosri baat, jo demo me kaam aati hai: **har request naya `initial_state()`
banati hai.** Koi checkpointer nahi, koi memory nahi — graph stateless hai.
Isiliye UI ki history saaf likhti hai ki wo ek *record* hai, conversation memory
nahi.

### Q16. `question` kabhi mutate kyun nahi hota?

Rewrite alag key me jaata hai — `transformed_query`. Original question ko badal
dete to trace me pata hi nahi chalta ki user ne kya poochha tha aur system ne
usko kya bana diya. Wo farak dikhana hi fallback path ka sabse convincing hissa
hai — UI me *"Rewritten for search: ..."* isi se aata hai.

---

## 5. Retrieval — hybrid + reranker

[backend/app/tools/reranker.py](../backend/app/tools/reranker.py)

### Q17. Bi-encoder aur cross-encoder me farak kya hai?

- **Bi-encoder (retriever):** query aur document ko **alag-alag** embed karta
  hai. Document vectors pehle se bane hote hain, query time pe sirf ek embedding
  + nearest-neighbour lookup. Isliye fast — aur isiliye query-document
  interaction dekh hi nahi sakta, kyunki dono kabhi ek saath model me jaate hi
  nahi.
- **Cross-encoder (reranker):** dono ko **ek saath** model me daalta hai, ek
  doosre ke context me padhta hai. Kaafi zyada accurate. Keemat: har
  (query, document) pair pe ek forward pass — poore corpus pe chalana namumkin.

Isiliye do-step: **sasta retriever candidates laata hai, mehnga reranker unme se
best chunta hai.**

### Q18. RRF me scores normalize kyun nahi karte?

[reranker.py:66-75](../backend/app/tools/reranker.py#L66-L75)

Vector search cosine **distance** deta hai (0 = best) aur BM25 ek unbounded
positive score (bada = best). Ye alag scales hain — inhe ek doosre me convert
karna corpus-specific tuning hai, aur wahi tuning kal doosre corpus pe galat ho
jaayegi.

RRF sirf **rank** use karta hai: `score(d) = Σ 1 / (60 + rank(d))`. Score ki
value kya thi, isse koi farak nahi padta. Isliye kisi bhi do retrievers ko fuse
kiya ja sakta hai bina unke scale jaane.

### Q19. `rerank()` fail hone pe exception kyun nahi phenkta?

[reranker.py:57-60](../backend/app/tools/reranker.py#L57-L60)

Reranking ek **improvement** hai, requirement nahi. Model load fail ho jaye to
retrieval phir bhi kaam karni chahiye — bas thodi kam accurate. Isliye original
order laut jaata hai (fail open).

Ulta hota — reranker na chale to poori query fail — to ek optional component
core path ko le doobta.

### Q20. Reranker ka point answer quality hai ya kuch aur?

Is project me **grader ka input** hai. `grade_documents` decide karta hai ki
local context kaafi hai ya nahi. Agar retrieval sahi chunk laayi par wo top-k me
neeche reh gaya, grader use dekh hi nahi paata aur galat `"no"` de sakta hai.
Reranker sahi chunk ko upar laata hai.

**Lekin** — Q5 yaad karo — grader chunks concatenate karta hai, to ordering uske
liye invisible hai. Isiliye A/B flat aaya. Ye do baatein ek saath rakhna:
reranker theory me grader ko madad kar sakta tha, par is grader ke design me
nahi kar sakta.

---

## 6. Eval — sabse zyada follow-up yahin aayega

### Q21. Routing accuracy 100% hai. Iska matlab router perfect hai?

**Nahi, iska matlab task aasan hai.** Corpus ka gap **categorical** hai —
concepts andar, vendor/pricing/news bahar — to zyadatar web cases ek obvious axis
pe alag hain. Ye maine hi design kiya tha, aur maine hi labels lagaye the.

Isiliye 8 **ambiguous** cases add kiye jinme corpus topic ko aadha cover karta
hai, aur unhe **correctness** se nahi **stability** se score kiya jaata hai —
kyunki unka sahi jawab genuinely debatable hai.

### Q22. Tumne khud corpus likha aur khud labels lagaye. Ye bias nahi?

**Bilkul hai, aur wo likha hua hai.** Isiliye BEIR SciFact laaya gaya: wahan
`local` cases ke labels dataset ke apne **qrels** se aate hain — expert
judgements ki kaunsa abstract kaunse claim ka jawab deta hai. Wo labels maine
nahi banaye.

`web` cases abhi bhi haath se likhe hain, aur wo bhi likha hua hai — par wo aasan
half hai: SciFact 2020-era scientific abstracts hain, to "aaj ka pricing" wale
sawaal usme ho hi nahi sakte.

### Q23. Latency ka number kyun nahi dikhate?

Kyunki naapa nahi ja saka, aur ye batana khud ek finding hai.

Pehla run file order me chala — pehle saare local cases, phir web. Result:
`local 13.7s vs web 18.5s`, local ki saaf jeet. **Artifact tha.** Per-case
timings dikhate hain ki case 5 ke baad sab 15–22s ho gaye, route chahe koi bhi
ho — Groq throttle kar raha tha, aur local cases pehle chale the, to poora
slowdown unke bucket me gira.

`interleave()` add kiya jo local/web alternate karta hai. Dobara chalaya:
`local 16.2s vs web 14.9s` — web **tez**, jo structurally impossible hai kyunki
wo strictly zyada kaam karta hai. Dono numbers noise the.

Isliye cost argument **LLM call counts** pe khada hai (local 3, web 4), jo
graph ki shakl se aate hain aur har run me exactly wahi rehte hain.

### Q24. "Missed fallback" aur "unnecessary fallback" me farak?

- **Missed fallback** — local jawab de diya jabki dena nahi chahiye tha.
  **Mehngi galti**: user ko galat context pe bana hua confident answer milta hai.
- **Unnecessary fallback** — web search kar liya jabki local docs kaafi the.
  **Sasti galti**: ek extra LLM call aur thodi latency, answer phir bhi sahi.

Dono corpora pe missed fallbacks **0** rahe. Router sirf sasti direction me
galat hua — aur ye ek design choice ka natija hai (Q2, Q8), ittefaq nahi.

### Q25. Hybrid + reranking add kiya to kya improve hua?

**Concepts corpus pe kuch nahi** — routing 20/20 dono me, stability 8/8 dono me.
Par retrieval sach me badla: 28 me se **27 sawaal alag chunks** se answer hue, 0
bilkul same.

Wajah Q5 me hai: grader ordering nahi padhta, aur 22-chunk corpus pe membership
badalne se topic shayad hi badalta hai.

**SciFact pe hila:** routing 75.0% → 78.6%, recall@k 65% → 70%. Par wo **exactly
ek case** hai 28 me se, aur ek gold document 20 me se — noise ke andar. Jo sabit
hua wo mechanism hai, magnitude nahi.

### Q26. To reranking bekar hai?

Nahi — **galat metric pe naapa gaya tha.** Reranking ko *answer* pe asar dikhana
chahiye (model kaunse passages se likhta hai), routing pe nahi. Isiliye baad me
**answer verdict** metric add kiya: SciFact claim-verification dataset hai, to
dataset khud batata hai ki gold abstract claim ko SUPPORT karta hai ya
CONTRADICT — aur naapa ja sakta hai ki hamara answer wahi kehta hai ya nahi.

Wo LLM-judge nahi hai: sahi-galat ka faisla dataset karta hai, model se sirf ek
*reading* nikaali jaati hai ki answer ne kya stand liya.

### Q27. SciFact pe 78.6% hai. Grader kharab hai?

**Ulta.** Baseline run pe correlation perfect tha:

| Gold document | Cases | Route | Sahi |
|---|---|---|---|
| Retrieved | 13 | local | **13 / 13** |
| Missed | 7 | web | 0 / 7 |

**Grader ne ek bhi apni galti nahi ki.** Har "routing failure" ek retrieval miss
tha jise grader ne theek pakda — usne chaar chunks dekhe jinme jawab tha hi
nahi, aur keh diya. 78.6% grader ko **under-report** karti hai; bottleneck
retrieval hai, grading nahi.

---

## 7. Ek test jaan-boojh ke todo

Padhne se zyada tez tareeka. Todo, dekho kya fail hota hai, phir wapas theek
karo.

**Exercise 1 — docs replace ka invariant**

[web_search_fallback.py:65](../backend/app/nodes/web_search_fallback.py#L65) me:

```python
"documents": snippets,                      # abhi
"documents": state["documents"] + snippets, # ye kar ke dekho
```

Phir `.\dev.ps1 test` chalao. Kaunsa test fail hota hai? Uska naam padho aur
socho ki wo test **kyun** likha gaya tha. Phir wapas theek karo.

**Exercise 2 — reducer**

[crag_state.py:35](../backend/app/schemas/crag_state.py#L35) me `documents` ko
`Annotated[List[str], operator.add]` bana do. Ab **koi node ka code nahi badla**
— phir bhi wahi bug aa gaya. Test chalao.

Ye samajhne ke liye sabse achha exercise hai ki state design code jitna hi
important hai.

**Exercise 3 — default direction**

[build_graph.py:41](../backend/app/graph/build_graph.py#L41) me condition ko
ulta likh do:

```python
return "generate" if state.get("relevance_score") == "yes" else "transform_query"   # abhi
return "transform_query" if state.get("relevance_score") == "no" else "generate"    # ye kar ke dekho
```

Dono `"yes"` aur `"no"` pe **bilkul same** behave karte hain. Ab socho: agar
`relevance_score` khaali reh gaya (koi bug, ya grader ka naya output format), to
dono me kya hoga? Kaunsa version safe hai, aur kyun?

Ye test se nahi pakda jaayega — koi test khaali `relevance_score` nahi bhejta.
Isiliye ye exercise sabse kaam ki hai: kuch faisle test se nahi, sirf soch ke
pakde jaate hain.

---

## Agar kuch na aaye

Jo sawaal atka, us file ko kholo aur uske docstring padho — har faisle ki wajah
wahin likhi hai. Phir sawaal dobara bina dekhe bolo.

Aur agar koi sawaal ka jawab **tujhe theek na lage** — wo bhi valid hai. Bol
dena, discuss karenge. Apne hi code se disagree kar pana usse ratta maarne se
behtar hai.
