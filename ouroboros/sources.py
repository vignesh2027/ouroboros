"""Evidence fetchers for the Ouroboros platform.

Five sources, all queried over plain HTTPS with the standard library:
Wikipedia, OpenAlex, arXiv, PubMed and the open web (via the HTML endpoint of
DuckDuckGo). Each fetcher returns clean plain-text Document objects. A fetcher
that fails logs and returns an empty list; it never raises into the caller.

Only the search query text leaves the machine. No personal data is placed in a
URL or header. Results are cached on disk, and offline mode reads only the
cache.
"""

from __future__ import annotations

import hashlib
import html
import json
import logging
import os
import ipaddress
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, wait
from dataclasses import asdict, dataclass, field
from html.parser import HTMLParser

log = logging.getLogger("ouroboros.sources")


def _prefer_ipv4() -> None:
    """Try IPv4 addresses before IPv6 ones, process wide.

    Python's urllib connects to each address in order and waits for a timeout
    before moving on. On networks where IPv6 is advertised but broken, every
    fetch then stalls for the full timeout. Sorting IPv4 first keeps IPv6 as a
    fallback. Set OUROBOROS_KEEP_IPV6=1 to turn this off.
    """
    if os.environ.get("OUROBOROS_KEEP_IPV6") == "1":
        return
    if getattr(socket.getaddrinfo, "_ouroboros_ipv4_first", False):
        return
    original = socket.getaddrinfo

    def getaddrinfo(*args, **kwargs):
        infos = original(*args, **kwargs)
        return sorted(infos, key=lambda info: 0 if info[0] == socket.AF_INET else 1)

    getaddrinfo._ouroboros_ipv4_first = True
    socket.getaddrinfo = getaddrinfo


_prefer_ipv4()

USER_AGENT = "OuroborosResearch/0.2 (academic project)"
FETCH_TIMEOUT = 12.0        # seconds per fetcher
MAX_TEXT = 6000             # characters kept per document
MAX_PAGE_BYTES = 1_500_000  # never read more than this from one web page
ALL_SOURCES = ["wikipedia", "openalex", "arxiv", "pubmed", "web"]

_STOP = set(
    "a an the of in on at to for and or is are was were be been being do does did "
    "how what which who whom whose why when where that this these those it its as by "
    "with from about into than then so such can could should would will not no yes "
    "i you he she we they my your our their me us them there any some more most".split()
)


@dataclass
class Document:
    doc_id: str
    source: str
    title: str
    url: str
    domain: str
    text: str
    year: int | None = None
    meta: dict = field(default_factory=dict)


# ----------------------------------------------------------------- text utils

def doc_id_for(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]


def clean_text(text: str, cap: int = MAX_TEXT) -> str:
    """Unescape entities, collapse whitespace, cap at a word boundary."""
    text = html.unescape(text or "")
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > cap:
        cut = text[:cap]
        sp = cut.rfind(" ")
        text = cut[:sp] if sp > cap * 0.8 else cut
    return text


def keywords(query: str, limit: int = 8) -> list[str]:
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9\-']*", query)
    out, seen = [], set()
    for w in words:
        lw = w.lower()
        if lw in _STOP or lw in seen:
            continue
        seen.add(lw)
        out.append(w)
    return out[:limit]


def _host(url: str) -> str:
    host = urllib.parse.urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host


_SKIP_TAGS = {
    "script", "style", "nav", "header", "footer", "aside", "form", "noscript",
    "svg", "iframe", "button", "select", "template", "head", "dialog",
}
_VOID = {"br", "img", "hr", "meta", "link", "input", "source", "wbr", "area", "base", "col", "embed", "param", "track"}
_BLOCK = {
    "p", "div", "br", "li", "ul", "ol", "tr", "td", "th", "table", "section",
    "article", "main", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6", "pre", "dd", "dt", "figcaption",
}
_JUNK_TOKENS = {
    "nav", "navbar", "navigation", "menu", "sidebar", "footer", "cookie", "cookies",
    "consent", "banner", "popup", "modal", "advert", "ads", "advertisement", "promo",
    "newsletter", "breadcrumb", "breadcrumbs", "share", "social", "comments", "related",
}
_NO_JUNK_CHECK = {"html", "body", "main", "article"}
_JUNK_PHRASES = (
    "accept cookies", "cookie policy", "sign up for", "subscribe to", "all rights reserved",
    "privacy policy", "terms of use", "terms of service", "skip to", "javascript is disabled",
    "enable javascript", "log in", "sign in", "follow us",
)


