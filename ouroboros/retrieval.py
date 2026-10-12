"""Retriever and text encoder for the Ouroboros prototype.

The encoder is TF-IDF over the corpus vocabulary. That is a lexical
embedding, not a neural one. It is used here because it runs instantly on
a laptop CPU with no model download, and because the mechanism under test
is lexical: a retriever ranks documents by how closely they match the
wording of the query it receives. Swapping in a neural sentence encoder
such as bge-small is planned and does not change the interface below.
"""

from sklearn.feature_extraction.text import TfidfVectorizer

from .metric import cosine


class Encoder:
    """Fits a TF-IDF vocabulary once, then encodes any text into a vector."""

    def __init__(self, fit_texts):
        self.vec = TfidfVectorizer(
            lowercase=True,
            stop_words="english",
            ngram_range=(1, 1),
            sublinear_tf=True,
        )
        self.vec.fit(fit_texts)

    def encode(self, text):
        return self.vec.transform([text]).toarray()[0]

    def encode_many(self, texts):
        return self.vec.transform(texts).toarray()


class Retriever:
    """Ranks passages by cosine similarity to the query wording."""

    def __init__(self, passages, encoder):
        self.passages = passages
        self.encoder = encoder
        self.matrix = encoder.encode_many([p["text"] for p in passages])

    def search(self, query, k=4):
        # A negative k would slice from the end of the ranking and quietly
        # return the worst matches, so guard it rather than trusting the slice.
        if k <= 0:
            return []
        qv = self.encoder.encode(query)
        scored = [
            (cosine(qv, self.matrix[i]), i) for i in range(len(self.passages))
        ]
        scored.sort(key=lambda t: (-t[0], t[1]))
        out = []
        for score, idx in scored[:k]:
            p = dict(self.passages[idx])
            p["score"] = round(score, 4)
            out.append(p)
        return out
