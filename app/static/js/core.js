/* Ouroboros core. Plain JS, no framework, no build step. Everything lives on window.O.
   Load order: core.js, then home.js, thread.js, pages.js (all deferred). The marketing landing page is a separate document (landing.html, served at /) with its own landing.js; this app lives at /app. Page scripts call O.route() while loading.
   Add ?mock=1 to the page address to replay hand-made fixtures with no server.

   =============================== O.* API ===============================

   DOM and values
     O.$(sel, root?)                      first match or null
     O.$$(sel, root?)                     array of matches
     O.h(tag, props?, ...children)        make an element. props: class, text, style (string), on<event> handlers, any attribute
                                          (true sets a bare attribute, false/null skips it). Children: nodes, strings, arrays, null.
     O.svg(tag, attrs?, text?)            make an SVG element
     O.clear(el)                          remove all children, returns el
     O.esc(str)                           escape for innerHTML (prefer O.h; this is for the rare string template)
     O.isNum(v)  O.fmt(v, digits=2)  O.pct(v, digits=0)  O.plural(n, 'word')  O.safeUrl(url)  O.sleep(ms)  O.trunc(str, n)
     O.query(name)                        value of a ?name= query parameter or null
     O.MOCK (bool)  O.REDUCED (bool, prefers-reduced-motion)
     O.EXAMPLES                           the six cached example questions, exact strings
     O.DEPTH                              [{id:'quick',label:'Quick',hops:2},{id:'standard',label:'Standard',hops:4},{id:'deep',label:'Deep',hops:6}]
     O.MODE_LABEL                         {guarded:'Balanced search', standard:'Standard search'}
     O.SOURCE_LABELS                      {wikipedia:'Wikipedia', openalex:'OpenAlex', arxiv:'arXiv', pubmed:'PubMed', web:'Web'}
     O.AI_MODELS                          ['ChatGPT','Claude','Gemini','Other']

   Server calls (mock aware)
     O.api(path, opts?)                   fetch JSON, throws Error(message in plain words)
     O.postJSON(path, body)               POST JSON, returns parsed JSON
     O.sse(url, onEvent)                  open an event stream. returns {done: Promise, stop(): void}. onEvent gets each parsed event.
                                          Rejects with AbortError after stop(). Works for /api/research/stream and /api/compare/stream.
     O.recordToEvents(run)                turn a saved run record into the same event list the live stream sends (replay)
     O.runSummary(run)                    {mean_baqd,max_baqd,final_skew,cqi_count,domains_total,evidence_support_score}
     O.friendlyError(err)                 plain-words message for any thrown error

   Router (hash based, under /app: #/ask  #/thread  #/r/<run_id>  #/audit  #/compare  #/benchmark  #/how)
     O.route(name, def)                   register a page. def = {
                                            title: 'Check an AI answer',        // sets document.title
                                            init(el):        called once, el is the page's own <section class="view">
                                            show(el, params): every time the page is entered, params = {id?, segs:[], query:URLSearchParams}
                                            hide(el):        optional, called when leaving (streams may keep running)
                                          }
                                          Names in use: ask, thread, r, audit, compare, benchmark, how. An empty hash or an unknown route goes to #/ask.
     O.go(path)                           navigate, e.g. O.go('/audit'). Re-enters the page even when the hash is unchanged.
     O.href(path)                         '#/audit' style link target for <a href>
     O.current()                          {name, params}
     O.startThread({question, guarded, hops})
                                          stash a request and go to #/thread. The thread page calls O.takePending() in show().
     O.takePending()                      returns the stashed request once, then null
     O.openRun(run_id)                    go to #/r/<run_id>
     O.setTitle(text)

   Shared UI builders (all return elements unless noted)
     O.logo(height=28, {word, rule})      the Ouroboros ribbon mark (PNG in a span.logo), optional wordmark and ornament
     O.icon(name, size=20)                line icon. names: plus home shield columns chart flow menu close arrow-up arrow-right search
                                          check alert info external sun moon monitor book globe layers scale pen doc refresh copy stop
                                          chat link chevron-down bolt
     O.spinner()
     O.gradePill(grade)                   pill coloured by grade ("Well supported", "Partly supported", "Weakly supported", "Contradicted by evidence")
     O.verdictPill(verdict)               verdict: supported | contradicted | mixed | not_verified
     O.modeBadge(mode)                    small chip: Balanced / Standard
     O.scoreRing(value, {size=108, grade})  animated ring with the number inside
     O.evidenceCard(report, {stated?, title?})
                                          Evidence card: score ring, grade, "x of y claims backed", websites, multi-source share, contradicted,
                                          not verified, confidence gap in words, honesty note. report = audit report {claims, scores, grade}.
                                          stated = the answer's own confidence 0..100 if known.
     O.claimCards(reportOrClaims, {cites?})  list of claim cards with verdict pill, note, and evidence rows with numbered cite chips
     O.domainBadge(domain)                round letter badge
     O.sourceCard(doc, n, {cited?})       numbered source card (link to the source). doc = {pid,title,url,domain,source,year,text}
     O.sourceRow(cites)                   horizontal row of source cards from a Citations registry (cited ones first)
     O.balanceBar(support, neutral, contradict)   stacked bar
     O.baqdBar(baqd, threshold=0.05)      centred bar with threshold marker
     O.steps(labels)                      live status steps. returns {el, activate(i), done(i), finish(), fail(i), reset()}.
                                          activate(i) marks steps before i as done and i as active.
     O.tabs({tabs:[{id,label,count?}], panels:{id:node}, active?, onChange?})
                                          returns an element with .select(id), .setCount(id, n), .active (current id)
     O.composer({placeholder, large?, options=true, value?, onSubmit(question, {guarded, depth, hops}), onStop?})
                                          chat-style box: textarea, "Balanced search" switch, Depth select, round Ask button.
                                          returns {el, input, getValue(), setValue(v), getOptions(), setOptions(o), setBusy(bool), focus()}
                                          Enter submits, Shift+Enter is a new line. While busy the Ask button becomes Stop and calls onStop.
     O.answerBlock(text, cites)           div.answer with paragraphs and numbered citation chips
     O.lineChart(host, {series, xmin, xmax, yTitle, xTitle, threshold, thresholdLabel, fixedY, nullLabel, aria})
                                          responsive SVG line chart (see source for series shape: [{name,color,dash?,points:[{x,y,mark?}]}])
     O.watchResize(host, redraw)          call redraw when host width changes
     O.toast(message)

   Citations (maps passage ids to numbers 1..n, like Perplexity)
     var c = new O.Citations()
     c.add(passageOrEvidence)  c.addAll(list)  c.has(pid)  c.get(pid)
     c.setAnswer(text)                    number the passages cited in the answer first (in order of first appearance), then the rest
     c.number(pid)                        number or null
     c.sources()                          [{n, doc, cited}] sorted by n
     c.chip(pid)                          numbered chip button (popover on hover/focus, click jumps to the source)
     c.render(text)                       array of nodes: plain text plus chips for every [pid] in the text
     c.jump(pid)                          scroll to and flash the element carrying data-pid="<pid>" (source cards and passages carry it)
     c.onJump = function(pid){ ... }      optional hook, return true to replace the default jump
     O.citationsFromRun(run)              Citations built from every hop's passages, with setAnswer(run.synthesis.answer) applied
     O.popover.attach(el, contentFn)      hover/focus popover. contentFn() returns a node. O.popover.show(anchor, node)  O.popover.hide()

   Sidebar
     O.refreshRuns()                      reload the Recent research list (call after a run finishes)
     O.theme.get() returns 'system'|'light'|'dark'    O.theme.set(value)
     O.health()                           re-read /api/health and update the quiet connection dot

   Data shapes (from the server): see app/static/DESIGN.md "Event stream".
   ====================================================================== */
