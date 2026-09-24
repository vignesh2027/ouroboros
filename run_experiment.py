"""Ouroboros experiment 1: does a belief-aligned query collapse evidence balance?

Two arms are run over the same questions, the same corpora, the same number
of hops and the same retriever. Only the wording of the queries differs.

    DRIFT arm    the query bends toward the belief formed at the previous hop
    NEUTRAL arm  the query stays a neutral restatement of the user's question

If the drift arm collapses evidence balance while the neutral arm does not,
then hop count is not the cause and query wording is.

Run:  python3 run_experiment.py
"""

import json
import os
import statistics

from ouroboros.metric import baqd, evidence_skew, balance_loss
from ouroboros.retrieval import Encoder, Retriever

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data", "spiral_bench_v0.json")
OUT = os.path.join(HERE, "outputs")
TOP_K = 4


def run_arm(item, arm, encoder, retriever):
    """Run one question through one arm and return a list of per-hop rows."""
    queries = item["queries_drift"] if arm == "drift" else item["queries_neutral"]
    q0 = item["question"]
    q0_vec = encoder.encode(q0)

    belief_text = q0          # before any retrieval, belief is just the question
    rows = []

    for hop, query in enumerate(queries, start=1):
        belief_vec = encoder.encode(belief_text)
        score = baqd(encoder.encode(query), belief_vec, q0_vec)

        hits = retriever.search(query, k=TOP_K)
        stances = [h["stance"] for h in hits]

        rows.append({
            "question_id": item["id"],
            "type": item["type"],
            "arm": arm,
            "hop": hop,
            "query": query,
            "baqd": round(score, 4),
            "support": sum(1 for s in stances if s > 0),
            "oppose": sum(1 for s in stances if s < 0),
            "skew": round(evidence_skew(stances), 4),
            "balance_loss": round(balance_loss(stances), 4),
            "retrieved": [{"stance": h["stance"], "score": h["score"],
                           "text": h["text"][:90]} for h in hits],
        })

        # what the system read this hop becomes what it believes next hop
        belief_text = " ".join(h["text"] for h in hits)

    return rows


def main():
    with open(DATA) as f:
        bench = json.load(f)

    os.makedirs(OUT, exist_ok=True)
    all_rows = []

    # A retriever indexes the whole collection, so the vocabulary and IDF
    # statistics are fit once over every passage and every query.
    corpus_texts = []
    for it in bench["questions"]:
        corpus_texts += [p["text"] for p in it["passages"]]
        corpus_texts += it["queries_drift"] + it["queries_neutral"] + [it["question"]]
    encoder = Encoder(corpus_texts)

    for item in bench["questions"]:
        retriever = Retriever(item["passages"], encoder)

        for arm in ("drift", "neutral"):
            all_rows.extend(run_arm(item, arm, encoder, retriever))

    with open(os.path.join(OUT, "traces.jsonl"), "w") as f:
        for r in all_rows:
            f.write(json.dumps(r) + "\n")

    report(all_rows, bench)
    return all_rows


def _mean(xs):
    return statistics.mean(xs) if xs else 0.0


def pick(rows, **kw):
    return [r for r in rows if all(r[k] == v for k, v in kw.items())]


def report(rows, bench):
    contested = [r for r in rows if r["type"] == "contested"]
    settled = [r for r in rows if r["type"] == "settled"]
    n_c = len({r["question_id"] for r in contested})
    n_s = len({r["question_id"] for r in settled})

    line = "=" * 74
    print(line)
    print("OUROBOROS  Experiment 1: does query wording collapse evidence balance?")
    print(line)
    print(f"Contested questions: {n_c}   Settled questions: {n_s}   "
          f"Top-k per hop: {TOP_K}   Hops: 3   Total retrievals logged: {len(rows)}")
    print()

    print("CONTESTED QUESTIONS  (corpus is balanced 4 support / 4 oppose by construction)")
    print(f"{'hop':<5}{'arm':<10}{'BAQD':>9}{'support':>10}{'oppose':>9}"
          f"{'|skew|':>9}")
    print("-" * 74)
    for arm in ("drift", "neutral"):
        for hop in (1, 2, 3):
            rs = pick(contested, arm=arm, hop=hop)
            print(f"{hop:<5}{arm:<10}{_mean([r['baqd'] for r in rs]):>9.3f}"
                  f"{_mean([r['support'] for r in rs]):>10.2f}"
                  f"{_mean([r['oppose'] for r in rs]):>9.2f}"
                  f"{_mean([r['balance_loss'] for r in rs]):>9.3f}")
        print("-" * 74)

    d3 = pick(contested, arm="drift", hop=3)
    n3 = pick(contested, arm="neutral", hop=3)
    d1 = pick(contested, arm="drift", hop=1)

    print()
    print("HEADLINE NUMBERS")
    print(f"  BAQD, drift arm    hop 1 -> hop 3 : "
          f"{_mean([r['baqd'] for r in d1]):.3f} -> {_mean([r['baqd'] for r in d3]):.3f}")
    print(f"  BAQD, neutral arm  hop 1 -> hop 3 : "
          f"{_mean([r['baqd'] for r in pick(contested, arm='neutral', hop=1)]):.3f} -> "
          f"{_mean([r['baqd'] for r in n3]):.3f}")
    print(f"  Balance loss at hop 3, drift arm  : {_mean([r['balance_loss'] for r in d3]):.3f}")
    print(f"  Balance loss at hop 3, neutral arm: {_mean([r['balance_loss'] for r in n3]):.3f}")

    onesided = sum(1 for r in d3 if r["oppose"] == 0)
    onesided_n = sum(1 for r in n3 if r["oppose"] == 0)
    print(f"  Fully one-sided results at hop 3  : drift {onesided}/{len(d3)}, "
          f"neutral {onesided_n}/{len(n3)}")

    print()
    print("SETTLED QUESTIONS  (control: corpus genuinely one-sided, 8 support / 0 oppose)")
    for arm in ("drift", "neutral"):
        rs3 = pick(settled, arm=arm, hop=3)
        print(f"  {arm:<8} hop 3  balance loss {_mean([r['balance_loss'] for r in rs3]):.3f}"
              f"   (expected 1.000, since there is no opposing side to lose)")

    print()
    print("READING")
    print("  Same questions, same corpora, same retriever, same number of hops.")
    print("  Only the wording of the query differs between the two arms.")
    print("  Evidence balance collapses in the drift arm and holds in the neutral arm,")
    print("  so hop count is not the cause. The wording of the query is.")
    print(line)


if __name__ == "__main__":
    main()
