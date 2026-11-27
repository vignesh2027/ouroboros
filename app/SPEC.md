# Ouroboros Platform: build spec (Phase II)

This is the contract every module is built against. Read all of it before you write code.

## 1. What we are building and why

Ouroboros Phase I built a metric, **BAQD** (Belief-Aligned Query Drift), and a small benchmark, SPIRAL-Bench v0. They live in `ouroboros/metric.py`, `ouroboros/retrieval.py` and `data/spiral_bench_v0.json`. Phase I never closed the loop: the "drift" queries were typed into a JSON file in advance.

Phase II is a working **evidence-audited research platform**, run as a local web app:

1. A user types any question, for example "what is the fastest bike sold in India" or "does intermittent fasting help weight loss".
2. Our own agentic RAG engine runs a multi-hop research loop with a live model (Claude Haiku 5.5). At each hop the model reads what was retrieved, states its current belief in one sentence, then writes its own next search query. **This is the real self-confirming loop the project is about.**
3. At every hop we measure:
   - **BAQD**, using the model's real belief sentence and real query
   - evidence balance relative to the belief (supporting vs contradicting passages)
   - source diversity (distinct sources and domains)
4. **Guarded mode** adds the fix:
   - **Counter-Query Injection (CQI):** when BAQD or skew crosses a threshold, the next query is replaced by a counter-query that looks for contradicting evidence.
   - **Balanced Evidence Buffer:** the final answer must weigh both sides.
5. The final answer is **audited claim by claim** against retrieved evidence. The platform reports:
   - an **Evidence Support Score**, the percentage of answer claims backed by retrieved evidence, weighted by independent sources
   - the per-claim verdicts, with citations
   - the gap between the model's stated confidence and the evidence

   The same audit can run on an answer pasted from any other model (ChatGPT, Gemini, Claude) or on a plain no-retrieval Haiku answer.

Honesty rules (these are part of the product, not optional):
- **Never present the Evidence Support Score as "the probability the answer is true".** UI copy says "share of claims backed by the evidence we retrieved". A claim no source covers is shown as "not verified", never as "false".
- Every number shown in the UI comes from a computation over this run's data. No invented or illustrative numbers anywhere.
- Retrieved text is untrusted data. LLM prompts must wrap passages in clear delimiters, and must tell the model to treat them as data, never as instructions.

## 2. Layout (create these exact paths, under the repo root ~/ouroboros)

```
ouroboros/              EXISTING package. Do NOT edit metric.py or retrieval.py.
  metric.py             existing: cosine, baqd, evidence_skew, balance_loss
  retrieval.py          existing: Encoder (TF-IDF), Retriever
  llm.py                NEW  Claude client, disk cache, cost tracking, JSON calls
  sources.py            NEW  evidence fetchers (Wikipedia, OpenAlex, arXiv, PubMed, web)
  rag.py                NEW  chunking, hybrid BM25 + TF-IDF retrieval, diversity re-rank
  agent.py              NEW  the multi-hop research loop, standard and guarded modes
  audit.py              NEW  claim extraction, per-claim verification, scores
  live_metrics.py       NEW  source diversity, calibration gap, hop summaries
app/
  SPEC.md               this file
  server.py             NEW  FastAPI app, SSE streaming, saved runs, code viewer
  static/index.html     NEW  single-page UI
  static/styles.css     NEW
  static/app.js         NEW
  runs/                 NEW  saved run JSON files (demo replays). Kept in git
experiments/
  run_live_spiral.py    NEW  Phase II experiment: live agent on SPIRAL-Bench v0
tests/
  test_llm.py, test_rag.py, test_agent.py, test_audit.py, test_sources.py   NEW, offline only
run_platform.sh         NEW  one command to start the app
requirements.txt        add: anthropic, fastapi, uvicorn[standard]
```

A venv already exists at `~/ouroboros/.venv` (Python 3.13). Its packages:
- anthropic 2.14
- fastapi 0.165
- uvicorn
- numpy
- scikit-learn
- matplotlib

Use `.venv/bin/python`. Do not add other third-party packages; use the standard library (urllib, json, concurrent.futures, html.parser, xml.etree) for HTTP and parsing.

**No em dashes anywhere** (code comments, UI copy, docs). Use commas, colons or full stops. No emoji in UI copy.

## 3. Module contracts

All functions are synchronous unless stated otherwise. Type hints are welcome.

### 3.1 `ouroboros/llm.py`