class _TextExtractor(HTMLParser):
    """Visible text only: drops script, style, nav-like containers and chrome."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_tag: str | None = None
        self._skip_depth = 0
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag == "title":
            self._in_title = True
        if tag in _VOID:
            if tag == "br" and self._skip_tag is None:
                self.parts.append("\n")
            return
        if self._skip_tag is not None:
            if tag == self._skip_tag:
                self._skip_depth += 1
            return
        junk = tag in _SKIP_TAGS
        if not junk and tag not in _NO_JUNK_CHECK:
            a = dict(attrs)
            toks = (a.get("class") or "").lower().split() + [(a.get("id") or "").lower()]
            if any(t in _JUNK_TOKENS or t.startswith("cookie") for t in toks if t):
                junk = True
            elif (a.get("role") or "").lower() in ("navigation", "banner", "contentinfo", "complementary"):
                junk = True
            elif (a.get("aria-hidden") or "").lower() == "true":
                junk = True
        if junk and tag != "head":
            self._skip_tag, self._skip_depth = tag, 1
            return
        if tag == "head":
            self._skip_tag, self._skip_depth = tag, 1
            return
        if tag in _BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if self._skip_tag is not None:
            if tag == self._skip_tag:
                self._skip_depth -= 1
                if self._skip_depth <= 0:
                    self._skip_tag = None
            return
        if tag in _BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if self._in_title and not self.title:
            self.title = data.strip()
        if self._skip_tag is None:
            self.parts.append(data)


def html_to_text(markup: str, cap: int = MAX_TEXT) -> str:
    """Strip a page to readable prose: no tags, no nav, no cookie banners."""
    p = _TextExtractor()
    try:
        p.feed(markup)
        p.close()
    except Exception as e:  # malformed markup, keep whatever was parsed
        log.debug("html parse issue: %s", e)
    blocks, seen = [], set()
    for raw in "".join(p.parts).split("\n"):
        b = re.sub(r"\s+", " ", raw).strip()
        if not b:
            continue
        n = len(b.split())
        low = b.lower()
        if n < 8 and not (n >= 5 and b[-1] in ".!?"):
            continue
        if n < 25 and any(ph in low for ph in _JUNK_PHRASES):
            continue
        # a long run with no sentence punctuation is a merged list of links or headlines
        if n >= 20 and b[-1] not in ".!?\"')" and not re.search(r"[.!?]\s", b):
            continue
        if low in seen:
            continue
        seen.add(low)
        blocks.append(b)
    return clean_text(" ".join(blocks), cap)


def strip_tags(fragment: str) -> str:
    """Inline markup to text, used for search snippets and API fields."""
    p = _TextExtractor()
    try:
        p.feed(fragment or "")
        p.close()
    except Exception:
        pass
    return clean_text("".join(p.parts))


def unwrap_ddg(href: str) -> str | None:
    """Turn a DuckDuckGo redirect link into the real target URL."""
    if not href:
        return None
    if href.startswith("//"):
        href = "https:" + href
    parsed = urllib.parse.urlparse(href)
    if parsed.netloc.endswith("duckduckgo.com"):
        if parsed.path.startswith("/l/"):
            target = urllib.parse.parse_qs(parsed.query).get("uddg")
            if target:
                href = urllib.parse.unquote(target[0])
                parsed = urllib.parse.urlparse(href)
            else:
                return None
        else:
            return None  # ads (y.js) and internal links
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None
    return href


# ------------------------------------------------------------------ HTTP

def is_public_url(url: str) -> bool:
    """True only when every address the host resolves to is a public one.

    Search results are untrusted, so a link to localhost, a private network or a
    cloud metadata address must never be fetched.
    """
    try:
        parsed = urllib.parse.urlparse(url)
        host = parsed.hostname
        if parsed.scheme not in ("http", "https") or not host:
            return False
        infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80),
                                   proto=socket.IPPROTO_TCP)
        if not infos:
            return False
        for info in infos:
            ip = ipaddress.ip_address(info[4][0].split("%")[0])
            if not ip.is_global:
                return False
        return True
    except (ValueError, OSError):
        return False


class _PublicOnlyRedirect(urllib.request.HTTPRedirectHandler):
    """Re-check every redirect target, so a public page cannot bounce us inward."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not is_public_url(newurl):
            raise urllib.error.URLError("redirect to a non-public address refused")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _http(url: str, data: bytes | None = None, timeout: float = FETCH_TIMEOUT,
          headers: dict | None = None, max_bytes: int = 4_000_000,
          public_only: bool = False) -> tuple[bytes, str]:
    if public_only and not is_public_url(url):
        raise urllib.error.URLError("refusing to fetch a non-public address")
    opener = (urllib.request.build_opener(_PublicOnlyRedirect) if public_only
              else urllib.request.build_opener())
    hdrs = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=data, headers=hdrs)
    for attempt in (0, 1):
        try:
            with opener.open(req, timeout=timeout) as r:
                ctype = r.headers.get("Content-Type", "")
                body = r.read(max_bytes)
            return body, ctype
        except urllib.error.HTTPError as e:
            # one polite retry on rate limiting, then give up
            if e.code == 429 and attempt == 0:
                try:
                    wait_s = min(3.0, float(e.headers.get("Retry-After", 1)))
                except (TypeError, ValueError):
                    wait_s = 1.0
                time.sleep(wait_s)
                continue
            raise
    raise RuntimeError("unreachable")


