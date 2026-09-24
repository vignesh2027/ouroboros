# OUROBOROS

**Detecting self-confirming retrieval loops in agentic RAG.**

[![experiments](https://github.com/vignesh2027/ouroboros/actions/workflows/ci.yml/badge.svg)](https://github.com/vignesh2027/ouroboros/actions/workflows/ci.yml)
[![dataset](https://img.shields.io/badge/dataset-SPIRAL--Bench-yellow)](https://huggingface.co/datasets/vigneshwar234/spiral-bench)
[![license](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

Project page: **https://vignesh2027.github.io/ouroboros**
Dataset: **https://huggingface.co/datasets/vigneshwar234/spiral-bench**

---

## The problem

An agentic RAG system searches several times, and it writes each follow-up query itself, using
what it currently believes. A retriever ranks documents by how closely they match the wording of
the query it receives.

Those two facts close a loop. Belief shapes the query, the query shapes the evidence, and the
evidence hardens the belief. Opposing studies are never deleted, they are simply never asked for
again.

Nothing false is ever produced. Every document is authentic, every citation checks out, and a
faithfulness scorer rates the answer as fully faithful. It is a **sampling failure, not a truth
failure**, which is why existing safeguards cannot see it. They all read the answer. None of them
read the query.

## Result

On a corpus balanced by construction, an **oracle query** built only from vocabulary unique to one
side retrieves **100% supporting** evidence, and the reverse oracle retrieves **100% opposing**
evidence.

| Measure | Value |
|---|---|
| Range of retrieved evidence reachable by query wording alone | **2.00** |
| Share of that range captured by our first hand-written drift queries | **4.2%** |
| Vocabulary shared between supporting and opposing passages | **12.9%** |

Query wording alone controls which evidence comes back. That is the half of the loop this
experiment set out to test.

The drift metric computed over a TF-IDF encoder stayed **flat**, a null result that points at the
encoder rather than at the mechanism. Short queries share few literal words with long belief text,
so a lexical encoder measures vocabulary overlap instead of meaning.

![results](docs/results.png)

## The metric

BAQD, or Belief-Aligned Query Drift, asks one question at every hop: is the query the system just
wrote closer to what it already believes than the user's neutral question was?

```
BAQD(n) = cos(query_n, belief_n-1) - cos(question_0, belief_n-1)
```

Three embeddings, two cosine similarities, one subtraction. No training, no labelled data, no GPU.

## Layout

```
ouroboros/metric.py          BAQD and evidence skew
ouroboros/retrieval.py       TF-IDF encoder and cosine retriever
data/spiral_bench_v0.json    SPIRAL-Bench v0, 8 questions, 64 passages
run_experiment.py            Experiment 1, drift arm versus neutral arm
run_diagnostic.py            Locates the cause of the null result
make_chart.py                Builds the results figure
scripts/build_hf_dataset.py  Flattens the corpus for the Hub, checks balance
outputs/traces.jsonl         One row per retrieval, 48 rows
docs/                        Project page published to GitHub Pages
```

## Reproduce

No GPU, no API key, no model download.

```bash
pip install -r requirements.txt

python3 run_experiment.py    # 48 retrievals, two arms
python3 run_diagnostic.py    # oracle comparison
python3 make_chart.py        # rebuilds the figure
```

Continuous integration runs all three on every push, so the numbers above are checked rather than
asserted.

## Honest limitations

1. The passages are **synthetic** research-style text written for this prototype. They describe
   real findings in outline but are not quotations and must not be cited as literature.
2. The benchmark is **small**: 8 questions, 64 passages.
3. Queries in v0 are **authored probes, not agent output**. Whether a live model writes queries
   like these is the open question.
4. Balance is balanced **by construction**, not by sampling from a real corpus.

## Next

A dense sentence encoder in place of TF-IDF, a live model writing its own follow-up queries, and a
larger question set.

## Team

Department of Artificial Intelligence and Data Science, Project Phase I.

| Member | Register number | Coordinates | GitHub |
|---|---|---|---|
| Harshavarthini M | TU6230103110012 | Dataset and evidence verification | [@Harsha2006-M](https://github.com/Harsha2006-M) |
| Sadhithiya V | TU6230103110024 | Literature, documentation, demo | [@sadhithiya2005-ship-it](https://github.com/sadhithiya2005-ship-it) |
| Vigneshwar L | TU6230103110040 | Pipeline and metric implementation | [@vignesh2027](https://github.com/vignesh2027) |

All three members take part in every stage. The third column shows who coordinates that part of
the work, not who works on it alone.

Project guide: **Dr. Senthil**, Networking and Database.

## License

MIT. Author: Vigneshwar L.