```python
MODEL = "claude-haiku-5-5"   # user's explicit choice: cheap, fast, uses his free credit

class LLM:
    def __init__(self, cache_dir: str = "outputs/.cache/llm", offline: bool = False): ...
    def json(self, system: str, user: str, schema: dict, max_tokens: int = 2000,
             effort: str = "low", tag: str = "") -> dict: ...
    def text(self, system: str, user: str, max_tokens: int = 2000,
             effort: str = "low", tag: str = "") -> str: ...
    usage: dict   # running totals: calls, cached_calls, input_tokens, output_tokens, cost_usd
```

**Credentials**, in this order:
1. the `ANTHROPIC_API_KEY` env var, giving `anthropic.Anthropic()`
2. the `ANTHROPIC_AUTH_TOKEN` env var
3. the file `~/.config/anthropic/credit-key`, read as an OAuth bearer token

For cases 2 and 3, build the client with:
```python
anthropic.Anthropic(auth_token=token, api_key=None, default_headers={"anthropic-beta": "oauth-2025-04-20"})
```
This exact form was verified to work on this machine. **Never print, log or return the token.**

**JSON calls** use structured outputs:
```python
client.messages.create(
    model=MODEL,
    max_tokens=...,
    system=...,
    messages=[{"role": "user", "content": user}],
    output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
)
```
This was verified on Haiku 5.5 and returns a single text block holding JSON. Schemas must use `additionalProperties: false` and list every property in `required`. Parse the result with `json.loads`.

**Model rules:**
- Do not pass `temperature`, `top_p`, `top_k` or `thinking`.
- Always check `stop_reason`. On `"refusal"`, raise `LLMRefusal`. On `"max_tokens"`, retry once with double `max_tokens`.

**Disk cache:**
- The key is the sha256 of `MODEL + system + user + json.dumps(schema, sort_keys=True) + effort`.
- Store one JSON file per key.
- A cache hit increments `usage["cached_calls"]` and costs nothing.
- With `offline=True`, a cache miss raises `LLMOffline`. This is how demo replays and the tests run with no network.

**Cost:** Haiku 5.5 costs $0.10 per 1M input tokens and $0.50 per 1M output tokens. Compute `cost_usd` from `response.usage`.

**Errors:** catch the anthropic typed errors in a chain (RateLimitError, then APIStatusError, then APIConnectionError) and re-raise as `LLMError` with a short message.

**Concurrency:** make the cache safe for concurrent use. Write to a temp file, then `os.replace`.

### 3.2 `ouroboros/sources.py`

```python
@dataclass
class Document:
    doc_id: str          # stable: sha1(url)[:12]
    source: str          # "wikipedia" | "openalex" | "arxiv" | "pubmed" | "web"
    title: str
    url: str
    domain: str          # e.g. "en.wikipedia.org", "doi.org/10.1016" style host for papers
    text: str            # plain text, whitespace-normalised, max ~6000 chars
    year: int | None
    meta: dict           # free-form (authors, venue, cited_by_count)

def search_all(query: str, per_source: int = 4, sources: list[str] | None = None,
               cache_dir: str = "outputs/.cache/sources", offline: bool = False) -> list[Document]
```

**Fetchers** run in parallel with a ThreadPoolExecutor. Each fetcher has a 12 s timeout. A failing fetcher logs, returns `[]`, and never raises.

- **wikipedia:** `https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch=...&format=json&srlimit=N`. Then fetch plain extracts with `action=query&prop=extracts&explaintext=1&exintro=0&titles=...`, truncating each to about 6000 chars.
- **openalex:** `https://api.openalex.org/works?search=...&per-page=N&filter=has_abstract:true`. Rebuild the abstract from `abstract_inverted_index`. The text is title plus abstract. The url is the DOI or the OpenAlex id. Add `mailto` only if it's a generic placeholder; **never put the user's email in a URL**.
- **arxiv:** `https://export.arxiv.org/api/query?search_query=all:...&max_results=N`, parsing the Atom feed (title and summary).
- **pubmed:**
  1. esearch: `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=...&retmode=json&retmax=N`
  2. efetch: `...&rettype=abstract&retmode=xml`, parsing ArticleTitle and AbstractText
- **web:** POST or GET `https://html.duckduckgo.com/html/?q=...`.
  - Parse the result links and snippets with html.parser.
  - Unwrap `duckduckgo.com/l/?uddg=` redirect links.
  - Then fetch up to `per_source` result pages, strip tags (script, style, nav), and keep about 6000 chars of visible text.
  - If a page fetch fails, use the snippet as the text.

