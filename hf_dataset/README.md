---
license: mit
task_categories:
  - question-answering
  - text-retrieval
language:
  - en
tags:
  - retrieval-augmented-generation
  - rag
  - agentic-rag
  - retrieval-bias
  - evidence-balance
  - evaluation
pretty_name: SPIRAL-Bench v0
size_categories:
  - n<1K
configs:
  - config_name: passages
    data_files: passages.jsonl
  - config_name: queries
    data_files: queries.jsonl
  - config_name: traces
    data_files: traces.jsonl
---

# SPIRAL-Bench v0

A small benchmark for testing whether the **wording of a retrieval query** changes the
**balance of the evidence** a retriever returns.

Built for the Ouroboros project, which studies self-confirming retrieval loops in agentic RAG.

## The question this dataset exists to answer

In agentic RAG, the system writes its own follow-up search queries, and it writes them using
what it currently believes. A retriever ranks documents by how closely they match the wording
of the query it receives. If those two facts combine, an agent can retrieve progressively
more one-sided evidence without any document being false and without any attacker involved.

Testing that claim needs a corpus where **balance is guaranteed rather than assumed**. That is
what this dataset provides.

## What is in it

Three configs.

### `passages` (64 rows)

Every contested question carries exactly four supporting and four opposing passages, so the
evidence is balanced **by construction**. Settled questions are deliberately one-sided and act
as a control.

| field | description |
|---|---|
| `question_id` | short identifier, for example `ev_cost` |
| `question` | the neutral question a user would ask |
| `question_type` | `contested` or `settled` |
| `passage_id` | unique passage identifier |
| `stance` | `1` supporting, `-1` opposing |
| `stance_label` | `supporting` or `opposing` |
| `text` | the passage |

### `queries` (48 rows)

Two query sequences per question, three hops each, for a controlled comparison.

| arm | what it does |
|---|---|
| `drift` | wording bends toward the belief, for example *"is an electric car cheaper than petrol"* becomes *"savings from owning an electric car"* |
| `neutral` | wording stays a neutral restatement across all three hops |

Everything else is held fixed between the arms, so any difference in retrieved balance is
attributable to wording alone.

### `traces` (48 rows)

The logged output of the first experiment: one row per retrieval, carrying the query, the
drift score, the support and oppose counts, and the retrieved passages.

## Questions covered

**Contested** (balanced 4 / 4): electric vehicle ownership cost, vitamin D supplementation,
remote work productivity, minimum wage and employment, intermittent fasting, nuclear power.

**Settled** (one-sided control): smoking and lung cancer, measles vaccine effectiveness.

## Result obtained on this dataset

Handing the retriever an **oracle query**, built only from vocabulary unique to one side,
retrieves **100% supporting** evidence. The reverse oracle retrieves **100% opposing** evidence.

So query wording alone moves retrieved evidence across a range of **2.00**, on a corpus that is
verifiably balanced. Supporting and opposing passages share only **12.9%** of their vocabulary,
so stance is separable in principle.

Hand-written drift queries captured only **4.2%** of that available range, and a drift metric
computed over a TF-IDF encoder stayed flat. The mechanism is available; the first probe was too
weak to trigger it.

## Honest limitations

Read these before using the dataset.

1. **The passages are synthetic.** They are research-style text written for this prototype, not
   excerpts from real papers. Claims inside them describe real findings in outline, but they are
   not quotations and must not be cited as literature.
2. **It is small.** 8 questions and 64 passages. Enough to test a mechanism, not enough for
   statistical claims about model behaviour.
3. **Queries in v0 are authored, not agent-generated.** They are deliberate probes written to
   represent belief-aligned drift. Whether a live language model writes queries like these is an
   open question this dataset does not answer.
4. **Balance is balanced by construction, not by sampling.** Real corpora are not balanced, and
   results here should not be read as an estimate of real-world evidence distributions.

## Loading

```python
from datasets import load_dataset

passages = load_dataset("vigneshwar234/spiral-bench", "passages", split="train")
queries  = load_dataset("vigneshwar234/spiral-bench", "queries",  split="train")
traces   = load_dataset("vigneshwar234/spiral-bench", "traces",   split="train")
```

## Reproducing the experiment

Code lives in the Ouroboros repository. It needs numpy, scikit-learn and matplotlib, and runs
on a laptop CPU with no GPU, no API key and no model download.

```bash
python3 run_experiment.py
python3 run_diagnostic.py
```

## Planned for v1

A larger question set, a dense sentence encoder in place of TF-IDF, and query sequences written
by a live language model rather than by hand.

## Citation

```bibtex
@misc{spiralbench2026,
  title  = {SPIRAL-Bench: a balanced-evidence benchmark for retrieval query bias},
  author = {Vigneshwar L},
  year   = {2026},
  note   = {Ouroboros project, Department of Artificial Intelligence and Data Science}
}
```

## License

MIT.
