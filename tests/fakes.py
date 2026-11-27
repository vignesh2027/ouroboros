"""Test doubles shared by the offline test files."""

import copy
import json
import threading


class FakeLLM:
    """Stands in for ouroboros.llm.LLM. Returns canned JSON keyed by tag.

    canned maps a tag to a dict, or to a callable(system, user, schema) that
    returns a dict. A list value is consumed in order, repeating the last item.
    Every call is recorded in self.calls.
    """

    def __init__(self, canned=None, default=None):
        self.canned = dict(canned or {})
        self.default = default
        self.calls = []
        self._lock = threading.Lock()
        self._counts = {}
        self.usage = {"calls": 0, "cached_calls": 0, "input_tokens": 0,
                      "output_tokens": 0, "cost_usd": 0.0}

    def _lookup(self, tag, system, user, schema):
        with self._lock:
            n = self._counts.get(tag, 0)
            self._counts[tag] = n + 1
        if tag in self.canned:
            item = self.canned[tag]
        elif self.default is not None:
            item = self.default
        else:
            raise KeyError("FakeLLM has no canned answer for tag %r" % tag)
        if isinstance(item, list):
            item = item[min(n, len(item) - 1)]
        if callable(item):
            item = item(system, user, schema)
        return copy.deepcopy(item)

    def json(self, system, user, schema, max_tokens=2000, effort="low", tag=""):
        with self._lock:
            self.calls.append({"kind": "json", "tag": tag, "system": system,
                               "user": user, "schema": schema})
            self.usage["calls"] += 1
        return self._lookup(tag, system, user, schema)

    def text(self, system, user, max_tokens=2000, effort="low", tag=""):
        with self._lock:
            self.calls.append({"kind": "text", "tag": tag, "system": system,
                               "user": user, "schema": None})
            self.usage["calls"] += 1
        out = self._lookup(tag, system, user, None)
        return out if isinstance(out, str) else json.dumps(out)

    def tags(self):
        return [c["tag"] for c in self.calls]