All fetchers send the User-Agent `OuroborosResearch/0.2 (academic project)`, and no personal data in any header or URL.

**Cache:** each `(source, query, per_source)` result goes to disk as JSON. With `offline=True`, a miss returns `[]`.

**Source selection:** `default_sources(question)` returns all five. The agent can pass a subset.

### 3.3 `ouroboros/rag.py` (our RAG system)

```python
@dataclass
class Passage:
    pid: str            # f"{doc_id}#{i}"
    doc_id: str; source: str; title: str; url: str; domain: str; year: int | None
    text: str           # 2 to 4 sentences, about 60 to 120 words
    score: float = 0.0

def chunk(doc: Document, max_words: int = 110) -> list[Passage]
class EvidencePool:
    """All passages seen in a run. Grows as hops fetch more documents."""
    def add_documents(self, docs: list[Document]) -> int            # returns new passage count
    def search(self, query: str, k: int = 6, exclude: set[str] = frozenset(),
               diversity: float = 0.5) -> list[Passage]
    def get(self, pid: str) -> Passage
    def __len__(self) -> int
```

**`search` scores the hybrid** `0.5 * bm25_norm + 0.5 * tfidf_cosine`:
- BM25: implement Okapi BM25 yourself (k1 = 1.5, b = 0.75) over lowercase word tokens, with a small English stop list.
- TF-IDF: reuse `ouroboros.retrieval.Encoder`, refitting it lazily when the pool has grown since the last fit.

**Then MMR-style diversity re-ranking:** penalise a candidate that shares a `doc_id` or `domain` with passages already picked, so that a single website can't fill the top k. `diversity = 0` turns this off.

The methods must be deterministic: no randomness, with a stable tie-break on `pid`.

### 3.4 `ouroboros/agent.py`

```python
@dataclass
class AgentConfig:
    mode: str = "guarded"          # "standard" | "guarded"
    hops: int = 4
    k: int = 6                     # passages read per hop
    per_source: int = 3            # documents fetched per source per hop
    sources: list[str] | None = None
    baqd_threshold: float = 0.05   # CQI fires when BAQD(n) > this ...
    skew_threshold: float = 0.5    # ... or |skew| at this hop >= this
    corpus: list[Passage] | None = None   # closed-corpus mode (SPIRAL-Bench): no web fetching

def run(question: str, cfg: AgentConfig, llm: LLM, emit=lambda event: None) -> dict
```

**Each hop:**
1. **query:**
   - hop 1 is the user's question itself
   - later hops use the query the model wrote at the end of the previous hop
   - in guarded mode the query can be replaced by CQI (see below)
2. **fetch:** `search_all(query)`, then `pool.add_documents`. Skip this in closed-corpus mode.
3. **retrieve:** `pool.search(query, k, exclude=already_read)`.
4. **read:** one `llm.json` call, given the question, the belief so far, and the retrieved passages (each with its pid). It returns:
   ```json
   {"stances": [{"pid": "...", "stance": "supports"|"contradicts"|"neutral", "reason": "max 20 words"}],
    "belief": "one sentence: what you now believe the answer is",
    "confidence": 0-100,
    "next_query": "the search you would run next to finish answering (max 14 words)"}
   ```
   The **stance is judged relative to the belief written in this same call**. That is the agent's own view. Neutral means off-topic or not taking a side.
