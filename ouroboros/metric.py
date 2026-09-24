"""BAQD: Belief-Aligned Query Drift.

The metric asks one question at every retrieval hop:

    Is the query the system just wrote for itself closer to what it
    currently believes than the user's original neutral question was?

    BAQD(n) = cos(query_n, belief_{n-1}) - cos(question_0, belief_{n-1})

A value near zero means the system is still searching neutrally.
A rising value means the query is bending toward the system's own belief.
"""

import numpy as np


def cosine(a, b):
    """Cosine similarity between two dense vectors."""
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def baqd(query_vec, belief_vec, question_vec):
    """Belief-Aligned Query Drift for a single hop.

    query_vec     embedding of the query the system wrote for this hop
    belief_vec    embedding of what the system believed after the previous hop
    question_vec  embedding of the user's original neutral question
    """
    return cosine(query_vec, belief_vec) - cosine(question_vec, belief_vec)


def evidence_skew(stances):
    """Signed balance of a retrieved set, in the range [-1, 1].

    +1 means every retrieved passage supports the claim.
     0 means the retrieved set is evenly balanced.
    -1 means every retrieved passage opposes it.
    """
    if not stances:
        return 0.0
    return float(sum(stances)) / len(stances)


def balance_loss(stances):
    """How far a retrieved set has moved from perfect balance, in [0, 1]."""
    return abs(evidence_skew(stances))