def _decode(body: bytes, ctype: str) -> str:
    m = re.search(r"charset=([\w\-]+)", ctype, re.I)
    enc = m.group(1) if m else None
    if not enc:
        m2 = re.search(rb"<meta[^>]+charset=[\"']?([\w\-]+)", body[:4096], re.I)
        enc = m2.group(1).decode("ascii", "ignore") if m2 else "utf-8"
    try:
        return body.decode(enc, errors="replace")
    except LookupError:
        return body.decode("utf-8", errors="replace")


def _get_json(url: str, timeout: float = FETCH_TIMEOUT) -> dict:
    body, _ = _http(url, timeout=timeout, headers={"Accept": "application/json"})
    return json.loads(body.decode("utf-8", errors="replace"))


# --------------------------------------------------------------- fetchers

def fetch_wikipedia(query: str, n: int) -> list[Document]:
    q = urllib.parse.urlencode({
        "action": "query", "list": "search", "srsearch": query,
        "format": "json", "srlimit": n, "srprop": "",
    })
    hits = _get_json("https://en.wikipedia.org/w/api.php?" + q).get("query", {}).get("search", [])
    titles = [h["title"] for h in hits[:n]]
    if not titles:
        return []
    def one(t: str) -> tuple[str, dict | None]:
        # Full-page extracts are limited to one title per request, so fetch in parallel.
        q2 = urllib.parse.urlencode({
            "action": "query", "prop": "extracts", "explaintext": 1,  # no exintro: any value means intro only
            "titles": t, "format": "json", "redirects": 1,
        })
        pages = _get_json("https://en.wikipedia.org/w/api.php?" + q2).get("query", {}).get("pages", {})
        return t, next(iter(pages.values()), None)

    with ThreadPoolExecutor(max_workers=len(titles)) as ex:
        fetched = list(ex.map(lambda t: _safe(one, t), titles))
    docs = []
    for item in fetched:
        if not item:
            continue
        t, p = item
        if not p or not p.get("extract"):
            continue
        # drop "== Heading ==" markers left by explaintext
        body = re.sub(r"^=+\s.*?\s=+\s*$", " ", p["extract"], flags=re.M)
        url = "https://en.wikipedia.org/wiki/" + urllib.parse.quote(t.replace(" ", "_"))
        text = clean_text(body)
        if len(text) < 150:  # stubs and disambiguation pages carry no evidence
            continue
        docs.append(Document(doc_id_for(url), "wikipedia", t, url, "en.wikipedia.org", text, None,
                             {"pageid": p.get("pageid")}))
    return docs