5. **metrics:**
   - `baqd(query_vec, prev_belief_vec, question_vec)`, using the `Encoder` fitted on the pool plus every query and belief text so far. Hop 1 has no previous belief, so record `baqd: null` (Phase I's degenerate 0 is gone).
   - support and contradict counts, `skew = (s - c) / max(1, s + c)` and `balance_loss = |skew|`
   - the number of distinct domains and sources in this hop's passages
   - the cumulative evidence (all read passages and their stances)
6. **guard** (guarded mode only), before using `next_query` for hop n+1:
   - If `BAQD(n) > baqd_threshold` or `|skew(n)| >= skew_threshold`, fire CQI.
   - CQI is one `llm.json` call that writes a counter-query looking specifically for evidence contradicting the current belief. It returns `{"counter_query": "...", "why": "..."}`.
   - Emit `{"type": "cqi", ...}` with the original and the counter-query.
   - The counter-query is what is searched at hop n+1.

**After the last hop: synthesis.** One `llm.json` call over all passages marked supports or contradicts, plus the 4 best neutral ones. It returns:
```json
{"answer": "120-220 words, plain prose, every factual sentence ends with [pid] citations",
 "confidence": 0-100,
 "one_line": "max 25 words"}
```
- In guarded mode, the prompt **must** require both sides to be weighed when contradicting evidence exists (the Balanced Evidence Buffer). The passages go in two labelled groups, supporting and contradicting.
- In standard mode the passages go in one list.

**Then** call `audit.audit_answer(question, answer, pool, llm, cited_pids=...)` and attach the result.

**Events emitted** (the server streams these to the UI; `emit` gets a dict):

```
{"type":"start", "question", "mode", "config":{...}}
{"type":"hop_query", "hop", "query", "origin": "question"|"model"|"counter"}
{"type":"hop_sources", "hop", "fetched": {"wikipedia": 3, ...}, "pool_size"}
{"type":"hop_read", "hop", "passages":[{pid,title,url,domain,source,year,text,stance,reason}],
     "belief", "confidence", "next_query"}
{"type":"hop_metrics", "hop", "baqd": float|null, "support", "contradict", "neutral",
     "skew", "balance_loss", "domains", "sources"}
{"type":"cqi", "hop", "trigger":{"baqd", "skew"}, "original_query", "counter_query", "why"}
{"type":"synthesis", "answer", "confidence", "one_line"}
{"type":"audit", "report":{...see audit}}
{"type":"done", "run_id", "usage":{calls, cached_calls, input_tokens, output_tokens, cost_usd}, "seconds"}
{"type":"error", "message"}
```

**The return value** is the full run record: `question`, `mode`, `config`, `hops` (a list of per-hop dicts merging the hop events), `cqi_events`, `synthesis`, `audit`, `usage`, `seconds`. It must be JSON-serialisable.

### 3.5 `ouroboros/audit.py`

```python
def audit_answer(question: str, answer: str, pool: EvidencePool, llm: LLM,
                 cited_pids: list[str] | None = None, fetch_more: bool = True,
                 sources: list[str] | None = None) -> dict
```

**Steps:**
1. **extract:**
   - Split the answer into atomic factual claims with one `llm.json` call, max 10 claims: `{"claims":[{"cid","text","cited_pids":[]}]}`.
   - The cited pids are parsed from `[pid]` markers in the answer when present.
   - Answers pasted from other models have none.
2. **evidence per claim:**
   - Use `pool.search(claim, k=4)`.
   - If `fetch_more` and the pool is small (under 30 passages), first run `search_all(claim, per_source=2)` for the 3 claims with the least coverage.
3. **verify:**
   - One `llm.json` call per claim, given the claim and its passages (with pids). Run these concurrently in a ThreadPoolExecutor of 6.
   - It returns `{"verdict": "supported"|"contradicted"|"mixed"|"not_verified", "evidence":[{"pid","relation":"supports"|"contradicts"}], "note": "max 25 words"}`.
   - The verdict must rest **only** on the passages given.
4. **scores** (pure Python, no LLM):
   - Count the independent sources for each claim: the distinct domains among its supporting pids.
   - `evidence_support_score = 100 * sum(w_i for supported claims) / sum(w_i)`, where `w_i = 1` and supported means a verdict of "supported" with at least 1 supporting pid. Mixed counts as half.
   - `multi_source_share`: the % of supported claims backed by 2 or more distinct domains.
   - `contradicted_share`: the % of claims with a "contradicted" verdict.
   - `unverified_share`: the % of claims verified as "not_verified".
   - `citation_faithfulness`: of the claims that had cited pids, the % whose cited pids appear among their supporting evidence. It is `null` when nothing was cited.
   - `distinct_domains`: the count over all evidence used.
   - `calibration_gap = stated_confidence - evidence_support_score`, where `stated_confidence` is passed in through an optional `stated_confidence: int | None = None` argument.
   - `grade`: "Well supported" (score 80 or more and multi_source 50% or more), "Partly supported" (50 or more), "Weakly supported" (otherwise), "Contradicted by evidence" (contradicted_share 30% or more overrides the others).
5. **return** `{"claims":[{cid,text,verdict,note,evidence:[{pid,relation,title,url,domain,source}],independent_sources}], "scores":{...}, "grade", "pool_size"}`

```python
def plain_answer(question: str, llm: LLM) -> dict
```
A no-retrieval Haiku answer, 120 to 200 words, in the form `{"answer", "confidence"}`. It is used by "Compare with a plain model answer".

### 3.6 `ouroboros/live_metrics.py`

These are small pure functions used by agent and audit:
- `source_diversity(passages)`, which returns `{domains, sources, top_domain_share}`
- `calibration_gap(conf, score)`
- `run_summary(run)`, which returns `{mean_baqd (hops 2+), max_baqd, final_skew, cqi_count, domains_total, evidence_support_score}`

Unit tests are required for each.

## 4. Server: `app/server.py`

FastAPI. Run it with `.venv/bin/python -m uvicorn app.server:app --port 8000` from the repo root.

| Method | Path | What it does |
|---|---|---|
| GET | `/` | `static/index.html` |
| GET | `/static/*` | static files |
| GET | `/api/health` | `{ok, model, credentials: "api_key"\|"oauth_token"\|"none", offline}`. Never the token |
| GET | `/api/research/stream?q=...&mode=guarded\|standard&hops=4` | SSE stream of agent events, one `data: <json>\n\n` per event, with a keep-alive comment every 10 s. On finish, save the run to `app/runs/<run_id>.json` (run_id = a slug of the question plus mode plus a short hash) |
| GET | `/api/compare/stream?q=...` | Runs the standard and guarded agents concurrently in two threads on the same question. Every event gains `"lane": "standard"\|"guarded"`. A final `{"type":"compare_done","summary":{...run_summary per lane}}`. Both lanes share one LLM cache |
| POST | `/api/audit` | JSON `{question, answer, model_name}`. Audits any pasted answer and returns the audit report (fetch_more=True, new pool) |
| POST | `/api/plain` | JSON `{question}`, returning `plain_answer` plus its audit |
| GET | `/api/runs` | list of saved runs: `[{run_id, question, mode, grade, score, saved_at}]` |
| GET | `/api/runs/{run_id}` | a saved run record. The UI replays it with the same renderer (instant) |
| GET | `/api/benchmark` | `{phase1: <parsed outputs/traces.jsonl + outputs/diagnostic.json summary>, phase2: <outputs/live_spiral.json if present>}` |
| GET | `/api/code?path=...` | the source text of an allow-listed file only: `ouroboros/*.py`, `app/server.py`, `experiments/run_live_spiral.py`, `tests/*.py`, `run_experiment.py`, `run_diagnostic.py`. Reject anything else with 404, including path traversal |
| GET | `/api/tests` | contents of `outputs/test_report.json` if present |

- Use a thread plus `queue.Queue` bridge for SSE, so the sync agent can stream through a `StreamingResponse`.
- Add the `OFFLINE=1` env var: the LLM and sources run in offline mode, so only cached work runs.
- Errors become an `error` event, never a crash.

## 5. UI: `app/static/` (index.html, styles.css, app.js)

Plain HTML, CSS and JS with no framework, no build step and no CDN dependencies. It must work with no internet except for the API itself, so use system font stacks.

**Audience:** college reviewers, many not technical, plus examiners who will ask how it works. **Design:** professional, calm, simple, like a research instrument, not a chatbot toy. Not generic AI-purple.

**Visual direction:**
- **Palette:**
  - ground: off-white paper (#F6F7F9)
  - surface: white
  - ink: deep slate (#1B2430)
  - one accent: deep teal (#0E6E6E) for "guarded / Ouroboros"
  - standard agent: warm graphite (#6B5E57)
  - semantic: supports = green #2E7D4F, contradicts = brick #B23A2E, neutral = grey #8A94A3, not verified = amber #B7791F
- **Dark mode** via `prefers-color-scheme` with token variables.
- **Type:**
  - a system UI stack for text
  - a system monospace stack for queries and pids
  - **queries are shown large**, because the query text is the evidence
- **Layout:**
  - a top bar with the name "Ouroboros" and the tagline "Research answers you can check"
  - tabs: **Research**, **Compare**, **Audit an answer**, **Benchmark**, **How it works**
  - responsive down to phone width

**Research tab:**
- a big question box with 6 example chips:
  - "Is intermittent fasting effective for weight loss?"
  - "Which is the fastest production motorcycle sold in India?"
  - "Does remote work increase productivity?"
  - "Is nuclear power a good way to cut carbon emissions?"
  - "Should adults take vitamin D supplements daily?"
  - "Does raising the minimum wage reduce employment?"
- a mode toggle (Guarded / Standard) and Run
- the live **hop timeline**: one card per hop, filled in as events arrive. Each card shows:
  - the query in large monospace, with an origin badge: "Your question", "Agent wrote this", or "Counter-query injected" in teal
  - the sources fetched
  - the passages as compact rows with stance chips, title, domain, an expandable text and a link
  - the belief sentence with confidence
  - a metrics strip: BAQD with a tiny bar, a support/contradict balance bar, domains
- a CQI banner between hops when it fires
- **the final answer** with clickable `[pid]` citations that scroll to and highlight the passage
- **the Evidence Report card:**
  - the big Evidence Support Score % and grade
  - a sub-line: "share of claims backed by the evidence we retrieved"
  - stat tiles: claims checked, independent domains, multi-source share, contradicted, not verified, citation faithfulness, model confidence vs evidence (the gap)
  - a claim table with verdict chips and evidence links
- **a BAQD-by-hop sparkline** in SVG, drawn to scale with labelled axes
- a cost line, for example "14 model calls, 9.2k tokens, $0.003"
- a "Saved runs" drawer listing `/api/runs`, which replays a run instantly

**Compare tab:** a two-column split, Standard agent (graphite) against Ouroboros guarded (teal), on the same question, streaming side by side. Underneath, a comparison table of the run summaries: mean BAQD, final skew, CQI count, domains, support score, contradicted share.

**Audit an answer tab:**
- a question field, a model name select (ChatGPT, Gemini, Claude, Other) and a textarea to paste the answer
- also a "Get a plain model answer" button that uses `/api/plain`
- shows the same Evidence Report card

**Benchmark tab:**
- Phase I (scripted queries, TF-IDF, closed corpus): the numbers from outputs/, honestly labelled as a null result, plus the oracle diagnostic
- Phase II (live agent, closed SPIRAL-Bench corpus): standard against guarded per question (BAQD by hop, balance loss, CQI count) from `/api/benchmark`
- If phase2 is missing, show "Not run yet" and the command to run it

**How it works tab:**
- a clean SVG pipeline diagram: Question, Search sources, Our RAG (chunk, BM25 + TF-IDF, diversity), Read (belief + stances), Measure (BAQD, balance, diversity), Guard (CQI), Synthesize (balanced buffer), Audit (claims, evidence, score)
- the BAQD formula
- a short plain-language explanation for non-technical reviewers
- a code browser: a file list from the allow-list and a viewer (`/api/code`) with line numbers
- the test results from `/api/tests`

**Quality bar:**
- No layout shift jank. Accessible contrast, visible focus states, `prefers-reduced-motion` respected.
- Every element shown at rest (no opacity-0 waiting for observers).
- Streaming renders progressively.
- Errors are shown inline in plain words.
- Copy in the UI is plain English, active voice, with no em dashes and no emoji.

## 6. Experiment: `experiments/run_live_spiral.py`

The Phase II experiment, on the SPIRAL-Bench v0 closed corpus:
- **Corpus:** each question's 8 passages become `Passage` objects (pid = `f"{qid}#{i}"`).
- **Runs:** each of the 8 questions in both modes, standard and guarded, with hops = 4, k = 3 (top-3 of 8, smaller than Phase I's top-4, so that collapse is possible), and the LLM live and cached.
- **Records:**
  - BAQD by hop, using the real model-written queries and beliefs
  - the skew and balance loss, using **ground-truth stances from the JSON**, not LLM stances
  - the CQI count
  - final answer confidence
- **Writes** `outputs/live_spiral.json` and prints a table: mean balance loss at the last hop by mode, mean BAQD at hops 2 to 4, and the settled-question control.
- **Conclusions are computed from the numbers, never hard-coded.** If guarded shows no improvement, say so.
- The CLI takes `--offline` to replay from the cache.

## 7. Tests

- Offline only. Use a `FakeLLM` that returns canned JSON keyed by the `tag`, and fake sources.
- Cover:
  - chunking
  - BM25 ranking order
  - diversity re-rank (two passages from one domain do not both take the top 2 when diversity = 1)
  - the agent loop event order and the CQI trigger
  - audit scoring maths (the grade boundaries)
  - the llm cache key and offline miss
  - the code-endpoint allow-list and path traversal rejection
  - the live_metrics functions
- The existing `python3 run_tests.py` must still pass (43 cases). New tests run with `.venv/bin/python -m unittest discover -s tests -t .`

## 8. Rules for everyone

- Do not edit `ouroboros/metric.py`, `ouroboros/retrieval.py`, `data/`, `docs/`, `run_experiment.py` or `run_diagnostic.py`, or anything in `outputs/` other than files you create.
- Do not commit or push. Do not touch git.
- Keep secrets out of logs, files, URLs and responses.
- Spend no more than about $1 of Haiku credit on development and testing. Cache everything.
