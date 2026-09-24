"""Charts for Ouroboros Review 1."""

import json
import os
import statistics

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "outputs")

INK, BLUE, RED, GREEN, GREY = "#111111", "#1B5E9E", "#B23A2B", "#14664A", "#8A8A8A"


def load_traces():
    with open(os.path.join(OUT, "traces.jsonl")) as f:
        return [json.loads(l) for l in f]


def mean(xs):
    return statistics.mean(xs) if xs else 0.0


def main():
    traces = load_traces()
    with open(os.path.join(OUT, "diagnostic.json")) as f:
        diag = json.load(f)

    contested = [r for r in traces if r["type"] == "contested"]
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
        "axes.edgecolor": "#CCCCCC", "axes.labelcolor": INK,
        "text.color": INK, "xtick.color": GREY, "ytick.color": GREY,
        "axes.spines.top": False, "axes.spines.right": False,
    })

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.6, 4.6))
    fig.subplots_adjust(wspace=0.30, left=0.09, right=0.97, top=0.84, bottom=0.22)

    # ---- Panel A: how far query wording can move the evidence ----
    labels = ["Oracle query\nfor support", "Our drifting\nquery, hop 3",
              "Neutral\nquery", "Oracle query\nfor opposition"]
    vals = [mean([d["oracle_support"] for d in diag]),
            mean([d["drift_hop3"] for d in diag]),
            mean([d["neutral"] for d in diag]),
            mean([d["oracle_oppose"] for d in diag])]
    colors = [RED, "#C9A227", GREY, BLUE]

    bars = ax1.barh(range(4), vals, color=colors, height=0.55)
    ax1.set_yticks(range(4))
    ax1.set_yticklabels(labels, fontsize=9)
    ax1.invert_yaxis()
    ax1.axvline(0, color="#CCCCCC", lw=1)
    ax1.set_xlim(-1.15, 1.15)
    ax1.set_xlabel("retrieved evidence skew   (-1 all opposing, 0 balanced, +1 all supporting)", fontsize=9, labelpad=8)
    ax1.set_title("Query wording alone controls the evidence",
                  fontsize=12, fontweight="bold", loc="left", pad=12)
    for i, (b, v) in enumerate(zip(bars, vals)):
        ax1.text(v + (0.06 if v >= 0 else -0.06), i, f"{v:+.2f}",
                 va="center", ha="left" if v >= 0 else "right",
                 fontsize=9, fontweight="bold", color=colors[i])
    fig.text(0.07, 0.035, "The full range a query can reach is 2.00 wide. "
                          "Our first drift probe captured 4.2% of it.",
             fontsize=9, color=GREY)

    # ---- Panel B: BAQD per hop, both arms ----
    hops = [1, 2, 3]
    for arm, colour, style in (("drift", RED, "-o"), ("neutral", BLUE, "--s")):
        ys = [mean([r["baqd"] for r in contested if r["arm"] == arm and r["hop"] == h])
              for h in hops]
        ax2.plot(hops, ys, style, color=colour, lw=2, ms=6,
                 label=f"{arm} arm")
    ax2.axhline(0, color="#CCCCCC", lw=1)
    ax2.set_xticks(hops)
    ax2.set_xlabel("retrieval hop", fontsize=9)
    ax2.set_ylabel("BAQD", fontsize=9)
    ax2.set_ylim(-0.12, 0.12)
    ax2.legend(frameon=False, fontsize=9, loc="upper left")
    ax2.set_title("BAQD stays flat under a lexical encoder",
                  fontsize=12, fontweight="bold", loc="left", pad=12)
    fig.text(0.56, 0.035, "Null result. BAQD needs a dense encoder before it can "
                          "register belief alignment.", fontsize=9, color=GREY)

    path = os.path.join(OUT, "review1_results.png")
    fig.savefig(path, dpi=170, facecolor="white")
    print("wrote", path)


if __name__ == "__main__":
    main()
