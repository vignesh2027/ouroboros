"""Ouroboros diagnostic: why did experiment 1 fail to reproduce the effect?

Experiment 1 found no collapse in evidence balance under a drifting query.
Three explanations are possible, and this script separates them.

  H1  The mechanism is not real.
  H2  The retriever cannot separate stance because supporting and opposing
      passages share the same vocabulary.
  H3  The encoder is lexical, so BAQD measures word overlap rather than
      belief alignment, and the queries are too short to overlap a long
      belief passage.

For H2 we hand the retriever an oracle query built only from the words that
appear in supporting passages and not in opposing ones, then the reverse.
If even an oracle query cannot shift the retrieved balance, the corpus
vocabulary is the binding constraint and no query wording could have worked.

Run:  python3 run_diagnostic.py
"""

import json
import os
import statistics

from ouroboros.metric import evidence_skew
from ouroboros.retrieval import Encoder, Retriever

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data", "spiral_bench_v0.json")
OUT = os.path.join(HERE, "outputs")
TOP_K = 4
STOP = set("""a an the and or of to in for on with is are was were be been by
that this those these it its as at from not no than then so such can could
will would may might shows show found find study studies research""".split())


def content_words(text):
    return {w for w in "".join(c.lower() if c.isalnum() else " " for c in text).split()
            if len(w) > 3 and w not in STOP}


def oracle_queries(passages):
    """Words unique to one side of the corpus, used as a best-case query."""
    sup, opp = set(), set()
    for p in passages:
        (sup if p["stance"] > 0 else opp).update(content_words(p["text"]))
    return " ".join(sorted(sup - opp)), " ".join(sorted(opp - sup))


def main():
    with open(DATA) as f:
        bench = json.load(f)

    corpus_texts = []
    for it in bench["questions"]:
        corpus_texts += [p["text"] for p in it["passages"]]
        corpus_texts += it["queries_drift"] + it["queries_neutral"] + [it["question"]]
    encoder = Encoder(corpus_texts)

    rows = []
    for item in bench["questions"]:
        if item["type"] != "contested":
            continue
        r = Retriever(item["passages"], encoder)
        sup_q, opp_q = oracle_queries(item["passages"])

        neutral = [h["stance"] for h in r.search(item["question"], k=TOP_K)]
        drift3 = [h["stance"] for h in r.search(item["queries_drift"][2], k=TOP_K)]
        o_sup = [h["stance"] for h in r.search(sup_q, k=TOP_K)]
        o_opp = [h["stance"] for h in r.search(opp_q, k=TOP_K)]

        rows.append({
            "id": item["id"],
            "neutral": evidence_skew(neutral),
            "drift_hop3": evidence_skew(drift3),
            "oracle_support": evidence_skew(o_sup),
            "oracle_oppose": evidence_skew(o_opp),
            "shared_vocab_ratio": shared_ratio(item["passages"]),
        })

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "diagnostic.json"), "w") as f:
        json.dump(rows, f, indent=2)

    report(rows)
    return rows


def shared_ratio(passages):
    sup, opp = set(), set()
    for p in passages:
        (sup if p["stance"] > 0 else opp).update(content_words(p["text"]))
    if not (sup | opp):
        return 0.0
    return round(len(sup & opp) / len(sup | opp), 3)


def m(rows, k):
    return statistics.mean(r[k] for r in rows)


def report(rows):
    line = "=" * 74
    print(line)
    print("OUROBOROS  Diagnostic: locating the cause of the null result")
    print(line)
    print("Retrieved-set skew, where +1 is all supporting and -1 is all opposing.")
    print()
    print(f"{'question':<18}{'neutral':>10}{'drift h3':>11}"
          f"{'oracle +':>11}{'oracle -':>11}{'shared vocab':>14}")
    print("-" * 74)
    for r in rows:
        print(f"{r['id']:<18}{r['neutral']:>10.2f}{r['drift_hop3']:>11.2f}"
              f"{r['oracle_support']:>11.2f}{r['oracle_oppose']:>11.2f}"
              f"{r['shared_vocab_ratio']:>14.3f}")
    print("-" * 74)
    print(f"{'mean':<18}{m(rows,'neutral'):>10.2f}{m(rows,'drift_hop3'):>11.2f}"
          f"{m(rows,'oracle_support'):>11.2f}{m(rows,'oracle_oppose'):>11.2f}"
          f"{m(rows,'shared_vocab_ratio'):>14.3f}")
    print()

    spread = m(rows, "oracle_support") - m(rows, "oracle_oppose")
    drift_shift = m(rows, "drift_hop3") - m(rows, "neutral")

    print("FINDINGS")
    print(f"  Oracle spread, best case a query could ever achieve : {spread:+.2f}")
    print(f"  Actual shift produced by our drifting query wording : {drift_shift:+.2f}")
    print(f"  Fraction of the achievable spread we captured       : "
          f"{(drift_shift / spread * 100 if spread else 0):.1f}%")
    print()
    if spread > 1.0:
        print("  The retriever CAN be steered. An oracle query moves the retrieved")
        print("  balance strongly, so the mechanism is available in principle.")
        print("  Our natural-language drift queries did not exploit it, which points")
        print("  at the query wording and the lexical encoder, not at the mechanism.")
    else:
        print("  The retriever CANNOT be steered on this corpus. Supporting and")
        print("  opposing passages share too much vocabulary for any query wording")
        print("  to separate them, so the corpus is the binding constraint.")
    print(line)


if __name__ == "__main__":
    main()