def _safe(fn, *args):
    try:
        return fn(*args)
    except Exception as e:
        log.debug("sub-request failed: %s", e)
        return None


def _openalex_abstract(inv: dict | None) -> str:
    if not inv:
        return ""
    pos = []
    for word, idxs in inv.items():
        for i in idxs:
            pos.append((i, word))
    pos.sort()
    return " ".join(w for _, w in pos)


def fetch_openalex(query: str, n: int) -> list[Document]:
    q = urllib.parse.urlencode({
        "search": query, "per-page": n, "filter": "has_abstract:true",
        "select": "id,doi,title,display_name,publication_year,abstract_inverted_index,cited_by_count,authorships,primary_location",
    })
    results = _get_json("https://api.openalex.org/works?" + q).get("results", [])
    docs = []
    for w in results[:n]:
        title = clean_text(w.get("title") or w.get("display_name") or "", 300)
        abstract = _openalex_abstract(w.get("abstract_inverted_index"))
        if not title or not abstract:
            continue
        doi = w.get("doi") or ""
        url = doi if doi.startswith("http") else (w.get("id") or "")
        if not url:
            continue
        m = re.search(r"doi\.org/(10\.\d+)/", doi)
        domain = "doi.org/" + m.group(1) if m else "openalex.org"
        authors = [a.get("author", {}).get("display_name", "") for a in (w.get("authorships") or [])[:5]]
        venue = ((w.get("primary_location") or {}).get("source") or {}).get("display_name")
        docs.append(Document(
            doc_id_for(url), "openalex", title, url, domain,
            clean_text(title + ". " + abstract), w.get("publication_year"),
            {"authors": [a for a in authors if a], "venue": venue, "cited_by_count": w.get("cited_by_count")},
        ))
    return docs


_ATOM = "{http://www.w3.org/2005/Atom}"


def parse_arxiv(xml_text: str) -> list[Document]:
    root = ET.fromstring(xml_text)
    docs = []
    for e in root.findall(_ATOM + "entry"):
        title = clean_text(e.findtext(_ATOM + "title") or "", 300)
        summary = clean_text(e.findtext(_ATOM + "summary") or "")
        url = (e.findtext(_ATOM + "id") or "").strip()
        if not title or not summary or not url:
            continue
        published = e.findtext(_ATOM + "published") or ""
        year = int(published[:4]) if published[:4].isdigit() else None
        authors = [clean_text(a.findtext(_ATOM + "name") or "", 80) for a in e.findall(_ATOM + "author")][:5]
        docs.append(Document(doc_id_for(url), "arxiv", title, url, "arxiv.org",
                             clean_text(title + ". " + summary), year, {"authors": authors}))
    return docs


def fetch_arxiv(query: str, n: int) -> list[Document]:
    kws = keywords(query, 6)
    if not kws:
        return []
    for k in (len(kws), 3):
        terms = " AND ".join("all:" + w for w in kws[:k])
        q = urllib.parse.urlencode({"search_query": terms, "max_results": n})
        body, _ = _http("https://export.arxiv.org/api/query?" + q)
        docs = parse_arxiv(body.decode("utf-8", errors="replace"))
        if docs or k <= 3:
            return docs[:n]
    return []