(function () {
  'use strict';

  var O = window.O = {};
  var NS = 'http://www.w3.org/2000/svg';

  /* ---------- basics ---------- */
  O.$ = function (s, r) { return (r || document).querySelector(s); };
  O.$$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  O.MOCK = new URLSearchParams(location.search).has('mock');
  O.REDUCED = !!(window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches);
  O.query = function (n) { return new URLSearchParams(location.search).get(n); };

  O.EXAMPLES = [
    'Is intermittent fasting effective for weight loss?',
    'Which is the fastest production motorcycle sold in India?',
    'Does remote work increase productivity?',
    'Is nuclear power a good way to cut carbon emissions?',
    'Should adults take vitamin D supplements daily?',
    'Does raising the minimum wage reduce employment?'
  ];
  O.DEPTH = [
    { id: 'quick', label: 'Quick', hops: 2 },
    { id: 'standard', label: 'Standard', hops: 4 },
    { id: 'deep', label: 'Deep', hops: 6 }
  ];
  O.MODE_LABEL = { guarded: 'Balanced search', standard: 'Standard search' };
  O.SOURCE_LABELS = { wikipedia: 'Wikipedia', openalex: 'OpenAlex', arxiv: 'arXiv', pubmed: 'PubMed', web: 'Web' };
  O.AI_MODELS = ['ChatGPT', 'Claude', 'Gemini', 'Other'];

  function append(el, kid) {
    if (kid == null || kid === false) return;
    if (Array.isArray(kid)) { kid.forEach(function (k) { append(el, k); }); return; }
    el.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  }
  O.h = function (tag, props) {
    var el = document.createElement(tag), p = props || {};
    Object.keys(p).forEach(function (k) {
      var v = p[k];
      if (v == null || v === false) return;
      if (k === 'class') el.className = v;
      else if (k === 'text') el.textContent = v;
      else if (k.indexOf('on') === 0 && typeof v === 'function') el.addEventListener(k.slice(2), v);
      else el.setAttribute(k, v === true ? '' : v);
    });
    for (var i = 2; i < arguments.length; i++) append(el, arguments[i]);
    return el;
  };
  O.svg = function (tag, attrs, text) {
    var el = document.createElementNS(NS, tag);
    Object.keys(attrs || {}).forEach(function (k) { el.setAttribute(k, attrs[k]); });
    if (text != null) el.textContent = text;
    return el;
  };
  var h = O.h;
  O.clear = function (el) { el.replaceChildren(); return el; };
  O.esc = function (s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); };
  O.isNum = function (v) { return typeof v === 'number' && isFinite(v); };
  O.fmt = function (v, d) { return O.isNum(v) ? v.toFixed(d == null ? 2 : d) : 'n/a'; };
  O.pct = function (v, d) { return O.isNum(v) ? v.toFixed(d == null ? 0 : d) + '%' : 'n/a'; };
  O.plural = function (n, w) { return n + ' ' + w + (n === 1 ? '' : 's'); };
  O.safeUrl = function (u) { return /^https?:\/\//i.test(u || '') ? u : null; };
  O.sleep = function (ms) { return new Promise(function (r) { setTimeout(r, ms); }); };
  O.trunc = function (s, n) { s = String(s || ''); return s.length > n ? s.slice(0, n - 1).replace(/\s+\S*$/, '') + '…' : s; };
  O.spinner = function () { return h('span', { class: 'spinner', 'aria-hidden': 'true' }); };
  O.setTitle = function (t) { document.title = t ? t + ' | Ouroboros' : 'Ouroboros: Research answers you can check'; };
  O.friendlyError = function (err) {
    var m = err && err.message ? err.message : String(err);
    return /Failed to fetch|NetworkError|Load failed/i.test(m) ? 'Could not reach the Ouroboros server. Check that it is running.' : m;
  };
  var isNum = O.isNum, pct = O.pct, plural = O.plural, safeUrl = O.safeUrl;

  /* ---------- icons and logo ---------- */
  var ICONS = {
    plus: 'M12 5v14M5 12h14',
    home: 'M4 11l8-7 8 7v8a1 1 0 0 1-1 1h-4v-6H9v6H5a1 1 0 0 1-1-1z',
    shield: 'M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6zM9 12l2.2 2.2L15 10',
    columns: 'M4 5h6v14H4zM14 5h6v14h-6z',
    chart: 'M5 20v-8M12 20V5M19 20v-5',
    flow: 'M4 5h6v5H4zM14 14h6v5h-6zM7 10v3a2 2 0 0 0 2 2h5',
    menu: 'M4 7h16M4 12h16M4 17h16',
    close: 'M6 6l12 12M18 6L6 18',
    'arrow-up': 'M12 19V5M6 11l6-6 6 6',
    'arrow-right': 'M5 12h14M13 6l6 6-6 6',
    search: 'M11 5a6 6 0 1 0 0 12 6 6 0 0 0 0-12zM20 20l-4.2-4.2',
    check: 'M5 12.5l4.5 4.5L19 7.5',
    alert: 'M12 4l9 16H3zM12 10v4M12 17v.01',
    info: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM12 11v5M12 8v.01',
    external: 'M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5',
    sun: 'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4',
    moon: 'M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z',
    monitor: 'M3 5h18v11H3zM8 20h8M12 16v4',
    book: 'M5 4h10a3 3 0 0 1 3 3v13H8a3 3 0 0 1-3-3zM5 17a3 3 0 0 1 3-3h10',
    globe: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18',
    layers: 'M12 3l9 5-9 5-9-5zM3 13l9 5 9-5',
    scale: 'M12 4v16M7 20h10M5 7h14M5 7l-3 7a3 3 0 0 0 6 0zM19 7l-3 7a3 3 0 0 0 6 0z',
    pen: 'M4 20l4-1 11-11-3-3L5 16zM14 6l3 3',
    doc: 'M7 3h8l4 4v14H7zM15 3v4h4M10 12h6M10 16h6',
    refresh: 'M20 11a8 8 0 0 0-14-4M4 4v4h4M4 13a8 8 0 0 0 14 4M20 20v-4h-4',
    copy: 'M9 9h11v11H9zM5 15V4h11',
    stop: 'M7 7h10v10H7z',
    chat: 'M4 5h16v11H10l-5 4v-4H4z',
    link: 'M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1',
    'chevron-down': 'M6 9l6 6 6-6',
    bolt: 'M13 3L5 13h6l-1 8 8-10h-6z'
  };
  O.icon = function (name, size) {
    var s = size || 20;
    var el = O.svg('svg', { viewBox: '0 0 24 24', width: s, height: s, fill: 'none', stroke: 'currentColor', 'stroke-width': 1.6, 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'aria-hidden': 'true', focusable: 'false', class: 'icon icon-' + name });
    el.append(O.svg('path', { d: ICONS[name] || ICONS.info }));
    return el;
  };

  /* The mark: a twisted bronze ribbon forming a loop (the ouroboros), from /static/img.
     O.logo(height=28, opts)   opts.word: add the OUROBOROS wordmark below (stacked lockup)
                               opts.rule: add the brass rule and double-slash ornament (with word)
     The mark PNG is about 1.49 times wider than tall. */
  var LOGO_RATIO = 636 / 496;
  O.logo = function (size, opts) {
    var hgt = size || 28; opts = opts || {};
    var w = Math.round(hgt * LOGO_RATIO);
    var src = hgt <= 40 ? '/static/img/logo-mark-128.png' : '/static/img/logo-mark.png';
    var set = hgt <= 40 ? '/static/img/logo-mark-128.png 1x, /static/img/logo-mark-320.png 2x' : '/static/img/logo-mark-320.png 1x, /static/img/logo-mark.png 2x';
    var img = h('img', { class: 'logo-img', src: src, srcset: set, alt: 'Ouroboros', width: String(w), height: String(hgt), decoding: 'async', style: 'width:' + w + 'px;height:' + hgt + 'px' });
    if (!opts.word) return h('span', { class: 'logo', style: 'width:' + w + 'px;height:' + hgt + 'px' }, img);
    var box = h('span', { class: 'logo-lockup' }, img, h('span', { class: 'logo-word' }, 'Ouroboros'));
    if (opts.rule) {
      var orn = h('span', { class: 'logo-rule', 'aria-hidden': 'true' });
      orn.innerHTML = '<i></i><svg viewBox="0 0 16 12" width="16" height="12" focusable="false"><path d="M7 1L4 11M12 1L9 11" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="butt"/></svg><i></i>';
      box.append(orn);
    }
    return h('span', { class: 'logo logo-full' }, box);
  };

  /* ---------- API layer (real or mock) ---------- */
  function fixture(name) {
    return fetch('/static/mock/' + name).then(function (r) {
      if (!r.ok) throw new Error('Sample file ' + name + ' is missing.');
      return r.json();
    });
  }
  function mockApi(path) {
    var p = path.split('?')[0];
    if (p === '/api/health') return Promise.resolve({ ok: true, offline: true, mock: true });
    if (p === '/api/runs') {
      return Promise.all([fixture('sample-run.json'), fixture('sample-run-standard.json')]).then(function (rs) {
        return [
          { run_id: 'sample-guarded', question: rs[0].question, mode: 'guarded', grade: rs[0].audit.grade, score: rs[0].audit.scores.evidence_support_score, saved_at: 'fixture' },
          { run_id: 'sample-standard', question: rs[1].question, mode: 'standard', grade: rs[1].audit.grade, score: rs[1].audit.scores.evidence_support_score, saved_at: 'fixture' }
        ];
      });
    }
    if (p.indexOf('/api/runs/') === 0) return fixture(p.slice(-8) === 'standard' ? 'sample-run-standard.json' : 'sample-run.json');
    if (p === '/api/benchmark') return fixture('benchmark.json');
    if (p === '/api/tests') return fixture('tests.json');
    if (p === '/api/audit' || p === '/api/plain') {
      return Promise.all([fixture('sample-run-standard.json'), O.sleep(900)]).then(function (a) {
        var run = a[0];
        if (p === '/api/plain') return { answer: run.synthesis.answer.replace(/\s*\[[0-9a-f]{12}#\d+\]/g, ''), confidence: run.synthesis.confidence, audit: run.audit };
        return run.audit;
      });
    }
    return Promise.reject(new Error('Not available in sample data mode.'));
  }
  O.api = function (path, opts) {
    if (O.MOCK) return mockApi(path, opts);
    return fetch(path, opts).then(function (r) {
      if (!r.ok) {
        return r.json().catch(function () { return {}; }).then(function (j) {
          throw new Error(j.error || j.detail || j.message || ('The server answered with status ' + r.status + '.'));
        });
      }
      return r.json();
    });
  };
  O.postJSON = function (path, body) {
    return O.api(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  };

  O.recordToEvents = function (run) {
    var ev = [{ type: 'start', question: run.question, mode: run.mode, config: run.config || {} }];
    (run.hops || []).forEach(function (hp) {
      ev.push({ type: 'hop_query', hop: hp.hop, query: hp.query, origin: hp.origin });
      ev.push({ type: 'hop_sources', hop: hp.hop, fetched: hp.fetched || {}, pool_size: hp.pool_size });
      ev.push({ type: 'hop_read', hop: hp.hop, passages: hp.passages || [], belief: hp.belief, confidence: hp.confidence, next_query: hp.next_query });
      ev.push({ type: 'hop_metrics', hop: hp.hop, baqd: hp.baqd == null ? null : hp.baqd, support: hp.support, contradict: hp.contradict, neutral: hp.neutral, skew: hp.skew, balance_loss: hp.balance_loss, domains: hp.domains, sources: hp.sources });
      (run.cqi_events || []).forEach(function (c) { if (c.hop === hp.hop) ev.push(Object.assign({ type: 'cqi' }, c)); });
    });
    if (run.synthesis) ev.push(Object.assign({ type: 'synthesis' }, run.synthesis));
    if (run.audit) ev.push({ type: 'audit', report: run.audit });
    ev.push({ type: 'done', run_id: run.run_id || '', usage: run.usage, seconds: run.seconds });
    return ev;
  };
  O.runSummary = function (run) {
    var b = (run.hops || []).map(function (x) { return x.baqd; }).filter(isNum);
    var last = (run.hops || [])[(run.hops || []).length - 1] || {};
    var doms = {};
    (run.hops || []).forEach(function (x) { (x.passages || []).forEach(function (p) { doms[p.domain] = 1; }); });
    return {
      mean_baqd: b.length ? b.reduce(function (a, c) { return a + c; }, 0) / b.length : null,
      max_baqd: b.length ? Math.max.apply(null, b) : null,
      final_skew: last.skew,
      cqi_count: (run.cqi_events || []).length,
      domains_total: Object.keys(doms).length,
      evidence_support_score: run.audit && run.audit.scores ? run.audit.scores.evidence_support_score : null
    };
  };

  O.sse = function (url, onEvent) {
    if (O.MOCK) return mockStream(url, onEvent);
    var ctrl = new AbortController();
    var done = fetch(url, { signal: ctrl.signal, headers: { Accept: 'text/event-stream' } }).then(function (r) {
      if (!r.ok) throw new Error('The server answered with status ' + r.status + '.');
      var reader = r.body.getReader(), dec = new TextDecoder(), buf = '';
      function pump() {
        return reader.read().then(function (res) {
          if (res.done) return;
          buf += dec.decode(res.value, { stream: true }).replace(/\r\n/g, '\n');
          var i;
          while ((i = buf.indexOf('\n\n')) >= 0) {
            var block = buf.slice(0, i); buf = buf.slice(i + 2);
            var data = block.split('\n').filter(function (l) { return l.indexOf('data:') === 0; })
              .map(function (l) { return l.slice(5).replace(/^ /, ''); }).join('\n');
            if (data) { try { onEvent(JSON.parse(data)); } catch (e) { console.error('bad event', e); } }
          }
          return pump();
        });
      }
      return pump();
    });
    return { done: done, stop: function () { ctrl.abort(); } };
  };
  function mockStream(url, onEvent) {
    var stopped = false;
    var q = new URLSearchParams(url.split('?')[1] || '');
    var isCompare = url.indexOf('/api/compare/') === 0;
    var dp = O.query('delay'), DL = dp == null ? null : Number(dp);
    function play(run, lane, delay) {
      var evs = O.recordToEvents(run);
      return (async function () {
        for (var i = 0; i < evs.length && !stopped; i++) {
          await O.sleep(delay);
          if (stopped) return;
          var e = Object.assign({}, evs[i]);
          if (lane) e.lane = lane;
          if (e.type === 'done') e.run_id = 'sample-' + (lane || run.mode);
          onEvent(e);
        }
      })();
    }
    var done = (async function () {
      if (isCompare) {
        var rs = await Promise.all([fixture('sample-run-standard.json'), fixture('sample-run.json')]);
        await Promise.all([play(rs[0], 'standard', DL == null ? 520 : DL), play(rs[1], 'guarded', DL == null ? 640 : DL)]);
        if (!stopped) onEvent({ type: 'compare_done', summary: { standard: O.runSummary(rs[0]), guarded: O.runSummary(rs[1]) } });
      } else {
        var run = await fixture(q.get('mode') === 'standard' ? 'sample-run-standard.json' : 'sample-run.json');
        await play(run, null, DL == null ? 650 : DL);
      }
    })();
    var handle = { done: done, stop: function () { stopped = true; } };
    handle.done = done.then(function () { if (stopped) { var e = new Error('stopped'); e.name = 'AbortError'; throw e; } });
    return handle;
  }

  /* ---------- router ---------- */
  var routes = {}, views = {}, cur = { name: null, params: {} }, pending = null;
  O.route = function (name, def) { routes[name] = def; };
  O.href = function (path) { return '#' + path; };
  O.current = function () { return cur; };
  O.go = function (path) {
    var target = '#' + path;
    if (location.hash === target) dispatch(); else location.hash = target;
  };
  O.openRun = function (id) { O.go('/r/' + encodeURIComponent(id)); };
  var lastStart = 0;
  O.startThread = function (req) { var now = Date.now(); if (now - lastStart < 1000) return; lastStart = now; pending = req; O.go('/thread'); };
  O.takePending = function () { var p = pending; pending = null; return p; };

  function parseHash() {
    var raw = (location.hash || '').replace(/^#\/?/, '');
    var parts = raw.split('?');
    var segs = parts[0].split('/').filter(Boolean).map(decodeURIComponent);
    return { name: segs[0] || 'ask', segs: segs, id: segs[1], query: new URLSearchParams(parts[1] || '') };
  }
  var NAV_FOR = { ask: 'ask', thread: 'ask', audit: 'audit', compare: 'compare', benchmark: 'benchmark', how: 'how' };
  function dispatch() {
    var p = parseHash();
    if (!routes[p.name]) { p = { name: 'ask', segs: ['ask'], query: new URLSearchParams() }; try { history.replaceState(null, '', '#/ask'); } catch (e) { /* keep the hash */ } }
    var def = routes[p.name];
    var host = O.$('#view');
    if (cur.name && views[cur.name] && cur.name !== p.name) {
      views[cur.name].classList.remove('is-active');
      var old = routes[cur.name];
      if (old && old.hide) { try { old.hide(views[cur.name]); } catch (e) { console.error(e); } }
    }
    var el = views[p.name];
    if (!el) {
      el = views[p.name] = h('section', { class: 'view', 'data-view': p.name });
      host.append(el);
      if (def && def.init) { try { def.init(el); } catch (e) { console.error(e); } }
    }
    el.classList.add('is-active');
    cur = { name: p.name, params: p };
    O.$$('.sb-link').forEach(function (a) { a.removeAttribute('aria-current'); if (a.dataset.route === NAV_FOR[p.name]) a.setAttribute('aria-current', 'page'); });
    O.setActiveRun(p.name === 'r' ? p.id : null);
    O.setTitle(def && def.title ? def.title : '');
    if (!def) { O.clear(el).append(h('div', { class: 'page' }, h('p', { class: 'muted' }, 'This page is not available.'))); }
    else if (def.show) { try { def.show(el, p); } catch (e) { console.error(e); O.clear(el).append(h('div', { class: 'page' }, h('div', { class: 'run-error', role: 'alert' }, 'This page could not be shown.'))); } }
    closeNav();
    window.scrollTo(0, 0);
  }
  window.addEventListener('hashchange', dispatch);

  /* ---------- popover ---------- */
  var pop = { el: null, timer: null };
  O.popover = {
    show: function (anchor, node) {
      pop.el = pop.el || O.$('#popover');
      clearTimeout(pop.timer);
      O.clear(pop.el).append(node);
      pop.el.hidden = false;
      var r = anchor.getBoundingClientRect(), w = pop.el.offsetWidth, hgt = pop.el.offsetHeight;
      var left = Math.max(12, Math.min(window.innerWidth - w - 12, r.left + r.width / 2 - w / 2));
      var top = r.bottom + 8;
      if (top + hgt > window.innerHeight - 8 && r.top - hgt - 8 > 8) top = r.top - hgt - 8;
      pop.el.style.left = left + 'px'; pop.el.style.top = top + 'px';
    },
    hide: function () { pop.el = pop.el || O.$('#popover'); pop.el.hidden = true; },
    attach: function (el, contentFn) {
      function on() { var c = contentFn(); if (c) O.popover.show(el, c); }
      el.addEventListener('mouseenter', on); el.addEventListener('focusin', on);
      el.addEventListener('mouseleave', O.popover.hide); el.addEventListener('focusout', O.popover.hide);
      el.addEventListener('keydown', function (e) { if (e.key === 'Escape') O.popover.hide(); });
    }
  };
  window.addEventListener('scroll', function () { if (pop.el && !pop.el.hidden) O.popover.hide(); }, { passive: true });

  /* ---------- domain badge, source card, citations ---------- */
  function domainOf(d) { return String(d || '').replace(/^www\./, ''); }
  /* A bare DOI prefix says nothing to a reader, so show what kind of source it is instead. */
  function domainLabel(doc) {
    var d = domainOf(doc.domain);
    if (/^(dx\.)?doi\.org/i.test(d)) return (O.SOURCE_LABELS[doc.source] || 'Journal') + ' paper';
    return d;
  }
  O.domainBadge = function (domain) {
    var d = domainOf(domain), sum = 0, i;
    for (i = 0; i < d.length; i++) sum = (sum * 31 + d.charCodeAt(i)) % 997;
    var ch = (d.match(/[a-z0-9]/i) || ['?'])[0];
    return h('span', { class: 'src-badge', 'data-av': String(sum % 6 + 1), 'aria-hidden': 'true' }, ch);
  };
  O.sourceCard = function (doc, n, opts) {
    var url = safeUrl(doc.url);
    var meta = [O.SOURCE_LABELS[doc.source] || doc.source || '', doc.year || ''].filter(Boolean).map(function (m) { return h('span', null, String(m)); });
    var attrs = { class: 'source-card', 'data-pid': doc.pid, 'aria-label': 'Source ' + n + ': ' + (doc.title || domainOf(doc.domain)) };
    if (url) { attrs.href = url; attrs.target = '_blank'; attrs.rel = 'noopener noreferrer'; }
    var card = h(url ? 'a' : 'div', attrs,
      h('div', { class: 'src-top' }, O.domainBadge(doc.domain), h('span', { class: 'src-domain' }, domainLabel(doc)), h('span', { class: 'src-num' }, String(n))),
      h('div', { class: 'src-title' }, doc.title || 'Untitled'),
      meta.length ? h('div', { class: 'src-meta' }, meta) : null);
    return card;
  };

  function Citations() { this.docs = {}; this.order = []; this.nums = {}; this.counter = 0; this.onJump = null; this.citedSet = {}; }
  Citations.prototype.add = function (p) {
    if (!p || !p.pid) return;
    var d = this.docs[p.pid];
    if (!d) { this.docs[p.pid] = Object.assign({}, p); this.order.push(p.pid); }
    else Object.keys(p).forEach(function (k) { if (d[k] == null && p[k] != null) d[k] = p[k]; });
  };
  Citations.prototype.addAll = function (list) { var self = this; (list || []).forEach(function (p) { self.add(p); }); };
  Citations.prototype.has = function (pid) { return !!this.docs[pid]; };
  Citations.prototype.get = function (pid) { return this.docs[pid] || null; };
  Citations.prototype.number = function (pid) {
    if (!this.docs[pid]) return null;
    if (!this.nums[pid]) this.nums[pid] = ++this.counter;
    return this.nums[pid];
  };
  Citations.prototype.setAnswer = function (text) {
    var self = this, re = /\[([A-Za-z0-9_-]+#\d+)\]/g, m;
    this.nums = {}; this.counter = 0; this.citedSet = {};
    while ((m = re.exec(text || ''))) { if (self.docs[m[1]]) { self.citedSet[m[1]] = 1; self.number(m[1]); } }
    this.order.forEach(function (pid) { self.number(pid); });
  };
  Citations.prototype.sources = function () {
    var self = this;
    this.order.forEach(function (pid) { self.number(pid); });
    return this.order.map(function (pid) { return { n: self.nums[pid], doc: self.docs[pid], cited: !!(self.citedSet && self.citedSet[pid]) }; })
      .sort(function (a, b) { return a.n - b.n; });
  };
  Citations.prototype.jump = function (pid) {
    if (this.onJump && this.onJump(pid) === true) return;
    var els = O.$$('[data-pid="' + pid + '"]').filter(function (e) { return e.offsetParent !== null; });
    var el = els[0]; if (!el) return;
    el.scrollIntoView({ block: 'center', behavior: O.REDUCED ? 'auto' : 'smooth' });
    el.classList.remove('flash'); void el.offsetWidth; el.classList.add('flash');
  };
  Citations.prototype.chip = function (pid) {
    var self = this, d = this.docs[pid];
    if (!d) return h('span', { class: 'cite is-dead', title: 'This source is not part of this view' }, '?');
    var n = this.number(pid);
    var btn = h('button', { type: 'button', class: 'cite', 'data-cite': pid, 'aria-label': 'Source ' + n + ': ' + (d.title || d.domain), onclick: function () { self.jump(pid); } }, String(n));
    O.popover.attach(btn, function () {
      return h('div', null,
        h('div', { class: 'pop-head' }, O.domainBadge(d.domain), h('span', { class: 'src-domain' }, domainLabel(d)), h('span', { class: 'src-num' }, String(n))),
        h('div', { class: 'pop-title' }, d.title || 'Untitled'),
        d.text ? h('p', { class: 'pop-snip' }, d.text) : null);
    });
    return btn;
  };
  Citations.prototype.render = function (text) {
    var out = [], re = /\[([A-Za-z0-9_-]+#\d+)\]/g, last = 0, m;
    text = text || '';
    while ((m = re.exec(text))) {
      var before = text.slice(last, m.index).replace(/\s+$/, '');
      if (before) out.push(before);
      out.push(this.chip(m[1]));
      last = m.index + m[0].length;
    }
    if (last < text.length) out.push(text.slice(last));
    return out;
  };
  O.Citations = Citations;
  O.citationsFromRun = function (run) {
    var c = new Citations();
    (run.hops || []).forEach(function (hp) { c.addAll(hp.passages); });
    c.setAnswer(run.synthesis && run.synthesis.answer);
    return c;
  };
  O.sourceRow = function (cites) {
    var items = cites.sources();
    var cited = items.filter(function (s) { return s.cited; });
    var list = cited.length ? cited : items;
    return h('div', { class: 'source-row', role: 'list', 'aria-label': 'Sources' }, list.map(function (s) {
      var c = O.sourceCard(s.doc, s.n); c.setAttribute('role', 'listitem'); return c;
    }));
  };
  O.answerBlock = function (text, cites) {
    var paras = String(text || '').split(/\n{2,}/).filter(Boolean);
    return h('div', { class: 'answer' }, paras.map(function (p) { return h('p', null, cites.render(p.trim())); }));
  };

  /* ---------- pills, rings, evidence card, claim cards ---------- */
  var VERDICT = { supported: 'Supported', contradicted: 'Contradicted', mixed: 'Mixed', not_verified: 'Not verified' };
  O.gradeClass = function (g) {
    return g === 'Well supported' ? 'g-well' : g === 'Partly supported' ? 'g-partly' : g === 'Contradicted by evidence' ? 'g-contra' : 'g-weak';
  };
  O.gradePill = function (grade) { return h('span', { class: 'pill grade-pill ' + O.gradeClass(grade) }, grade || 'No grade'); };
  O.verdictPill = function (v) { return h('span', { class: 'pill v-' + v }, VERDICT[v] || v); };
  O.modeBadge = function (mode) { return h('span', { class: 'badge badge-' + mode }, mode === 'guarded' ? 'Balanced' : 'Standard'); };

  O.scoreRing = function (value, opts) {
    opts = opts || {};
    var size = opts.size || 108, R = 45, C = 2 * Math.PI * R;
    var v = isNum(value) ? Math.max(0, Math.min(100, value)) : 0;
    var fill = O.svg('circle', { class: 'ring-fill', cx: 50, cy: 50, r: R, 'stroke-dasharray': C.toFixed(2), 'stroke-dashoffset': C.toFixed(2) });
    var el = h('div', { class: 'ring ' + (size < 64 ? 'ring-sm ' : '') + O.gradeClass(opts.grade), style: '--ring-size:' + size + 'px', role: 'img', 'aria-label': 'Evidence Support Score ' + (isNum(value) ? Math.round(value) + ' percent' : 'not available') },
      (function () { var s = O.svg('svg', { viewBox: '0 0 100 100' }); s.append(O.svg('circle', { class: 'ring-track', cx: 50, cy: 50, r: R }), fill); return s; })(),
      h('div', { class: 'ring-num' }, isNum(value) ? String(Math.round(value)) : 'n/a', isNum(value) ? h('small', null, '%') : null));
    var target = (C * (1 - v / 100)).toFixed(2);
    if (O.REDUCED) fill.setAttribute('stroke-dashoffset', target);
    else requestAnimationFrame(function () { requestAnimationFrame(function () { fill.setAttribute('stroke-dashoffset', target); }); });
    return el;
  };

  function countBy(claims, v) { return claims.filter(function (c) { return c.verdict === v; }).length; }
  O.evidenceCard = function (report, opts) {
    opts = opts || {};
    var sc = report.scores || {}, claims = report.claims || [];
    var score = sc.evidence_support_score;
    var nSup = countBy(claims, 'supported'), nCon = countBy(claims, 'contradicted'), nUnv = countBy(claims, 'not_verified'), nMix = countBy(claims, 'mixed');
    var stated = isNum(opts.stated) ? opts.stated : sc.stated_confidence;
    var gap = isNum(sc.calibration_gap) ? sc.calibration_gap : (isNum(stated) && isNum(score) ? stated - score : null);

    function row(label, value, hint) {
      return h('div', null, h('dt', null, label), h('dd', null, value, hint ? h('span', { class: 'hint' }, hint) : null));
    }
    var stats = h('dl', { class: 'ec-stats' },
      row('Independent websites', isNum(sc.distinct_domains) ? String(sc.distinct_domains) : 'n/a', 'across all the evidence used'),
      row('Claims backed by two or more websites', pct(sc.multi_source_share), 'share of the backed claims'),
      row('Contradicted by the evidence', plural(nCon, 'claim'), pct(sc.contradicted_share)),
      row('Not verified', plural(nUnv, 'claim'), 'no source we found covers them'),
      isNum(sc.citation_faithfulness) ? row('Citations that back their claim', pct(sc.citation_faithfulness)) : null);

    var gapEl = null;
    if (isNum(stated) && isNum(score)) {
      var verdict = (gap != null && gap > 5) ? 'That is more sure than the evidence supports.' : (gap != null && gap < -5) ? 'That is less sure than the evidence supports.' : 'That is about what the evidence supports.';
      gapEl = h('p', { class: 'ec-gap' }, 'The answer stated ' + Math.round(stated) + '% confidence. The evidence backs ' + Math.round(score) + '% of its claims. ' + verdict);
    }
    return h('section', { class: 'card evidence-card', 'aria-label': opts.title || 'Evidence' },
      h('div', { class: 'card-title' }, opts.title || 'Evidence'),
      h('div', { class: 'ec-head' }, O.scoreRing(score, { grade: report.grade }),
        h('div', { class: 'ec-head-text' }, O.gradePill(report.grade), h('div', { class: 'ec-claims' }, nSup + ' of ' + plural(claims.length, 'claim') + ' backed'),
          nMix ? h('div', { class: 'hint' }, plural(nMix, 'mixed claim') + ' count as half') : null)),
      h('p', { class: 'ec-lead' }, 'Evidence Support Score: the share of the answer’s claims backed by the evidence we found.'),
      stats, gapEl,
      h('p', { class: 'honesty' }, 'This is not the chance the answer is true. Not verified means no source we found covers the claim. It does not mean the claim is false.'));
  };

  O.claimCards = function (src, opts) {
    opts = opts || {};
    var claims = Array.isArray(src) ? src : (src && src.claims) || [];
    if (!claims.length) return h('p', { class: 'muted' }, 'No claims were extracted from this answer.');
    var cites = opts.cites || new Citations();
    claims.forEach(function (c) { (c.evidence || []).forEach(function (e) { cites.add(e); }); });
    return h('div', { class: 'claim-list' }, claims.map(function (c) {
      var seenEv = {}, uniq = [];
      (c.evidence || []).forEach(function (e) {
        var k = e.relation + '|' + (e.title || '') + '|' + (e.domain || '');
        if (seenEv[k]) { seenEv[k].dup.push(e); return; }
        seenEv[k] = { e: e, dup: [] }; uniq.push(seenEv[k]);
      });
      var ev = uniq.map(function (u) {
        var e = u.e, url = safeUrl(e.url);
        return h('li', null,
          h('span', { class: 'rel rel-' + e.relation }, e.relation === 'contradicts' ? 'Contradicts' : 'Supports'),
          cites.has(e.pid) ? cites.chip(e.pid) : null,
          url ? h('a', { class: 'ev-link', href: url, target: '_blank', rel: 'noopener noreferrer' }, e.title || e.domain || url) : h('span', null, e.title || ''),
          h('span', { class: 'muted small' }, domainOf(e.domain) + (u.dup.length ? ' x' + (u.dup.length + 1) : '')));
      });
      var n = c.independent_sources;
      return h('article', { class: 'claim-card v-' + c.verdict },
        h('div', { class: 'claim-top' }, O.verdictPill(c.verdict), isNum(n) && c.verdict !== 'not_verified' ? h('span', { class: 'muted small' }, plural(n, 'independent website')) : null),
        h('p', { class: 'claim-text' }, c.text),
        c.note ? h('p', { class: 'claim-note' }, /verification call failed/i.test(c.note) ? 'This claim could not be checked.' : c.note) : null,
        ev.length ? h('ul', { class: 'claim-ev' }, ev) : h('p', { class: 'claim-nosrc' }, /verification call failed/i.test(c.note || '') ? 'Not checked, so it is not counted as covered or uncovered.' : 'No source we found covers this claim.'));
    }));
  };

  /* ---------- small widgets ---------- */
  O.balanceBar = function (s, n, c) {
    s = s || 0; n = n || 0; c = c || 0;
    var t = Math.max(1, s + n + c);
    return h('div', { class: 'bal', role: 'img', 'aria-label': s + ' support, ' + n + ' neutral, ' + c + ' contradict' },
      h('i', { class: 's', style: 'width:' + s / t * 100 + '%' }), h('i', { class: 'n', style: 'width:' + n / t * 100 + '%' }), h('i', { class: 'c', style: 'width:' + c / t * 100 + '%' }));
  };
  O.baqdBar = function (baqd, thr) {
    thr = isNum(thr) ? thr : 0.05;
    var SC = 0.2;
    if (!isNum(baqd)) return h('div', { class: 'bar', 'aria-label': 'No value at hop 1' }, h('i', { class: 'bar-zero' }));
    var w = Math.min(1, Math.abs(baqd) / SC) * 50, over = baqd > thr;
    return h('div', { class: 'bar', role: 'img', 'aria-label': 'BAQD ' + baqd.toFixed(3) + ', scale minus 0.2 to plus 0.2' },
      h('i', { class: 'bar-zero' }),
      h('i', { class: 'bar-fill' + (over ? ' over' : ''), style: baqd >= 0 ? 'left:50%;width:' + w + '%' : 'right:50%;width:' + w + '%' }),
      h('i', { class: 'bar-thr', style: 'left:' + (50 + thr / SC * 50) + '%' }));
  };

  O.steps = function (labels) {
    var items = labels.map(function (l) {
      var mark = h('span', { class: 'step-mark' }); mark.append(O.icon('check', 12));
      return h('li', { class: 'step', 'data-state': 'pending' }, mark, h('span', null, l));
    });
    var el = h('ol', { class: 'steps', 'aria-label': 'Progress' }, items);
    function set(i, st) { if (items[i]) items[i].setAttribute('data-state', st); }
    return {
      el: el,
      activate: function (i) { items.forEach(function (_, k) { set(k, k < i ? 'done' : k === i ? 'active' : 'pending'); }); },
      done: function (i) { set(i, 'done'); },
      finish: function () { items.forEach(function (_, k) { set(k, 'done'); }); },
      fail: function (i) { set(i, 'error'); },
      reset: function () { items.forEach(function (_, k) { set(k, 'pending'); }); }
    };
  };

  O.tabs = function (cfg) {
    var ids = cfg.tabs.map(function (t) { return t.id; }), uid = 't' + Math.random().toString(36).slice(2, 7);
    var list = h('div', { class: 'tabs', role: 'tablist' }), btns = {}, panels = {};
    var root = h('div', { class: 'tabs-root' });
    cfg.tabs.forEach(function (t) {
      var count = h('span', { class: 'tab-count', hidden: t.count == null }, t.count == null ? '' : String(t.count));
      var b = h('button', { type: 'button', class: 'tab', role: 'tab', id: uid + '-tab-' + t.id, 'aria-controls': uid + '-panel-' + t.id, 'aria-selected': 'false', tabindex: '-1', onclick: function () { select(t.id, true); } }, t.label, count);
      b._count = count; btns[t.id] = b; list.append(b);
    });
    list.addEventListener('keydown', function (e) {
      var i = ids.indexOf(root.active);
      var n = e.key === 'ArrowRight' ? i + 1 : e.key === 'ArrowLeft' ? i - 1 : e.key === 'Home' ? 0 : e.key === 'End' ? ids.length - 1 : null;
      if (n == null) return;
      e.preventDefault(); select(ids[(n + ids.length) % ids.length], true);
    });
    root.append(list);
    ids.forEach(function (id) {
      var p = h('div', { class: 'tabpanel', role: 'tabpanel', id: uid + '-panel-' + id, 'aria-labelledby': uid + '-tab-' + id, hidden: true }, (cfg.panels || {})[id]);
      panels[id] = p; root.append(p);
    });
    function select(id, focus) {
      if (ids.indexOf(id) < 0) return;
      root.active = id;
      ids.forEach(function (k) {
        var on = k === id;
        btns[k].setAttribute('aria-selected', on ? 'true' : 'false'); btns[k].tabIndex = on ? 0 : -1; panels[k].hidden = !on;
      });
      if (focus) btns[id].focus();
      if (cfg.onChange) cfg.onChange(id);
    }
    root.select = function (id) { select(id, false); };
    root.setCount = function (id, n) { var c = btns[id] && btns[id]._count; if (c) { c.hidden = n == null; c.textContent = String(n); } };
    root.panel = function (id) { return panels[id]; };
    select(cfg.active || ids[0], false);
    return root;
  };

  O.composer = function (cfg) {
    cfg = cfg || {};
    var withOptions = cfg.options !== false;
    var uid = 'cmp' + (++composerSeq);
    var ta = h('textarea', { rows: 1, maxlength: 400, placeholder: cfg.placeholder || 'Ask a question', 'aria-label': cfg.label || 'Your question' });
    var sw = h('input', { type: 'checkbox', role: 'switch', checked: true });
    var radios = O.DEPTH.map(function (d) {
      return h('input', { type: 'radio', name: uid + '-depth', value: d.id, checked: d.id === 'standard' });
    });
    var btn = h('button', { type: 'submit', class: 'btn-ask', 'aria-label': 'Ask' }, O.icon('arrow-up', 20));
    var busy = false;
    var optLabel = h('span', null);
    var optBtn = withOptions ? h('button', { type: 'button', class: 'opt-btn', 'aria-expanded': 'false', 'aria-haspopup': 'true', 'aria-label': 'Search options' }, optLabel, O.icon('chevron-down', 14)) : null;
    var menu = null;
    if (withOptions) {
      menu = h('div', { class: 'opt-menu', hidden: true, role: 'group', 'aria-label': 'Search options' },
        h('label', { class: 'switch' }, sw, h('span', { class: 'switch-track' }), h('span', null, 'Balanced search')),
        h('p', { class: 'hint' }, 'Also looks for the other side when the search starts to lean one way.'),
        h('fieldset', { class: 'opt-group' }, h('legend', null, 'Depth'),
          O.DEPTH.map(function (d, i) {
            return h('label', { class: 'opt-radio' }, radios[i], h('span', null, d.label), h('small', null, d.hops + ' rounds'));
          })));
    }
    var bar = h('div', { class: 'composer-bar' }, optBtn, h('span', { class: 'spacer' }), btn);
    var form = h('form', { class: 'composer' + (cfg.large ? ' composer-lg' : ''), autocomplete: 'off' }, ta, bar, menu);
    function depthObj() { for (var i = 0; i < radios.length; i++) if (radios[i].checked) return O.DEPTH[i]; return O.DEPTH[1]; }
    function labelNow() { if (optLabel) optLabel.textContent = (sw.checked ? 'Balanced' : 'Plain') + ', ' + depthObj().label; }
    function setMenu(open) {
      if (!menu) return;
      menu.hidden = !open; optBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
    }
    if (withOptions) {
      optBtn.addEventListener('click', function () { setMenu(menu.hidden); });
      sw.addEventListener('change', labelNow);
      radios.forEach(function (r) { r.addEventListener('change', labelNow); });
      document.addEventListener('click', function (e) { if (!menu.hidden && !form.contains(e.target)) setMenu(false); });
      form.addEventListener('keydown', function (e) { if (e.key === 'Escape' && !menu.hidden) { setMenu(false); optBtn.focus(); } });
      labelNow();
    }
    function grow() { ta.style.height = 'auto'; ta.style.height = Math.min(ta.scrollHeight, 220) + 'px'; }
    function sync() { btn.disabled = !busy && !ta.value.trim(); }
    function opts() { var d = depthObj(); return { guarded: sw.checked, depth: d.id, hops: d.hops }; }
    ta.addEventListener('input', function () { grow(); sync(); });
    ta.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); form.requestSubmit(); }
    });
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      if (busy) { if (cfg.onStop) cfg.onStop(); return; }
      var q = ta.value.trim(); if (!q) return;
      setMenu(false);
      if (cfg.onSubmit) cfg.onSubmit(q, opts());
    });
    if (cfg.value) ta.value = cfg.value;
    sync();
    return {
      el: form, input: ta,
      getValue: function () { return ta.value.trim(); },
      setValue: function (v) { ta.value = v || ''; grow(); sync(); },
      getOptions: opts,
      setOptions: function (o) {
        if (!o) return;
        if (typeof o.guarded === 'boolean') sw.checked = o.guarded;
        if (o.depth) radios.forEach(function (r) { r.checked = r.value === o.depth; });
        labelNow();
      },
      setBusy: function (b) {
        busy = !!b; btn.classList.toggle('is-stop', busy);
        btn.setAttribute('aria-label', busy ? 'Stop' : 'Ask');
        O.clear(btn).append(O.icon(busy ? 'stop' : 'arrow-up', busy ? 16 : 20));
        sync();
      },
      focus: function () { ta.focus(); }
    };
  };
  var composerSeq = 0;

  O.toast = function (msg) {
    var t = h('div', { class: 'toast', role: 'status' }, msg);
    document.body.append(t);
    setTimeout(function () { t.remove(); }, 2600);
  };

  /* ---------- charts ---------- */
  function niceStep(raw) {
    var p = Math.pow(10, Math.floor(Math.log10(raw))), f = raw / p;
    return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * p;
  }
  O.lineChart = function (host, o) {
    var W = Math.max(260, host.clientWidth || 600), H = 240, m = { l: 56, r: 34, t: 16, b: 58 };
    var ys = [];
    o.series.forEach(function (se) { se.points.forEach(function (p) { if (isNum(p.y)) ys.push(p.y); }); });
    if (isNum(o.threshold)) ys.push(o.threshold);
    var ymin, ymax, step;
    if (o.fixedY) { ymin = o.fixedY[0]; ymax = o.fixedY[1]; step = (ymax - ymin) / 4; }
    else {
      ymin = Math.min.apply(null, ys.concat([0])); ymax = Math.max.apply(null, ys.concat([0.1]));
      step = niceStep((ymax - ymin) / 4);
      ymin = Math.floor(ymin / step + 1e-9) * step; ymax = Math.ceil(ymax / step - 1e-9) * step;
    }
    var dec = 0;
    while (dec < 3 && Math.abs(step * Math.pow(10, dec) - Math.round(step * Math.pow(10, dec))) > 1e-6) dec++;
    var xmin = o.xmin == null ? 1 : o.xmin, xmax = Math.max(o.xmax || 2, xmin + 1);
    function sx(x) { return m.l + (x - xmin) / (xmax - xmin) * (W - m.l - m.r); }
    function sy(y) { return H - m.b - (y - ymin) / (ymax - ymin) * (H - m.t - m.b); }
    var s = O.svg('svg', { viewBox: '0 0 ' + W + ' ' + H, width: W, height: H, role: 'img', 'aria-label': o.aria || 'Line chart', class: 'chart' });
    var n = Math.round((ymax - ymin) / step);
    for (var i = 0; i <= n; i++) {
      var v = ymin + i * step, y = sy(v);
      s.append(O.svg('line', { x1: m.l, x2: W - m.r, y1: y, y2: y, class: Math.abs(v) < 1e-9 ? 'zero' : 'grid' }));
      s.append(O.svg('text', { x: m.l - 8, y: y + 4, 'text-anchor': 'end' }, v.toFixed(dec)));
    }
    s.append(O.svg('line', { x1: m.l, x2: m.l, y1: m.t, y2: H - m.b, class: 'axis' }));
    s.append(O.svg('line', { x1: m.l, x2: W - m.r, y1: H - m.b, y2: H - m.b, class: 'axis' }));
    for (var x = xmin; x <= xmax; x++) {
      s.append(O.svg('line', { x1: sx(x), x2: sx(x), y1: H - m.b, y2: H - m.b + 4, class: 'axis' }));
      s.append(O.svg('text', { x: sx(x), y: H - m.b + 18, 'text-anchor': 'middle' }, 'Hop ' + x));
    }
    s.append(O.svg('text', { x: m.l + (W - m.l - m.r) / 2, y: H - 6, 'text-anchor': 'middle', class: 'ttl' }, o.xTitle || 'Hop'));
    var cy0 = m.t + (H - m.t - m.b) / 2;
    s.append(O.svg('text', { x: 14, y: cy0, 'text-anchor': 'middle', class: 'ttl', transform: 'rotate(-90 14 ' + cy0 + ')' }, o.yTitle || ''));
    if (isNum(o.threshold)) {
      var ty = sy(o.threshold);
      s.append(O.svg('line', { x1: m.l, x2: W - m.r, y1: ty, y2: ty, class: 'thr' }));
      s.append(O.svg('text', { x: W - m.r - 4, y: ty - 5, 'text-anchor': 'end', class: 'thr-l' }, o.thresholdLabel || ''));
    }
    o.series.forEach(function (se) {
      var pts = se.points.filter(function (p) { return isNum(p.y); });
      if (pts.length > 1) s.append(O.svg('polyline', { points: pts.map(function (p) { return sx(p.x) + ',' + sy(p.y); }).join(' '), fill: 'none', stroke: se.color, 'stroke-width': 2.5, 'stroke-linejoin': 'round', 'stroke-dasharray': se.dash || 'none' }));
      se.points.forEach(function (p) {
        if (!isNum(p.y)) { if (o.nullLabel) s.append(O.svg('text', { x: sx(p.x), y: H - m.b + 33, 'text-anchor': 'middle' }, o.nullLabel)); return; }
        var cx = sx(p.x), cy = sy(p.y);
        var t = O.svg('title', {}, (se.name ? se.name + ', ' : '') + 'hop ' + p.x + ': ' + p.y.toFixed(3) + (p.mark ? ' (counter-search hop)' : ''));
        var mk = p.mark
          ? O.svg('rect', { x: cx - 6, y: cy - 6, width: 12, height: 12, transform: 'rotate(45 ' + cx + ' ' + cy + ')', fill: 'var(--surface)', stroke: se.color, 'stroke-width': 2.5 })
          : O.svg('circle', { cx: cx, cy: cy, r: 5, fill: se.color, stroke: 'var(--surface)', 'stroke-width': 1.5 });
        mk.append(t); s.append(mk);
        if (o.series.length === 1) s.append(O.svg('text', { x: cx, y: cy - 11, 'text-anchor': 'middle', style: 'fill:var(--ink-2);font-size:11px;stroke:var(--surface);stroke-width:3px;paint-order:stroke' }, p.y.toFixed(dec > 2 ? 3 : 2)));
      });
    });
    host.replaceChildren(s);
  };
  O.watchResize = function (host, redraw) {
    if (!window.ResizeObserver) return;
    var last = 0;
    new ResizeObserver(function () { var w = host.clientWidth; if (w && Math.abs(w - last) > 4) { last = w; redraw(); } }).observe(host);
  };

  /* ---------- sidebar: recent runs, theme, connection, drawer ---------- */
  var activeRun = null;
  O.setActiveRun = function (id) {
    activeRun = id;
    O.$$('.sb-run').forEach(function (a) { if (a.dataset.run === id) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current'); });
  };
  function runWhen(iso) {
    var d = iso ? new Date(iso) : null;
    if (!d || isNaN(d)) return '';
    var now = new Date(), t = d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
    if (d.toDateString() === now.toDateString()) return 'Today ' + t;
    return d.toLocaleDateString([], { day: 'numeric', month: 'short' });
  }
  O.refreshRuns = function () {
    var host = O.$('#sb-recent');
    return O.api('/api/runs').then(function (runs) {
      O.clear(host);
      if (!runs || !runs.length) { host.append(h('p', { class: 'sb-empty' }, 'Your finished research will be listed here.')); return; }
      var seen = {};
      runs = runs.filter(function (r) { var k = String(r.question || '').trim().toLowerCase(); if (seen[k]) return false; seen[k] = 1; return true; });
      runs.slice(0, 6).forEach(function (r) {
        var tip = r.question + [isNum(r.score) ? Math.round(r.score) + '% backed' : '', runWhen(r.saved_at)].filter(Boolean).map(function (x) { return ', ' + x; }).join('');
        var a = h('a', { class: 'sb-run', role: 'listitem', href: O.href('/r/' + encodeURIComponent(r.run_id)), 'data-run': r.run_id, title: tip },
          h('span', { class: 'sb-run-q' }, r.question));
        if (r.run_id === activeRun) a.setAttribute('aria-current', 'page');
        host.append(a);
      });
    }).catch(function () { O.clear(host).append(h('p', { class: 'sb-empty' }, 'Recent research could not be loaded.')); });
  };

  var themeBtns = {};
  O.theme = {
    get: function () { try { var t = localStorage.getItem('ouro-theme'); return t === 'light' || t === 'dark' ? t : 'system'; } catch (e) { return 'system'; } },
    set: function (v) {
      var root = document.documentElement;
      if (v === 'light' || v === 'dark') root.setAttribute('data-theme', v); else root.removeAttribute('data-theme');
      try { if (v === 'system') localStorage.removeItem('ouro-theme'); else localStorage.setItem('ouro-theme', v); } catch (e) { /* storage may be blocked */ }
      Object.keys(themeBtns).forEach(function (k) { themeBtns[k].setAttribute('aria-pressed', k === v ? 'true' : 'false'); });
    }
  };
  function initTheme() {
    var host = O.$('#theme-toggle');
    [['system', 'Auto', 'monitor'], ['light', 'Light', 'sun'], ['dark', 'Dark', 'moon']].forEach(function (t) {
      var b = h('button', { type: 'button', 'aria-pressed': 'false', 'aria-label': t[1] + ' colour theme', onclick: function () { O.theme.set(t[0]); } }, O.icon(t[2], 16));
      themeBtns[t[0]] = b; host.append(b);
    });
    var cur0 = O.theme.get();
    Object.keys(themeBtns).forEach(function (k) { themeBtns[k].setAttribute('aria-pressed', k === cur0 ? 'true' : 'false'); });
  }

  O.health = function () {
    var box = O.$('#conn'), txt = O.$('#conn-text');
    function set(state, text) { box.setAttribute('data-state', state); box.setAttribute('title', text); txt.textContent = text; }
    return O.api('/api/health').then(function (r) {
      if (r.mock) set('offline', 'Sample data');
      else if (r.offline) set('offline', 'Offline mode');
      else set('ready', 'Connected');
    }).catch(function () { set('down', 'Not connected'); });
  };

  function closeNav() {
    if (!document.body.classList.contains('nav-open')) return;
    document.body.classList.remove('nav-open');
    var mc = O.$('.main-col'); if (mc) mc.inert = false;
    var b = O.$('#nav-open'); b.setAttribute('aria-expanded', 'false');
  }
  function initNav() {
    var open = O.$('#nav-open'), close = O.$('#nav-close');
    open.append(O.icon('menu', 22)); close.append(O.icon('close', 22));
    open.addEventListener('click', function () {
      document.body.classList.add('nav-open'); open.setAttribute('aria-expanded', 'true');
      var mc = O.$('.main-col'); if (mc) mc.inert = true;
      close.focus({ focusVisible: false });
    });
    close.addEventListener('click', function () { closeNav(); open.focus({ focusVisible: false }); });
    O.$('#scrim').addEventListener('click', function () { closeNav(); open.focus({ focusVisible: false }); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') { O.popover.hide(); if (document.body.classList.contains('nav-open')) { closeNav(); open.focus({ focusVisible: false }); } } });
    O.$$('.sidebar a').forEach(function (a) { a.addEventListener('click', closeNav); });
    var skip = O.$('.skip');
    if (skip) skip.addEventListener('click', function (e) { e.preventDefault(); var v = O.$('#view'); if (v) v.focus(); });
  }
  function fillSlots() {
    O.$$('[data-slot]').forEach(function (s) {
      var k = s.getAttribute('data-slot');
      if (k === 'logo') s.replaceWith(O.logo(20));
      else if (k.indexOf('icon-') === 0) s.replaceWith(O.icon(k.slice(5), 18));
    });
  }

  /* ---------- boot ---------- */
  function boot() {
    fillSlots(); initTheme(); initNav();
    if (O.MOCK) O.$('#mock-banner').hidden = false;
    O.health(); O.refreshRuns();
    dispatch();
  }
  /* Deferred scripts run while readyState is 'interactive', so wait for DOMContentLoaded to let every page script register its route first. */
  if (document.readyState === 'complete') boot(); else document.addEventListener('DOMContentLoaded', boot);
})();
