"""Small pure helpers used by the agent and the audit."""

from collections import Counter


def _get(p, name, default=None):
    if isinstance(p, dict):
        return p.get(name, default)
    return getattr(p, name, default)


def source_diversity(passages) -> dict:
    """Distinct domains and sources in a set of passages (dicts or objects).

    top_domain_share is the fraction of passages from the most common domain,
    0.0 for an empty set.
    """
    passages = list(passages or [])
    domains = Counter(_get(p, "domain") for p in passages if _get(p, "domain"))
    sources = {_get(p, "source") for p in passages if _get(p, "source")}
    top = max(domains.values()) / len(passages) if domains else 0.0
    return {"domains": len(domains), "sources": len(sources), "top_domain_share": top}


def calibration_gap(conf, score):
    """Stated confidence minus evidence support score. None if either is missing.

    Positive means the model sounds more sure than the evidence justifies.
    """
    if conf is None or score is None:
        return None
    return float(conf) - float(score)


def run_summary(run: dict) -> dict:
    """Headline numbers for one saved run record."""
    hops = run.get("hops") or []
    baqds = [h.get("baqd") for h in hops if h.get("hop", 0) >= 2 and h.get("baqd") is not None]
    if not baqds:
        baqds = [h["baqd"] for h in hops[1:] if h.get("baqd") is not None]
    domains = set()
    for h in hops:
        for p in h.get("passages") or []:
            if p.get("domain"):
                domains.add(p["domain"])
    audit = run.get("audit") or {}
    scores = audit.get("scores") or {}
    final_skew = hops[-1].get("skew") if hops else None
    return {
        "mean_baqd": sum(baqds) / len(baqds) if baqds else None,
        "max_baqd": max(baqds) if baqds else None,
        "final_skew": final_skew,
        "cqi_count": len(run.get("cqi_events") or []),
        "domains_total": len(domains),
        "evidence_support_score": scores.get("evidence_support_score"),
    }
