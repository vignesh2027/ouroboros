"""Convert SPIRAL-Bench v0 into flat files for the Hugging Face Hub."""

import json
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(HERE, "data", "spiral_bench_v0.json")
DST = os.path.join(HERE, "hf_dataset")


def main():
    os.makedirs(DST, exist_ok=True)
    with open(SRC) as f:
        bench = json.load(f)

    passages, queries = [], []
    for item in bench["questions"]:
        for i, p in enumerate(item["passages"]):
            passages.append({
                "question_id": item["id"],
                "question": item["question"],
                "question_type": item["type"],
                "passage_id": f"{item['id']}_p{i:02d}",
                "stance": p["stance"],
                "stance_label": "supporting" if p["stance"] > 0 else "opposing",
                "text": p["text"],
            })
        for arm, key in (("drift", "queries_drift"), ("neutral", "queries_neutral")):
            for hop, q in enumerate(item[key], start=1):
                queries.append({
                    "question_id": item["id"],
                    "question": item["question"],
                    "question_type": item["type"],
                    "arm": arm,
                    "hop": hop,
                    "query": q,
                })

    for name, rows in (("passages", passages), ("queries", queries)):
        path = os.path.join(DST, f"{name}.jsonl")
        with open(path, "w") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"{name}: {len(rows)} rows -> {path}")

    src_traces = os.path.join(HERE, "outputs", "traces.jsonl")
    if os.path.exists(src_traces):
        with open(src_traces) as a, open(os.path.join(DST, "traces.jsonl"), "w") as b:
            b.write(a.read())
        print("traces: copied")

    # integrity check: every contested question must be balanced
    bad = []
    for item in bench["questions"]:
        if item["type"] != "contested":
            continue
        s = sum(1 for p in item["passages"] if p["stance"] > 0)
        o = sum(1 for p in item["passages"] if p["stance"] < 0)
        if s != o:
            bad.append((item["id"], s, o))
    if bad:
        raise SystemExit(f"BALANCE CHECK FAILED: {bad}")
    print("balance check: every contested question is balanced")


if __name__ == "__main__":
    main()
