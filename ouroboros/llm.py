"""Claude client with a disk cache, cost tracking and structured JSON calls.

Credentials are looked up in this order: ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN,
then the OAuth bearer token file ~/.config/anthropic/credit-key. A token is
never printed, logged, stored or returned.
"""

import hashlib
import json
import os
import tempfile
import threading

MODEL = "claude-haiku-5-5"
PRICE_IN_PER_M = 0.10
PRICE_OUT_PER_M = 0.50
CRED_FILE = os.path.expanduser("~/.config/anthropic/credit-key")
_TEXT_SCHEMA = {"__plain_text__": True}


class LLMError(Exception):
    """Any failure talking to the model."""


class LLMRefusal(LLMError):
    """The model declined to answer."""


class LLMOffline(LLMError):
    """Offline mode and the call is not in the cache."""


def credential_kind() -> str:
    """Return 'api_key', 'oauth_token' or 'none'. Never exposes the secret."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "api_key"
    if os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return "oauth_token"
    try:
        if os.path.isfile(CRED_FILE) and open(CRED_FILE).read().strip():
            return "oauth_token"
    except OSError:
        pass
    return "none"


def _build_client():
    import anthropic

    if os.environ.get("ANTHROPIC_API_KEY"):
        return anthropic.Anthropic()
    token = os.environ.get("ANTHROPIC_AUTH_TOKEN", "").strip()
    if not token:
        try:
            with open(CRED_FILE) as fh:
                token = fh.read().strip()
        except OSError:
            token = ""
    if not token:
        raise LLMError("no credentials found")
    return anthropic.Anthropic(
        auth_token=token,
        api_key=None,
        default_headers={"anthropic-beta": "oauth-2025-04-20"},
    )


def cache_key(system: str, user: str, schema: dict, effort: str) -> str:
    raw = MODEL + system + user + json.dumps(schema, sort_keys=True) + effort
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class LLM:
    def __init__(self, cache_dir: str = "outputs/.cache/llm", offline: bool = False):
        self.cache_dir = cache_dir
        self.offline = offline
        self._client = None
        self._lock = threading.Lock()
        # Shared by every fork: one set of per-key locks, so two threads asking for the
        # same uncached call make one request and the second reads the cache.
        self._shared = {"key_locks": {}, "guard": threading.Lock()}
        self.usage = {
            "calls": 0,
            "cached_calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0.0,
        }
        os.makedirs(cache_dir, exist_ok=True)

    def fork(self):
        """A new LLM with its own usage tally that shares the cache and the client.

        Used so concurrent lanes (compare mode) each report only their own calls.
        """
        other = LLM.__new__(LLM)
        other.cache_dir = self.cache_dir
        other.offline = self.offline
        other._lock = threading.Lock()
        other._shared = self._shared
        other._client = None
        other._parent = self
        other.usage = {"calls": 0, "cached_calls": 0, "input_tokens": 0,
                       "output_tokens": 0, "cost_usd": 0.0}
        return other

    def _key_lock(self, key: str):
        with self._shared["guard"]:
            return self._shared["key_locks"].setdefault(key, threading.Lock())

    # cache -----------------------------------------------------------------
    def _path(self, key: str) -> str:
        return os.path.join(self.cache_dir, key + ".json")

    def _read_cache(self, key: str):
        try:
            with open(self._path(key)) as fh:
                hit = json.load(fh)
        except (OSError, ValueError):
            return None
        # A cache file that is valid JSON but not our shape is treated as a miss.
        if isinstance(hit, dict) and isinstance(hit.get("text"), str):
            return hit
        return None

    def _write_cache(self, key: str, payload: dict) -> None:
        os.makedirs(self.cache_dir, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.cache_dir, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as fh:
                json.dump(payload, fh)
            os.replace(tmp, self._path(key))
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    # client ----------------------------------------------------------------
    def _get_client(self):
        parent = getattr(self, "_parent", None)
        if parent is not None:
            return parent._get_client()
        with self._lock:
            if self._client is None:
                self._client = _build_client()
            return self._client

    def _request(self, system, user, schema, max_tokens, effort):
        import anthropic

        client = self._get_client()
        kwargs = dict(
            model=MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        cfg = {"effort": effort}
        if schema is not None:
            cfg["format"] = {"type": "json_schema", "schema": schema}
        kwargs["output_config"] = cfg
        try:
            return client.messages.create(**kwargs)
        except anthropic.RateLimitError:
            raise LLMError("rate limited by the model API")
        except anthropic.APIStatusError as e:
            raise LLMError("model API error, status %s" % getattr(e, "status_code", "?"))
        except anthropic.APIConnectionError:
            raise LLMError("could not reach the model API")

    def _call(self, system, user, schema, max_tokens, effort, tag):
        key_schema = schema if schema is not None else _TEXT_SCHEMA
        key = cache_key(system, user, key_schema, effort)
        # Single flight per key. Without it, two lanes issuing the same prompt at once
        # both miss, both pay, and the later write replaces the earlier answer, so a
        # saved run no longer matches the cache it was made from.
        with self._key_lock(key):
            return self._call_locked(key, system, user, schema, max_tokens, effort, tag)

    def _call_locked(self, key, system, user, schema, max_tokens, effort, tag):
        hit = self._read_cache(key)
        if hit is not None:
            with self._lock:
                self.usage["calls"] += 1
                self.usage["cached_calls"] += 1
            return hit["text"]
        if self.offline:
            raise LLMOffline("offline and not cached (tag=%r)" % tag)

        resp = self._request(system, user, schema, max_tokens, effort)
        in_tok = out_tok = 0
        in_tok += resp.usage.input_tokens
        out_tok += resp.usage.output_tokens
        if resp.stop_reason == "max_tokens":
            resp = self._request(system, user, schema, max_tokens * 2, effort)
            in_tok += resp.usage.input_tokens
            out_tok += resp.usage.output_tokens
        cost = in_tok * PRICE_IN_PER_M / 1e6 + out_tok * PRICE_OUT_PER_M / 1e6
        with self._lock:
            self.usage["calls"] += 1
            self.usage["input_tokens"] += in_tok
            self.usage["output_tokens"] += out_tok
            self.usage["cost_usd"] += cost
        if resp.stop_reason == "refusal":
            raise LLMRefusal("the model declined this request (tag=%r)" % tag)
        if resp.stop_reason == "max_tokens":
            raise LLMError("response cut off at max_tokens (tag=%r)" % tag)
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        if schema is not None:
            try:
                json.loads(text)
            except ValueError:
                raise LLMError("model returned invalid JSON (tag=%r)" % tag)
        self._write_cache(
            key, {"text": text, "tag": tag, "input_tokens": in_tok, "output_tokens": out_tok}
        )
        return text

    # public ----------------------------------------------------------------
    def json(self, system: str, user: str, schema: dict, max_tokens: int = 2000,
             effort: str = "low", tag: str = "") -> dict:
        text = self._call(system, user, schema, max_tokens, effort, tag)
        try:
            return json.loads(text)
        except ValueError:
            raise LLMError("cached or returned JSON is invalid (tag=%r)" % tag)

    def text(self, system: str, user: str, max_tokens: int = 2000,
             effort: str = "low", tag: str = "") -> str:
        return self._call(system, user, None, max_tokens, effort, tag)