def parse_pubmed(xml_text: str) -> list[Document]:
    root = ET.fromstring(xml_text)
    docs = []
    for art in root.findall(".//PubmedArticle"):
        pmid = (art.findtext(".//MedlineCitation/PMID") or "").strip()
        title = clean_text("".join(art.find(".//ArticleTitle").itertext()) if art.find(".//ArticleTitle") is not None else "", 300)
        parts = []
        for ab in art.findall(".//Abstract/AbstractText"):
            t = "".join(ab.itertext()).strip()
            label = ab.get("Label")
            parts.append(f"{label.capitalize()}: {t}" if label and t else t)
        abstract = clean_text(" ".join(p for p in parts if p))
        if not pmid or not title or not abstract:
            continue
        year = None
        y = art.findtext(".//Journal/JournalIssue/PubDate/Year")
        if not y:
            md = art.findtext(".//Journal/JournalIssue/PubDate/MedlineDate") or ""
            m = re.search(r"(19|20)\d\d", md)
            y = m.group(0) if m else None
        if y and y.isdigit():
            year = int(y)
        authors = []
        for a in art.findall(".//AuthorList/Author")[:5]:
            nm = ((a.findtext("ForeName") or "") + " " + (a.findtext("LastName") or "")).strip()
            if nm:
                authors.append(nm)
        url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        docs.append(Document(doc_id_for(url), "pubmed", title, url, "pubmed.ncbi.nlm.nih.gov",
                             clean_text(title + ". " + abstract), year,
                             {"pmid": pmid, "authors": authors, "venue": art.findtext(".//Journal/Title")}))
    return docs


def fetch_pubmed(query: str, n: int) -> list[Document]:
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
    kws = keywords(query, 8)
    for term in (" ".join(kws), " ".join(kws[:3])):
        if not term:
            return []
        q = urllib.parse.urlencode({"db": "pubmed", "term": term, "retmode": "json", "retmax": n, "sort": "relevance"})
        ids = _get_json(base + "esearch.fcgi?" + q).get("esearchresult", {}).get("idlist", [])
        if ids:
            break
    else:
        return []
    q2 = urllib.parse.urlencode({"db": "pubmed", "id": ",".join(ids), "rettype": "abstract", "retmode": "xml"})
    body, _ = _http(base + "efetch.fcgi?" + q2)
    docs = parse_pubmed(body.decode("utf-8", errors="replace"))
    order = {i: k for k, i in enumerate(ids)}
    docs.sort(key=lambda d: order.get(d.meta.get("pmid"), 99))
    return docs[:n]


class _DDGParser(HTMLParser):
    """Pulls (href, title, snippet) triples out of html.duckduckgo.com results."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.results: list[dict] = []
        self._cur: dict | None = None
        self._mode: str | None = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = (a.get("class") or "").split()
        if tag == "a" and "result__a" in cls:
            self._cur = {"href": a.get("href", ""), "title": "", "snippet": ""}
            self.results.append(self._cur)
            self._mode = "title"
        elif tag in ("a", "div", "td") and "result__snippet" in cls and self.results:
            self._cur = self.results[-1]
            self._mode = "snippet"

    def handle_endtag(self, tag):
        if tag == "a" and self._mode == "title":
            self._mode = None
        elif tag in ("a", "div", "td") and self._mode == "snippet":
            self._mode = None

    def handle_data(self, data):
        if self._cur is not None and self._mode:
            self._cur[self._mode] += data


def parse_ddg(markup: str) -> list[dict]:
    p = _DDGParser()
    p.feed(markup)
    p.close()
    out = []
    for r in p.results:
        url = unwrap_ddg(r["href"])
        if not url:
            continue
        out.append({"url": url, "title": clean_text(r["title"], 300), "snippet": clean_text(r["snippet"], 600)})
    return out


def _fetch_page_text(url: str, timeout: float) -> str:
    try:
        body, ctype = _http(url, timeout=timeout, max_bytes=MAX_PAGE_BYTES,
                            headers={"Accept": "text/html,application/xhtml+xml"},
                            public_only=True)
    except Exception as e:
        log.debug("page fetch failed %s: %s", url, e)
        return ""
    if ctype and "html" not in ctype.lower() and "text" not in ctype.lower():
        return ""
    return html_to_text(_decode(body, ctype))


def fetch_web(query: str, n: int) -> list[Document]:
    start = time.monotonic()
    data = urllib.parse.urlencode({"q": query}).encode()
    body, ctype = _http("https://html.duckduckgo.com/html/", data=data, timeout=8,
                        headers={"Content-Type": "application/x-www-form-urlencoded"})
    results = parse_ddg(_decode(body, ctype))
    # one result per host so a single site cannot fill the slate
    picked, hosts = [], set()
    for r in results:
        h = _host(r["url"])
        if h in hosts:
            continue
        hosts.add(h)
        picked.append(r)
        if len(picked) >= n:
            break
    if not picked:
        return []
    remaining = max(2.0, FETCH_TIMEOUT - 1.5 - (time.monotonic() - start))
    with ThreadPoolExecutor(max_workers=len(picked)) as ex:
        futs = [ex.submit(_fetch_page_text, r["url"], remaining) for r in picked]
        wait(futs, timeout=remaining + 0.5)
        texts = [f.result() if f.done() and not f.exception() else "" for f in futs]
    docs = []
    for r, page in zip(picked, texts):
        text = page if len(page) >= 200 else clean_text((r["title"] + ". " + r["snippet"]).strip(". "))
        if len(text) < 20:
            continue
        docs.append(Document(doc_id_for(r["url"]), "web", r["title"] or _host(r["url"]), r["url"],
                             _host(r["url"]), text, None, {"snippet": r["snippet"], "full_page": len(page) >= 200}))
    return docs


FETCHERS = {
    "wikipedia": fetch_wikipedia,
    "openalex": fetch_openalex,
    "arxiv": fetch_arxiv,
    "pubmed": fetch_pubmed,
    "web": fetch_web,
}


# ------------------------------------------------------------------ cache

def _norm_query(q: str) -> str:
    return re.sub(r"\s+", " ", q.strip().lower())


def _cache_path(cache_dir: str, source: str, query: str, per_source: int) -> str:
    key = hashlib.sha1(f"{source}|{_norm_query(query)}|{per_source}".encode()).hexdigest()
    return os.path.join(cache_dir, source, key + ".json")


def _cache_read(path: str) -> list[Document] | None:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return [Document(**d) for d in json.load(f)]
    except (OSError, ValueError, TypeError):
        return None


def _cache_write(path: str, docs: list[Document]) -> None:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = f"{path}.{os.getpid()}.{id(docs)}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump([asdict(d) for d in docs], f)
        os.replace(tmp, path)
    except OSError as e:
        log.warning("cache write failed: %s", e)


# ------------------------------------------------------------------ API

def default_sources(question: str = "") -> list[str]:
    return list(ALL_SOURCES)


def _run_one(source: str, query: str, per_source: int, cache_dir: str, offline: bool) -> list[Document]:
    path = _cache_path(cache_dir, source, query, per_source)
    hit = _cache_read(path)
    if hit is not None:
        return hit
    if offline:
        return []
    try:
        docs = FETCHERS[source](query, per_source)
    except Exception as e:
        log.warning("source %s failed: %s: %s", source, type(e).__name__, e)
        return []
    docs = [d for d in docs if d.text][:per_source]
    if docs:  # never cache emptiness: it may be a block page or a timeout
        _cache_write(path, docs)
    return docs


def search_all(query: str, per_source: int = 4, sources: list[str] | None = None,
               cache_dir: str = "outputs/.cache/sources", offline: bool = False) -> list[Document]:
    """Query every requested source in parallel. Never raises. Order is by source."""
    names = [s for s in (sources or default_sources(query)) if s in FETCHERS]
    if not names or not query.strip():
        return []
    ex = ThreadPoolExecutor(max_workers=len(names))
    futs = {s: ex.submit(_run_one, s, query, per_source, cache_dir, offline) for s in names}
    wait(list(futs.values()), timeout=FETCH_TIMEOUT)
    ex.shutdown(wait=False, cancel_futures=True)
    out, seen = [], set()
    for s in names:
        f = futs[s]
        if not f.done():
            log.warning("source %s timed out after %.1fs", s, FETCH_TIMEOUT)
            continue
        try:
            docs = f.result()
        except Exception as e:
            log.warning("source %s failed: %s", s, e)
            continue
        for d in docs:
            if d.doc_id not in seen:
                seen.add(d.doc_id)
                out.append(d)
    return out
