/* Thread page: #/thread (live) and #/r/<run_id> (saved run replayed instantly). Owned by HOME+THREAD.
   One Thread per view. A Thread holds Turns (question, sources, answer, evidence, tabs) and a sticky follow-up box.
   Every Turn is fed the same event objects whether they come from the live stream or from a saved record. */
(function () {
  'use strict';
  var h = O.h, isNum = O.isNum;

  var STEP_LABELS = ['Searching sources', 'Reading passages', 'Checking the search for bias', 'Writing the answer', 'Checking every claim'];
  var STANCE = {
    support: { label: 'Agrees with the belief', cls: 'st-support' },
    contradict: { label: 'Goes against the belief', cls: 'st-contradict' },
    neutral: { label: 'Neutral', cls: 'st-neutral' }
  };
  var VERDICT = { supported: 'Backed', contradicted: 'Contradicted', mixed: 'Mixed', not_verified: 'Not verified' };

  /* Long names on wide screens, short ones on phones so every tab stays visible. */
  function tabLabel(long, short) { return h('span', null, h('span', { class: 'tl-long' }, long), h('span', { class: 'tl-short' }, short)); }
  function domainOf(d) { return String(d || '').split('/')[0].replace(/^www\./, ''); }
  /* A bare DOI prefix says nothing to a reader, so name the kind of source instead. */
  function siteLabel(d) {
    var dom = domainOf(d.domain);
    if (/^(dx\.)?doi\.org/i.test(dom)) return (O.SOURCE_LABELS[d.source] || 'Journal') + ' paper';
    return dom;
  }
  function metaLine(d) { return siteLabel(d) + (d.year ? ', ' + d.year : ''); }
  function pctOf(v) { return O.isNum(v) ? O.pct(v, 0) : null; }

  /* ---------- evidence block (shared with Check an AI answer and Compare) ---------- */
  function countBy(claims, v) { return claims.filter(function (c) { return c.verdict === v; }).length; }

  O.evBlock = function (report, opts) {
    opts = opts || {};
    var sc = report.scores || {}, claims = report.claims || [], score = sc.evidence_support_score;
    var nSup = countBy(claims, 'supported'), nCon = countBy(claims, 'contradicted'), nUnv = countBy(claims, 'not_verified'), nMix = countBy(claims, 'mixed');
    var stated = O.isNum(opts.stated) ? opts.stated : sc.stated_confidence;
    var uid = 'ev' + Math.random().toString(36).slice(2, 7);

    var facts = [];
    if (O.isNum(sc.distinct_domains)) facts.push(O.plural(sc.distinct_domains, 'website') + ' behind the claims');
    var multi = pctOf(sc.multi_source_share);
    if (multi && nSup) facts.push(multi + ' backed by two or more');
    facts.push(nCon + ' contradicted');

    function row(label, value) { return h('div', { class: 'ev-row' }, h('dt', null, label), h('dd', null, value)); }
    var rows = [];
    if (opts.mode && O.MODE_LABEL[opts.mode]) rows.push(row('Search style', O.MODE_LABEL[opts.mode]));
    rows.push(row('Not verified', O.plural(nUnv, 'claim') + ', no source we found covers them'));
    if (nMix) rows.push(row('Mixed', O.plural(nMix, 'claim') + ', counted as half'));
    if (O.isNum(sc.citation_faithfulness)) rows.push(row('Citations that back their claim', O.pct(sc.citation_faithfulness, 0)));
    var gapText = null;
    if (O.isNum(stated) && O.isNum(score)) {
      var gap = O.isNum(sc.calibration_gap) ? sc.calibration_gap : stated - score;
      gapText = 'The answer stated ' + Math.round(stated) + '% confidence. The evidence backs ' + Math.round(score) + '% of its claims. ' +
        (gap > 5 ? 'That is more sure than the evidence supports.' : gap < -5 ? 'That is less sure than the evidence supports.' : 'That is about what the evidence supports.');
    }
    var more = h('div', { class: 'ev-more', id: uid, hidden: true },
      h('dl', { class: 'ev-rows' }, rows),
      gapText ? h('p', { class: 'ev-gap' }, gapText) : null,
      h('p', { class: 'ev-def' }, 'The Evidence Support Score is the share of the answer’s claims backed by the evidence we retrieved. It is not the chance the answer is true. The grade also considers how many independent websites back each claim. Not verified means no source we found covers the claim. It does not mean the claim is false.'));
    var chev = O.icon('chevron-down', 16);
    var tog = h('button', { type: 'button', class: 'ev-toggle', 'aria-expanded': 'false', 'aria-controls': uid, onclick: function () {
      var open = tog.getAttribute('aria-expanded') !== 'true';
      tog.setAttribute('aria-expanded', open ? 'true' : 'false'); more.hidden = !open;
    } }, h('span', null, 'Details'), chev);

    return h('section', { class: 'ev', 'aria-label': opts.title || 'Evidence' },
      h('div', { class: 'ev-main' },
        O.scoreRing(score, { size: 56, grade: report.grade }),
        h('div', { class: 'ev-text' },
          h('div', { class: 'ev-cap' }, 'Evidence Support Score'),
          h('div', { class: 'ev-grade ' + O.gradeClass(report.grade) }, report.grade || 'No grade'),
          h('div', { class: 'ev-sub' }, nSup + ' of ' + O.plural(claims.length, 'claim') + ' backed'),
          report.grade === 'Partly supported' && O.isNum(score) && score >= 80 ? h('div', { class: 'ev-sub ev-qual' }, 'Few sources agree with each other, so the grade is held back.') : null),
        tog),
      h('p', { class: 'ev-facts' }, facts.join(', ')),
      more);
  };

  /* ---------- claim rows ---------- */
  O.claimRows = function (src, opts) {
    opts = opts || {};
    var claims = Array.isArray(src) ? src : (src && src.claims) || [];
    if (!claims.length) return h('p', { class: 'muted' }, 'No claims were extracted from this answer.');
    var cites = opts.cites || new O.Citations();
    claims.forEach(function (c) { (c.evidence || []).forEach(function (e) { cites.add(e); }); });
    return h('div', { class: 'cl-list' }, claims.map(function (c) {
      var seen = {}, uniq = [];
      (c.evidence || []).forEach(function (e) {
        var k = e.relation + '|' + (e.title || '') + '|' + (e.domain || '');
        if (seen[k]) { seen[k].n++; return; }
        seen[k] = { e: e, n: 1 }; uniq.push(seen[k]);
      });
      var failed = /verification call failed/i.test(c.note || '');
      var ev = uniq.map(function (u) {
        var e = u.e, url = O.safeUrl(e.url);
        return h('li', null,
          cites.has(e.pid) ? cites.chip(e.pid) : h('span'),
          h('div', { class: 'cl-src' },
            url ? h('a', { class: 'cl-link', href: url, target: '_blank', rel: 'noopener noreferrer' }, e.title || e.domain || url) : h('span', { class: 'cl-link' }, e.title || ''),
            h('span', { class: 'cl-dom' }, siteLabel(e) + (u.n > 1 ? ' x' + u.n : '')),
            e.relation === 'contradicts' ? h('span', { class: 'cl-rel' }, 'contradicts') : null));
      });
      var n = c.independent_sources;
      return h('article', { class: 'cl v-' + c.verdict },
        h('div', { class: 'cl-top' }, h('span', { class: 'vd vd-' + c.verdict }, VERDICT[c.verdict] || c.verdict),
          O.isNum(n) && c.verdict !== 'not_verified' ? h('span', { class: 'cl-n' }, O.plural(n, 'independent website')) : null),
        h('p', { class: 'cl-text' }, c.text),
        c.note ? h('p', { class: 'cl-note' }, failed ? 'This claim could not be checked.' : c.note) : null,
        ev.length ? h('ul', { class: 'cl-ev' }, ev)
          : h('p', { class: 'cl-note' }, failed ? 'Not checked, so it is not counted as covered or uncovered.' : 'No source we found covers this claim.'));
    }));
  };

  /* ====================================================================== shared renderers
     O.evidenceMap(report, {onSource})   claims to sources, grouped by source type (graph on wide, stacked cards on phones)
     O.beliefJourney(model)              BAQD, balance, guard and belief per round. model = {rounds:[...], threshold}. el.update(model)
     O.answerXray(model)                 side panel "How this answer was made". model comes from Turn.prototype.xrayModel */
  var SRC_ORDER = ['wikipedia', 'openalex', 'arxiv', 'pubmed', 'web'];
  function docId(pid) { return String(pid || '').split('#')[0]; }
  function sv(tag, attrs, text) { return O.svg(tag, attrs, text); }
  function cut(s, n) { s = String(s || ''); return s.length > n ? s.slice(0, Math.max(1, n - 1)).replace(/\s+\S*$/, '') + '…' : s; }
  function wrapLines(s, max, maxLines) {
    var words = String(s || '').split(/\s+/).filter(Boolean), lines = [], cur = '';
    words.forEach(function (w) {
      if (!cur) cur = w;
      else if ((cur + ' ' + w).length <= max) cur += ' ' + w;
      else { lines.push(cur); cur = w; }
    });
    if (cur) lines.push(cur);
    if (lines.length > maxLines) {
      lines = lines.slice(0, maxLines);
      var last = lines[maxLines - 1];
      lines[maxLines - 1] = (last.length > max - 1 ? last.slice(0, max - 1) : last).replace(/[\s,.;:]+$/, '') + '…';
    }
    return lines;
  }
  function andList(a) { return a.length < 2 ? a.join('') : a.slice(0, -1).join(', ') + ' and ' + a[a.length - 1]; }

  /* ---------- evidence map ---------- */
  function mapDocLabel(d) {
    if (d.source === 'web') return d.domain || d.title || 'Web page';
    return d.title || ((O.SOURCE_LABELS[d.source] || 'Source') + ' paper');
  }
  function mapModel(report) {
    var claims = [], docs = {};
    (report.claims || []).forEach(function (c, i) {
      var links = {}, ids = [];
      (c.evidence || []).forEach(function (e) {
        var id = docId(e.pid) || e.url || e.title || ('x' + i), l = links[id], d = docs[id];
        if (!l) { l = links[id] = { id: id, n: 0, sup: 0, con: 0 }; ids.push(id); }
        l.n++; if (e.relation === 'contradicts') l.con++; else l.sup++;
        if (!d) {
          d = docs[id] = { id: id, pid: e.pid, title: e.title || '', url: e.url, domain: domainOf(e.domain), source: SRC_ORDER.indexOf(e.source) < 0 ? 'web' : e.source, year: e.year, claims: [] };
          d.label = mapDocLabel(d);
        }
        if (d.claims.indexOf(i) < 0) d.claims.push(i);
      });
      var none = c.verdict === 'not_verified' || !ids.length;
      var linkedSites = {};
      ids.forEach(function (id) { linkedSites[docs[id].domain || id] = 1; });
      var nLinked = Object.keys(linkedSites).length;
      /* Only a backed claim counts independent supporting sites. A contradicted or mixed claim shows how many websites are linked to it. */
      var sites = c.verdict === 'supported' && O.isNum(c.independent_sources) ? c.independent_sources : nLinked;
      claims.push({ i: i, text: c.text || '', verdict: c.verdict, note: c.note, sites: sites, links: none ? {} : links, ids: none ? [] : ids,
        kind: none ? 'none' : (sites >= 2 ? 'solid' : 'single') });
    });
    /* A document that only backs not-verified claims never shows. */
    var shown = {};
    claims.forEach(function (c) { c.ids.forEach(function (id) { shown[id] = 1; }); });
    Object.keys(docs).forEach(function (id) { if (!shown[id]) delete docs[id]; else docs[id].claims = docs[id].claims.filter(function (i) { return claims[i].kind !== 'none'; }); });
    /* Two sources with the same name get their year (then a number) so they can be told apart. */
    var seenLbl = {};
    Object.keys(docs).forEach(function (id) {
      var d = docs[id], k = d.label.toLowerCase();
      if (seenLbl[k]) { d.suffix = d.year ? ' (' + d.year + ')' : ''; seenLbl[k].forEach(function (o) { if (!o.suffix && o.year) o.suffix = ' (' + o.year + ')'; }); seenLbl[k].push(d); }
      else { seenLbl[k] = [d]; d.suffix = ''; }
    });
    Object.keys(seenLbl).forEach(function (k) {
      var g = seenLbl[k]; if (g.length < 2) return;
      var used = {};
      g.forEach(function (d, n) { if (used[d.suffix] || !d.suffix) d.suffix = ' (' + (n + 1) + ')'; used[d.suffix] = 1; });
    });
    return { claims: claims, docs: docs };
  }
  function linkStance(l, c) { return l.con && l.con >= l.sup ? 'contradict' : (c.verdict === 'mixed' ? 'mixed' : 'support'); }
  function claimTag(c) {
    if (c.kind === 'none') return 'Not verified';
    return (VERDICT[c.verdict] || c.verdict) + ', ' + siteTag(c);
  }
  /* "single source" belongs to backed claims. For other verdicts say how many websites are linked. */
  function siteTag(c) {
    if (c.verdict === 'supported') return c.kind === 'solid' ? c.sites + ' websites' : 'single source';
    return c.sites === 1 ? 'one website' : c.sites + ' websites';
  }
  var VCLS = { supported: 'support', mixed: 'mixed', contradicted: 'contradict', not_verified: 'none' };

  O.evidenceMap = function (report, opts) {
    opts = opts || {};
    var m = mapModel(report || {});
    var host = h('div', { class: 'emap' });
    if (!m.claims.length) { host.append(h('p', { class: 'muted' }, 'No claims were extracted from this answer, so there is nothing to map.')); return host; }
    var nSolid = m.claims.filter(function (c) { return c.kind === 'solid'; }).length;
    var nSingle = m.claims.filter(function (c) { return c.kind === 'single'; }).length;
    var nNone = m.claims.filter(function (c) { return c.kind === 'none'; }).length;
    var summary = h('p', { class: 'emap-sum' }, O.plural(m.claims.length, 'claim') + ': ' + nSolid + ' linked to two or more websites, ' + nSingle + ' linked to one website, ' + nNone + ' not verified.');
    var body = h('div', { class: 'emap-body' });
    var readout = h('div', { class: 'emap-read', 'aria-live': 'polite' });
    var legend = h('p', { class: 'emap-legend' },
      h('span', { class: 'lg lg-support' }, 'Supports'), h('span', { class: 'lg lg-contradict' }, 'Contradicts'), h('span', { class: 'lg lg-mixed' }, 'Mixed'),
      h('span', { class: 'lg-txt' }, 'Thicker line: more passages. Bigger dot: backs more claims. Dashed: no source found.'));
    host.append(summary, body, readout, legend);

    function openSource(d) {
      if (opts.onSource && opts.onSource(d) !== false) return;
      var u = O.safeUrl(d.url); if (u) window.open(u, '_blank', 'noopener');
    }
    function claimReadout(c) {
      var names = c.ids.map(function (id) { return m.docs[id].label; });
      return h('div', null,
        h('div', { class: 'er-top' }, h('strong', null, 'Claim ' + (c.i + 1)), h('span', { class: 'er-tag vd-' + c.verdict }, claimTag(c))),
        h('p', { class: 'er-text' }, c.text),
        names.length ? h('p', { class: 'er-sub' }, 'Linked to ' + cut(andList(names.map(function (n) { return cut(n, 48); })), 260)) : h('p', { class: 'er-sub' }, 'No source we found covers this claim. That does not make it false.'));
    }
    function sourceReadout(d) {
      var where = (d.source === 'web' ? d.domain : (O.SOURCE_LABELS[d.source] || '')) + (d.year ? ', ' + d.year : '');
      return h('div', null,
        h('div', { class: 'er-top' }, h('strong', null, cut(d.title || d.label, 120))),
        h('p', { class: 'er-sub' }, where),
        h('p', { class: 'er-sub' }, 'Backs ' + (d.claims.length === 1 ? 'claim ' : 'claims ') + andList(d.claims.map(function (i) { return String(i + 1); })) + '. Click to read the passage.'));
    }
    var idle = h('p', { class: 'er-idle' }, 'Hover or focus a claim to see its sources. Click a source to read the passage.');
    O.clear(readout).append(idle);

    /* ----- graph (wide) ----- */
    function drawGraph(W) {
      var pin = null, claimEls = {}, linkEls = [], srcEls = {};
      var colL = Math.round(W * 0.39), nodeX = Math.round(W * 0.66), nodeCx = nodeX + 14;
      var claimChars = Math.floor((colL - 40) / 6.5), srcChars = Math.floor((W - nodeCx - 22) / 6.4);
      var rowH = 76, srcH = 30, hdrH = 34;
      var groups = [];
      SRC_ORDER.forEach(function (k) {
        var ds = Object.keys(m.docs).map(function (id) { return m.docs[id]; }).filter(function (d) { return d.source === k; });
        if (ds.length) groups.push({ k: k, docs: ds });
      });
      groups.forEach(function (g) {
        g.docs.forEach(function (d) { d.bary = d.claims.reduce(function (a, b) { return a + b; }, 0) / d.claims.length; });
        g.docs.sort(function (a, b) { return a.bary - b.bary; });
        g.bary = g.docs.reduce(function (a, d) { return a + d.bary; }, 0) / g.docs.length;
      });
      groups.sort(function (a, b) { return a.bary - b.bary; });
      var nDocs = 0; groups.forEach(function (g) { nDocs += g.docs.length; });
      var Hs = groups.length * hdrH + nDocs * srcH, Hc = m.claims.length * rowH, pad = 6;
      var H = Math.max(Hs, Hc) + pad * 2;
      var fs = (H - pad * 2) / Hs;
      var svg = sv('svg', { viewBox: '0 0 ' + W + ' ' + H, width: W, height: H, class: 'emap-svg', role: 'group', 'aria-label': 'Evidence map: claims on the left, the sources that back them on the right.' });
      var gLinks = sv('g', { class: 'emap-links' }), gSrc = sv('g'), gCl = sv('g');
      svg.append(gLinks, gSrc, gCl);

      var srcY = {}, y = pad;
      groups.forEach(function (g) {
        var gy = y + (hdrH * fs) * 0.62;
        gSrc.append(sv('text', { x: nodeX, y: gy, class: 'emap-gh' }, (O.SOURCE_LABELS[g.k] || g.k).toUpperCase()),
          sv('line', { x1: nodeX, x2: W, y1: gy + 7, y2: gy + 7, class: 'emap-rule' }));
        y += hdrH * fs;
        g.docs.forEach(function (d) { srcY[d.id] = y + srcH * fs / 2 + 2; y += srcH * fs; });
      });

      m.claims.forEach(function (c) {
        var cy = pad + (c.i + 0.5) * (H - pad * 2) / m.claims.length;
        c.cy = cy;
        var vc = VCLS[c.verdict] || 'none';
        var lines = wrapLines(c.text, claimChars, 3), blockH = lines.length * 16 + 18, top = cy - blockH / 2;
        var tag = c.kind === 'none' ? 'Not verified' : (VERDICT[c.verdict] || c.verdict) + ' · ' + siteTag(c);
        var g = sv('g', { class: 'emap-claim k-' + c.kind + ' c-' + vc, tabindex: 0, role: 'button', 'aria-pressed': 'false', 'aria-label': 'Claim ' + (c.i + 1) + ', ' + claimTag(c) + '. ' + c.text });
        g.append(sv('rect', { x: -4, y: cy - rowH / 2 + 3, width: colL + 4, height: rowH - 6, rx: 8, class: 'emap-claim-box' }),
          sv('circle', { cx: 14, cy: top + 9, r: 11, class: 'emap-mark' }),
          sv('text', { x: 14, y: top + 13.2, class: 'emap-num', 'text-anchor': 'middle' }, String(c.i + 1)));
        var t = sv('text', { x: 34, y: top + 13, class: 'emap-ct' });
        lines.forEach(function (ln, j) { t.append(sv('tspan', { x: 34, dy: j ? 16 : 0 }, j < lines.length - 1 ? ln + ' ' : ln)); });
        g.append(t, sv('text', { x: 34, y: top + 13 + lines.length * 16 + 1, class: 'emap-meta' }, tag));
        gCl.append(g);
        claimEls[c.i] = g;
        g.addEventListener('mouseenter', function () { focus('claim', c.i); });
        g.addEventListener('mouseleave', function () { focus(pin && pin.k, pin && pin.v); });
        g.addEventListener('focus', function () { focus('claim', c.i); });
        g.addEventListener('blur', function () { focus(pin && pin.k, pin && pin.v); });
        function toggle() {
          pin = pin && pin.k === 'claim' && pin.v === c.i ? null : { k: 'claim', v: c.i };
          O.$$('.emap-claim', svg).forEach(function (el) { el.setAttribute('aria-pressed', 'false'); });
          if (pin) g.setAttribute('aria-pressed', 'true');
          focus(pin ? 'claim' : null, c.i);
        }
        g.addEventListener('click', toggle);
        g.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(); } });
      });

      m.claims.forEach(function (c) {
        c.ids.forEach(function (id) {
          var l = c.links[id], d = m.docs[id], r = Math.min(14, 5 + 2.5 * d.claims.length);
          var x1 = colL + 4, y1 = c.cy, x2 = nodeCx - r - 2, y2 = srcY[id], mx = (x1 + x2) / 2;
          var p = sv('path', { d: 'M' + x1 + ' ' + y1 + ' C' + mx + ' ' + y1 + ' ' + mx + ' ' + y2 + ' ' + x2 + ' ' + y2, class: 'emap-link s-' + linkStance(l, c), 'stroke-width': (1.2 + Math.min(l.n, 4) * 0.8).toFixed(1) });
          p.append(sv('title', {}, 'Claim ' + (c.i + 1) + ' and ' + d.label + ': ' + O.plural(l.n, 'passage')));
          gLinks.append(p);
          linkEls.push({ el: p, ci: c.i, id: id });
        });
      });

      Object.keys(m.docs).forEach(function (id) {
        var d = m.docs[id], r = Math.min(14, 5 + 2.5 * d.claims.length), cy = srcY[id];
        var g = sv('g', { class: 'emap-src', tabindex: 0, role: 'link', 'aria-label': d.label + ', backs ' + O.plural(d.claims.length, 'claim') + '. Open in the sources list.' });
        g.append(sv('rect', { x: nodeX - 4, y: cy - srcH / 2, width: W - nodeX + 4, height: srcH, rx: 6, class: 'emap-src-hit' }),
          sv('circle', { cx: nodeCx, cy: cy, r: r, class: 'emap-node' }));
        if (d.claims.length > 1) g.append(sv('text', { x: nodeCx, y: cy + 4, class: 'emap-nn', 'text-anchor': 'middle' }, String(d.claims.length)));
        g.append(sv('text', { x: nodeCx + 14 + 8, y: cy + 4.5, class: 'emap-st' }, cut(d.label, srcChars - (d.suffix || '').length) + (d.suffix || '')));
        gSrc.append(g);
        srcEls[id] = g;
        g.addEventListener('mouseenter', function () { focus('src', id); });
        g.addEventListener('mouseleave', function () { focus(pin && pin.k, pin && pin.v); });
        g.addEventListener('focus', function () { focus('src', id); });
        g.addEventListener('blur', function () { focus(pin && pin.k, pin && pin.v); });
        g.addEventListener('click', function () { openSource(d); });
        g.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openSource(d); } });
      });

      function focus(kind, key) {
        svg.classList.toggle('has-focus', !!kind);
        m.claims.forEach(function (c) {
          var on = kind === 'claim' ? key === c.i : kind === 'src' ? c.links[key] : false;
          claimEls[c.i].classList.toggle('is-on', !!on);
        });
        linkEls.forEach(function (l) { l.el.classList.toggle('is-on', kind === 'claim' ? l.ci === key : kind === 'src' ? l.id === key : false); });
        Object.keys(srcEls).forEach(function (id) {
          var on = kind === 'src' ? id === key : kind === 'claim' ? m.claims[key].links[id] : false;
          srcEls[id].classList.toggle('is-on', !!on);
        });
        O.clear(readout);
        if (kind === 'claim') readout.append(claimReadout(m.claims[key]));
        else if (kind === 'src') readout.append(sourceReadout(m.docs[key]));
        else readout.append(idle);
      }
      return svg;
    }

    /* ----- stacked (phones) ----- */
    function drawStack() {
      return h('div', { class: 'emap-stack' }, m.claims.map(function (c) {
        var vc = VCLS[c.verdict] || 'none';
        var srcs = c.ids.map(function (id) {
          var d = m.docs[id], l = c.links[id];
          return h('li', null, h('button', { type: 'button', class: 'es-src', onclick: function () { openSource(d); } },
            h('span', { class: 'es-dot s-' + linkStance(l, c), 'aria-hidden': 'true' }),
            h('span', { class: 'es-name' }, cut(d.label, 70 - (d.suffix || '').length) + (d.suffix || '')),
            h('span', { class: 'es-kind' }, O.SOURCE_LABELS[d.source] + (l.n > 1 ? ', ' + l.n + ' passages' : ''))));
        });
        return h('article', { class: 'es-card k-' + c.kind + ' c-' + vc },
          h('div', { class: 'es-top' }, h('span', { class: 'es-n' }, String(c.i + 1)), h('span', { class: 'er-tag vd-' + c.verdict }, claimTag(c))),
          h('p', { class: 'es-text' }, c.text),
          srcs.length ? h('ul', { class: 'es-list' }, srcs) : h('p', { class: 'es-none' }, 'No source we found covers this claim. That does not make it false.'));
      }));
    }

    var lastMode = null, lastW = 0;
    function draw() {
      var W = Math.min(host.clientWidth || 0, 760);
      if (!W) return;
      var mode = W >= 600 ? 'graph' : 'stack';
      if (mode === lastMode && Math.abs(W - lastW) < 4) return;
      lastMode = mode; lastW = W;
      host.classList.toggle('is-stack', mode === 'stack');
      O.clear(body).append(mode === 'graph' ? drawGraph(W) : drawStack());
      readout.hidden = legend.hidden = mode === 'stack';
      if (mode === 'graph') O.clear(readout).append(idle);
    }
    O.watchResize(host, draw);
    return host;
  };

  /* ---------- belief journey ---------- */
  var ORIGIN_TAG = { question: 'your question', model: 'own search', counter: 'counter-search' };
  var ORIGIN_TAG_SM = { question: 'question', model: 'own', counter: 'counter' };
  O.beliefJourney = function (initial) {
    var model = initial || { rounds: [], threshold: 0.05 };
    var host = h('div', { class: 'bj', hidden: true });
    var chart = h('div', { class: 'bj-chart' }), notes = h('div', { class: 'bj-notes' }), beliefs = h('div', { class: 'bj-beliefs' });
    host.append(h('div', { class: 'bj-head' }, h('h3', { class: 'bj-title' }, 'Belief journey'),
      h('p', { class: 'bj-sub' }, 'How the agent’s belief and its searches moved round by round, and where the balance check stepped in.')), chart, notes, beliefs);

    function draw() {
      var rounds = (model.rounds || []).filter(Boolean).sort(function (a, b) { return a.hop - b.hop; });
      host.hidden = !rounds.length;
      if (!rounds.length) return;
      var thr = O.isNum(model.threshold) ? model.threshold : 0.05;
      var W = Math.min(host.clientWidth || 0, 760);
      O.clear(chart); O.clear(notes);
      if (W >= 240) chart.append(drawChart(rounds, W, thr));
      var hasNull = rounds.some(function (r) { return r.hop === 1 && r.measured && !O.isNum(r.baqd); });
      if (rounds.some(function (r) { return r.cqi; })) notes.append(h('p', { class: 'bj-keyrow' }, h('span', { class: 'bj-key bj-key-guard', 'aria-hidden': 'true' }), h('span', null, 'Diamond: the balance check stepped in and swapped the next search for one that looks at the other side.')));
      var neg = rounds.some(function (r) { return O.isNum(r.baqd) && r.baqd < 0; });
      notes.append(h('p', { class: 'bj-def' }, 'BAQD is belief-aligned query drift: how much more closely a new search follows the agent’s earlier belief than your original question did. Above ' + thr + ' counts as drift.' +
        (neg ? ' A negative value means the search was less aligned with the belief than your question was.' : '') +
        (hasNull ? ' Round 1 has nothing to compare with, so it is left blank, not set to zero.' : '') + ' Neutral passages are not drawn.'));
      O.clear(beliefs).append(h('ol', { class: 'bj-list' }, rounds.filter(function (r) { return r.belief; }).map(function (r) {
        var b = h('button', { type: 'button', class: 'bj-line', 'aria-expanded': 'false', onclick: function () {
          var o = b.getAttribute('aria-expanded') !== 'true'; b.setAttribute('aria-expanded', o ? 'true' : 'false');
        } }, h('span', { class: 'bj-r' }, 'Round ' + r.hop + ':'), h('span', { class: 'bj-t' }, r.belief));
        return h('li', null, b);
      })));
    }

    function drawChart(rounds, W, thr) {
      var wide = W >= 560, G = wide ? 128 : 0, cap = wide ? 0 : 18, n = rounds.length;
      var plotW = W - G - 6, colW = Math.min(plotW / n, 150);
      var x0 = G + (plotW - colW * n) / 2 + colW / 2;
      function cx(i) { return x0 + i * colW; }
      var hasNeg = rounds.some(function (r) { return O.isNum(r.baqd) && r.baqd < 0; });
      var yHdr = 0, yB = 46 + cap, hB = hasNeg ? 124 : 92, yG = yB + hB + 12 + cap, hG = 22, yV = yG + hG + 10 + cap, hV = 76, yC = yV + hV + 8 + cap;
      var H = yC + 22;
      var svg = sv('svg', { viewBox: '0 0 ' + W + ' ' + H, width: W, height: H, class: 'bj-svg', role: 'img',
        'aria-label': 'Belief journey over ' + O.plural(n, 'round') + ': drift value, balance of passages, balance check actions and stated confidence for each round.' });
      function rowLabel(y, a, b) {
        if (wide) { svg.append(sv('text', { x: 0, y: y + 14, class: 'bj-rl' }, a)); if (b) svg.append(sv('text', { x: 0, y: y + 29, class: 'bj-rs' }, b)); }
        else svg.append(sv('text', { x: 0, y: y - 6, class: 'bj-rl' }, a + (b ? ' ' + b : '')));
      }
      /* headers */
      rounds.forEach(function (r, i) {
        svg.append(sv('text', { x: cx(i), y: 14, class: 'bj-hd', 'text-anchor': 'middle' }, (wide ? 'Round ' : 'R') + r.hop));
        var tag = (wide ? ORIGIN_TAG : ORIGIN_TAG_SM)[r.origin] || '';
        svg.append(sv('text', { x: cx(i), y: 30, class: 'bj-tag' + (r.origin === 'counter' ? ' is-counter' : ''), 'text-anchor': 'middle' }, tag));
      });
      /* drift row */
      var vals = rounds.map(function (r) { return r.baqd; }).filter(O.isNum);
      var yMax = Math.max(thr * 1.6, (vals.length ? Math.max.apply(null, vals) : 0) * 1.25);
      var yMin = hasNeg ? Math.min.apply(null, vals) * 1.25 : 0;
      var inT = yB + 24, inB = yB + hB - 6;
      function yy(v) { return inB - ((v - yMin) / (yMax - yMin)) * (inB - inT); }
      rowLabel(yB, 'Drift (BAQD)', 'up is toward the belief');
      svg.append(sv('rect', { x: G, y: yB, width: W - G, height: yy(thr) - yB, class: 'bj-zone' }),
        sv('line', { x1: G, x2: W, y1: yy(thr), y2: yy(thr), class: 'bj-thr' }),
        sv('text', { x: G + 6, y: yB + 14, class: 'bj-zt', 'text-anchor': 'start' }, 'Above ' + thr + ' counts as drift'),
        sv('line', { x1: G, x2: W, y1: yy(0), y2: yy(0), class: 'bj-axis' }),
        sv('text', { x: G - 6, y: yy(0) + 3.5, class: 'bj-tick', 'text-anchor': 'end' }, '0'));
      var d = '', pen = false;
      rounds.forEach(function (r, i) {
        if (O.isNum(r.baqd)) { d += (pen ? 'L' : 'M') + cx(i).toFixed(1) + ' ' + yy(r.baqd).toFixed(1) + ' '; pen = true; } else pen = false;
      });
      if (d) svg.append(sv('path', { d: d, class: 'bj-line-path' }));
      rounds.forEach(function (r, i) {
        if (O.isNum(r.baqd)) {
          var py = yy(r.baqd);
          var c = sv('circle', { cx: cx(i), cy: py, r: 4.5, class: 'bj-pt' + (r.baqd > thr ? ' is-over' : '') });
          c.append(sv('title', {}, 'Round ' + r.hop + ': drift ' + r.baqd.toFixed(3)));
          var pv = rounds[i - 1] && O.isNum(rounds[i - 1].baqd) ? rounds[i - 1].baqd : null, nv = rounds[i + 1] && O.isNum(rounds[i + 1].baqd) ? rounds[i + 1].baqd : null;
          var nb = (pv != null && nv != null) ? (pv + nv) / 2 : (pv != null ? pv : nv);
          var below = nb != null && nb > r.baqd;
          var ly = below ? py + 17 : py - 10;
          if (ly > inB + 6) ly = py - 10;
          if (ly < yB + 10) ly = py + 17;
          svg.append(c, sv('text', { x: cx(i), y: ly, class: 'bj-val', 'text-anchor': 'middle' }, r.baqd.toFixed(3)));
        } else if (r.measured) {
          var ny = yy(0) - 8;
          [yy(0) - 8, yy(0) + 13, yy(0) - 24].some(function (cand) { ny = cand; return Math.abs(cand - 4 - yy(thr)) > 10 && cand < inB + 12; });
          svg.append(sv('text', { x: cx(i), y: ny, class: 'bj-na', 'text-anchor': 'middle' }, wide ? 'not measured' : 'n/a'));
        }
      });
      /* guard row */
      rowLabel(yG, 'Balance check', null);
      svg.append(sv('line', { x1: G, x2: W, y1: yG + hG / 2, y2: yG + hG / 2, class: 'bj-axis' }));
      rounds.forEach(function (r, i) {
        if (!r.cqi) return;
        var gy = yG + hG / 2, why = [];
        if (r.cqi.trigger && O.isNum(r.cqi.trigger.baqd) && r.cqi.trigger.baqd > thr) why.push('drift above ' + thr);
        if (r.cqi.trigger && O.isNum(r.cqi.trigger.skew) && Math.abs(r.cqi.trigger.skew) >= 0.5) why.push('evidence leaning one way');
        var g = sv('g', {});
        g.append(sv('path', { d: 'M' + cx(i) + ' ' + (gy - 8) + ' L' + (cx(i) + 8) + ' ' + gy + ' L' + cx(i) + ' ' + (gy + 8) + ' L' + (cx(i) - 8) + ' ' + gy + ' Z', class: 'bj-dia' }),
          sv('title', {}, 'After round ' + r.hop + ' the balance check added a counter-search' + (why.length ? ' because of ' + why.join(' and ') : '')));
        svg.append(g);
        if (wide && colW > 90) svg.append(sv('text', { x: cx(i) + 14, y: gy + 4.5, class: 'bj-gt' }, 'stepped in'));
      });
      /* balance row */
      rowLabel(yV, 'Evidence balance', 'agree up, against down');
      var zero = yV + hV / 2, half = hV / 2 - 14;
      var mx = Math.max(1, Math.max.apply(null, rounds.map(function (r) { return Math.max(r.support || 0, r.contradict || 0); })));
      svg.append(sv('line', { x1: G, x2: W, y1: zero, y2: zero, class: 'bj-axis' }));
      var bw = Math.min(18, colW * 0.34);
      rounds.forEach(function (r, i) {
        if (!r.measured) return;
        var s = r.support || 0, k = r.contradict || 0;
        if (s) svg.append(sv('rect', { x: cx(i) - bw / 2, y: zero - (s / mx) * half, width: bw, height: (s / mx) * half, class: 'bj-bar-s' }));
        if (k) svg.append(sv('rect', { x: cx(i) - bw / 2, y: zero, width: bw, height: (k / mx) * half, class: 'bj-bar-c' }));
        svg.append(sv('text', { x: cx(i), y: zero - (s / mx) * half - 4, class: 'bj-val bj-cs' }, String(s)));
        svg.append(sv('text', { x: cx(i), y: zero + (k / mx) * half + 14, class: 'bj-val bj-cc' }, String(k)));
      });
      /* confidence row */
      rowLabel(yC - 4, 'Confidence', null);
      rounds.forEach(function (r, i) {
        svg.append(sv('text', { x: cx(i), y: yC + 12, class: 'bj-conf', 'text-anchor': 'middle' }, O.isNum(r.confidence) ? Math.round(r.confidence) + '%' : 'n/a'));
      });
      return svg;
    }

    O.watchResize(host, draw);
    host.update = function (m) { model = m; draw(); };
    draw();
    return host;
  };

  /* ---------- how this answer was made ---------- */
  var COMPARE_ROWS = [
    { q: 'Looks up live sources', a: ['part', 'Sometimes'], b: ['yes', 'Yes'], c: function () { return ['yes', 'Yes']; } },
    { q: 'Searches several kinds of sources', a: ['no', 'No'], b: ['part', 'Usually one'], c: function (x) { return ['yes', x.fetchedTypes ? x.fetchedTypes + ' of 5 kinds here' : '5 kinds']; } },
    { q: 'Writes its own follow-up searches', a: ['no', 'No'], b: ['no', 'No'], c: function (x) { return x.own ? ['yes', x.own + (x.own === 1 ? ' search' : ' searches') + ' of its own here' + (x.counter ? ', ' + x.counter + ' by the balance check' : '')] : ['part', 'None of its own here']; } },
    { q: 'Checks itself for one-sided searching', a: ['no', 'No'], b: ['no', 'No'], c: function (x) { return x.guarded ? ['yes', 'After each round'] : ['no', 'Off in this run']; } },
    { q: 'Searches the other side when it drifts', a: ['no', 'No'], b: ['no', 'No'], c: function (x) { return !x.guarded ? ['no', 'Not used in this run'] : ['yes', x.counter ? O.plural(x.counter, 'time') + ' here' : 'Not needed here']; } },
    { q: 'Cites the exact passage', a: ['no', 'No'], b: ['part', 'Often a page'], c: function () { return ['yes', 'Yes']; } },
    { q: 'Checks every claim against the evidence', a: ['no', 'No'], b: ['no', 'No'], c: function (x) { return ['yes', O.plural(x.claims.n, 'claim') + ' here']; } },
    { q: 'Says when a claim is not verified', a: ['no', 'No'], b: ['part', 'Rarely'], c: function (x) { return ['yes', x.claims.not_verified ? x.claims.not_verified + ' flagged here' : 'None to flag here']; } }
  ];
  function mark(kind, text) {
    var ic = kind === 'yes' ? O.icon('check', 16) : h('span', { class: 'xr-dash', 'aria-hidden': 'true' });
    return h('span', { class: 'xr-mark is-' + kind }, ic, h('span', { class: 'xr-mt' }, text));
  }

  var xrOpen = null;
  O.answerXray = function (x, opener) {
    if (xrOpen) xrOpen.close();
    var prevFocus = opener || document.activeElement, prevOverflow = document.body.style.overflow;
    var tid = 'xr-title-' + Math.random().toString(36).slice(2, 6);

    function stage(label, big, cap) {
      return h('li', { class: 'xr-stage' }, h('span', { class: 'xr-sl' }, label),
        big == null ? null : h('span', { class: 'xr-big' }, String(big)), h('span', { class: 'xr-cap' }, cap));
    }
    var cl = x.claims, verdictBits = [];
    if (cl.supported) verdictBits.push(cl.supported + ' backed');
    if (cl.mixed) verdictBits.push(cl.mixed + ' mixed');
    if (cl.contradicted) verdictBits.push(cl.contradicted + ' contradicted');
    if (cl.not_verified) verdictBits.push(cl.not_verified + ' not verified');
    var strip = h('ol', { class: 'xr-pipe' },
      stage('Question', null, '“' + cut(x.question, 74) + '”'),
      stage('Searched', x.searches, (x.searches === 1 ? 'search' : 'searches') + (x.counter ? ', ' + x.counter + ' of them added by the balance check' : ', none added by the balance check')),
      stage('Fetched', x.fetchedTotal, 'documents from ' + O.plural(x.fetchedTypes, 'source type')),
      stage('Ranked', x.pool, O.isNum(x.pool) ? 'passages ranked and kept in the evidence pool' : 'passages in the evidence pool'),
      stage('Read', x.read, 'passages the agent read, from ' + O.plural(x.sites, 'website')),
      stage('Checked', cl.n, (cl.n === 1 ? 'claim' : 'claims') + ' checked' + (verdictBits.length ? ', ' + verdictBits.join(', ') : '')));
    var fmax = Math.max(1, Math.max.apply(null, SRC_ORDER.map(function (k) { return x.fetched[k] || 0; })));
    var bars = h('div', { class: 'xr-bars' }, SRC_ORDER.map(function (k) {
      var v = x.fetched[k] || 0;
      return h('div', { class: 'xr-bar' }, h('span', { class: 'xr-bl' }, O.SOURCE_LABELS[k]),
        h('span', { class: 'xr-bt' }, h('span', { class: 'xr-bf', style: 'width:' + (v / fmax * 100) + '%' })), h('span', { class: 'xr-bv' }, String(v)));
    }));
    var timeTxt = !O.isNum(x.seconds) ? null : x.seconds < 1 ? 'Opened from saved work, so no new time was spent.' : 'This research took ' + (x.seconds >= 90 ? O.plural(Math.round(x.seconds / 60), 'minute') : O.plural(Math.round(x.seconds), 'second')) + '.';

    var rows = COMPARE_ROWS.map(function (r) {
      var a = r.a, b = r.b, c = r.c(x);
      return h('div', { class: 'xr-row', role: 'row' },
        h('div', { class: 'xr-q', role: 'rowheader' }, r.q),
        h('div', { class: 'xr-cell', role: 'cell' }, h('span', { class: 'xr-cc' }, 'Typical chatbot'), mark(a[0], a[1])),
        h('div', { class: 'xr-cell', role: 'cell' }, h('span', { class: 'xr-cc' }, 'Typical RAG search'), mark(b[0], b[1])),
        h('div', { class: 'xr-cell xr-us', role: 'cell' }, h('span', { class: 'xr-cc' }, 'Ouroboros'), mark(c[0], c[1])));
    });
    var table = h('div', { class: 'xr-table', role: 'table', 'aria-label': 'Comparison of a typical chatbot, a typical RAG search and Ouroboros' },
      h('div', { class: 'xr-row xr-hd', role: 'row' }, h('div', { role: 'columnheader' }, h('span', { class: 'sr' }, 'Feature')), h('div', { role: 'columnheader' }, 'Typical chatbot'), h('div', { role: 'columnheader' }, 'Typical RAG search'), h('div', { role: 'columnheader', class: 'xr-us' }, 'Ouroboros')),
      rows);

    var closeBtn = h('button', { type: 'button', class: 'xr-close btn-icon', 'aria-label': 'Close' }, O.icon('close', 20));
    var panel = h('aside', { class: 'xr-panel', role: 'dialog', 'aria-modal': 'true', 'aria-labelledby': tid, tabindex: '-1' },
      h('header', { class: 'xr-head' }, h('h2', { id: tid }, 'How this answer was made'), closeBtn),
      h('div', { class: 'xr-scroll', tabindex: '0', role: 'region', 'aria-label': 'How this answer was made, details' },
        h('p', { class: 'xr-lead' }, 'The counts below are from this research. Nothing here is an estimate.'),
        strip, bars, SRC_ORDER.some(function (k) { return !x.fetched[k]; }) ? h('p', { class: 'xr-time' }, 'A source showing 0 returned no documents for this question, or did not answer in time.') : null, timeTxt ? h('p', { class: 'xr-time' }, timeTxt) : null,
        h('section', { class: 'xr-sec' },
          h('h3', null, 'What makes this different'),
          h('p', { class: 'xr-note' }, 'Typical systems vary. These columns describe common designs, not any one product.'),
          table),
        h('p', { class: 'xr-foot' }, 'The Evidence Support Score is the share of the answer’s claims backed by the evidence we retrieved. It is not the chance the answer is true, and not verified never means false.')));
    var root = h('div', { class: 'xr-root' }, h('div', { class: 'xr-scrim' }), panel);
    root.firstChild.addEventListener('click', close);
    closeBtn.addEventListener('click', close);

    function focusables() {
      return O.$$('button, [href], input, [tabindex]:not([tabindex="-1"])', panel).filter(function (e) { return !e.disabled && e.offsetParent !== null; });
    }
    function onKey(e) {
      if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); close(); return; }
      if (e.key !== 'Tab') return;
      var f = focusables(); if (!f.length) { e.preventDefault(); return; }
      var first = f[0], last = f[f.length - 1];
      if (!panel.contains(document.activeElement)) { e.preventDefault(); first.focus(); }
      else if (e.shiftKey && (document.activeElement === first || document.activeElement === panel)) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
    function close() {
      document.removeEventListener('keydown', onKey, true);
      window.removeEventListener('hashchange', close);
      document.body.style.overflow = prevOverflow;
      root.classList.remove('is-in');
      var gone = function () { root.remove(); };
      if (O.REDUCED) gone(); else setTimeout(gone, 180);
      xrOpen = null;
      if (prevFocus && prevFocus.focus && document.contains(prevFocus)) prevFocus.focus();
    }
    document.body.append(root);
    document.body.style.overflow = 'hidden';
    document.addEventListener('keydown', onKey, true);
    window.addEventListener('hashchange', close, { once: true });
    requestAnimationFrame(function () { root.classList.add('is-in'); panel.focus(); });
    xrOpen = { close: close };
    return xrOpen;
  };

  /* ====================================================================== Turn */
  function Turn(thread, o) {
    this.thread = thread;
    this.question = o.question;
    this.guarded = o.guarded !== false;
    this.hopsPlanned = o.hops || 4;
    this.prev = o.prev || null;
    this.first = !!o.first;
    this.cites = new O.Citations();
    this.hops = {};
    this.hopCount = 0;
    this.runId = null;
    this.report = null;
    this.answered = false;
    this.finished = false;
    this.stream = null;
    this.rounds = {};
    this.readPids = {};
    this.cfg = {};
    this.seconds = null;
    this.build();
  }

  Turn.prototype.build = function () {
    var self = this;
    this.steps = O.steps(STEP_LABELS);
    this.steps.el.hidden = true;
    this.roundEl = h('span', { class: 'turn-round' });
    this.liveEl = h('span', { class: 'turn-live', 'aria-live': 'polite' });
    this.progress = h('div', { class: 'turn-progress' }, this.steps.el, O.spinner(), this.roundEl, this.liveEl);

    this.rewriteEl = h('p', { class: 'turn-rewrite', hidden: true });
    this.head = h('header', { class: 'turn-head' },
      h(this.first ? 'h1' : 'h2', { class: 'turn-q' }, this.question), this.rewriteEl);

    this.errorHost = h('div', { class: 'turn-error-host' });
    this.answerHost = h('div', { class: 'turn-answer' }, this.answerSkeleton());
    this.confHost = h('div', { class: 'turn-conf' });
    this.evidenceHost = h('div', { class: 'turn-evidence' }, this.evidenceSkeleton());

    this.sourcesList = h('div', { class: 'passage-list' });
    this.stepsHost = h('ol', { class: 'hop-list' });
    this.journey = O.beliefJourney({ rounds: [], threshold: 0.05 });
    this.stepsPanel = h('div', { class: 'turn-path' }, this.journey, this.stepsHost);
    this.mapHost = h('div', { class: 'turn-map' }, h('p', { class: 'muted' }, 'The evidence map appears when the claim check at the end of the research finishes.'));
    this.reportHost = h('div', { class: 'turn-report' }, h('p', { class: 'muted' }, 'The claim by claim report appears when the check at the end of the research finishes.'));

    this.tabs = O.tabs({
      tabs: [{ id: 'sources', label: 'Sources', count: 0 }, { id: 'map', label: tabLabel('Evidence map', 'Map') }, { id: 'steps', label: tabLabel('Research path', 'Path'), count: 0 }, { id: 'report', label: tabLabel('Evidence report', 'Report') }],
      panels: { sources: this.sourcesList, map: this.mapHost, steps: this.stepsPanel, report: this.reportHost }
    });
    this.tabs.classList.add('turn-tabs');

    this.el = h('section', { class: 'turn' + (this.first ? ' is-first' : '') },
      this.head, this.progress, this.errorHost, this.answerHost, this.confHost, this.evidenceHost, this.tabs);

    /* A citation jumps to the source row of THIS turn, so repeated documents in later turns do not scroll away. */
    this.cites.onJump = function (pid) {
      self.tabs.select('sources');
      var el = O.$('.passage[data-pid="' + pid + '"]', self.el);
      if (!el) return true;
      if (el.setOpen) el.setOpen(true);
      el.scrollIntoView({ block: 'center', behavior: O.REDUCED ? 'auto' : 'smooth' });
      el.classList.remove('flash'); void el.offsetWidth; el.classList.add('flash');
      return true;
    };
  };

  /* ---------- skeletons ---------- */
  Turn.prototype.answerSkeleton = function () {
    return h('div', { class: 'ans-skel', 'aria-hidden': 'true' },
      h('div', { class: 'skeleton sk-line', style: 'width:96%' }), h('div', { class: 'skeleton sk-line', style: 'width:88%' }),
      h('div', { class: 'skeleton sk-line', style: 'width:93%' }), h('div', { class: 'skeleton sk-line', style: 'width:52%' }));
  };
  Turn.prototype.evidenceSkeleton = function () {
    return h('div', { class: 'ev ev-skel', 'aria-hidden': 'true' },
      h('div', { class: 'ev-main' }, h('div', { class: 'skeleton sk-ring' }),
        h('div', { class: 'grow' }, h('div', { class: 'skeleton sk-line', style: 'width:40%' }), h('div', { class: 'skeleton sk-line', style: 'width:62%' }))));
  };

  /* ---------- event handling ---------- */
  Turn.prototype.handle = function (ev) {
    var fn = this['on_' + ev.type];
    if (fn) fn.call(this, ev);
  };

  Turn.prototype.on_start = function (ev) {
    if (ev.config && ev.config.hops) this.hopsPlanned = ev.config.hops;
    this.cfg = ev.config || {};
    if (ev.mode) this.guarded = ev.mode === 'guarded';
    this.steps.activate(0);
  };

  Turn.prototype.on_rewrite = function (ev) {
    if (!ev.question || ev.question === this.question) return;
    this.rewriteEl.hidden = false;
    O.clear(this.rewriteEl).append('Searching for: ', h('em', null, ev.question));
  };

  Turn.prototype.setLive = function (text) { this.liveEl.textContent = text || ''; };

  Turn.prototype.on_hop_query = function (ev) {
    var origin = ev.origin || 'model';
    this.hopCount = Math.max(this.hopCount, ev.hop);
    this.steps.activate(0);
    this.roundEl.textContent = 'Round ' + ev.hop + ' of ' + this.hopsPlanned;
    this.setLive('Searching: ' + ev.query);

    this.rounds[ev.hop] = { hop: ev.hop, origin: origin, query: ev.query };
    this.updateJourney();
    var card = this.hopCard(ev.hop, origin, ev.query);
    this.hops[ev.hop] = card;
    this.stepsHost.append(card.li);
    this.tabs.setCount('steps', Object.keys(this.hops).length);
  };

  var ORIGIN = { question: 'Your question', model: 'Agent’s own search', counter: 'Counter-search' };
  Turn.prototype.hopCard = function (n, origin, query) {
    var sources = h('p', { class: 'hop-sources' }, 'Searching sources');
    var body = h('div', { class: 'hop-body' }, h('p', { class: 'hop-wait' }, O.spinner(), 'Reading what came back'));
    var li = h('li', { class: 'hop' + (origin === 'counter' ? ' is-counter' : '') },
      h('div', { class: 'hop-head' }, h('span', { class: 'hop-num' }, 'Hop ' + n), h('span', { class: 'hop-origin' }, ORIGIN[origin] || origin)),
      h('code', { class: 'hop-query' }, query),
      sources, body);
    return { li: li, sources: sources, body: body, origin: origin, metrics: null, banner: null };
  };

  Turn.prototype.on_hop_sources = function (ev) {
    var c = this.hops[ev.hop]; if (!c) return;
    var f = ev.fetched || {}, parts = [];
    Object.keys(O.SOURCE_LABELS).forEach(function (k) { if (O.isNum(f[k])) parts.push(O.SOURCE_LABELS[k] + ' ' + f[k]); });
    var text = parts.join(', ');
    if (O.isNum(ev.pool_size)) text += (text ? ', ' : '') + ev.pool_size + ' candidates ranked';
    c.sources.textContent = text || 'Sources searched';
    if (this.rounds[ev.hop]) { this.rounds[ev.hop].fetched = f; this.rounds[ev.hop].pool = ev.pool_size; }
    this.setLive('Ranking what came back from the sources');
  };

  Turn.prototype.on_hop_read = function (ev) {
    var c = this.hops[ev.hop]; if (!c) return;
    this.steps.activate(1);
    var self = this, ps = ev.passages || [];
    if (this.rounds[ev.hop]) { this.rounds[ev.hop].belief = ev.belief; this.rounds[ev.hop].confidence = ev.confidence; this.rounds[ev.hop].read = ps.length; this.updateJourney(); }
    this.cites.addAll(ps);
    ps.forEach(function (p) { if (p.pid) self.readPids[p.pid] = p; });
    this.renderSources();
    this.setLive('Reading ' + O.plural(ps.length, 'passage') + ' and updating the belief');
    var list = ps.length ? h('details', { class: 'hop-fold' },
      h('summary', null, O.plural(ps.length, 'passage') + ' read', O.icon('chevron-down', 16)),
      h('ul', { class: 'hop-passages' }, ps.map(function (p) {
        var st = STANCE[p.stance] || STANCE.neutral;
        return h('li', { class: 'hop-passage' },
          h('div', { class: 'hop-passage-title' }, p.title || 'Untitled'),
          h('div', { class: 'hop-passage-meta' }, metaLine(p), h('span', { class: 'stance ' + st.cls }, st.label)),
          p.reason ? h('p', { class: 'hop-reason' }, p.reason) : null);
      }))) : h('p', { class: 'hop-none' }, 'No new passages were read in this round.');
    O.clear(c.body).append(list,
      ev.belief ? h('div', { class: 'hop-note' },
        h('div', { class: 'hop-label' }, 'What the agent believed after reading' + (O.isNum(ev.confidence) ? ' (confidence ' + Math.round(ev.confidence) + '%)' : '')),
        h('p', null, ev.belief)) : null,
      ev.next_query ? h('div', { class: 'hop-note' }, h('div', { class: 'hop-label' }, 'Its own next search'), h('code', { class: 'hop-code' }, ev.next_query)) : null);
  };

  Turn.prototype.on_hop_metrics = function (ev) {
    var c = this.hops[ev.hop]; if (!c) return;
    if (ev.hop >= this.hopsPlanned) { this.steps.activate(3); this.setLive('Writing the answer from everything it read'); }
    else { this.steps.activate(2); this.setLive('Checking whether the searches are drifting toward one side'); }
    var s = ev.support || 0, n = ev.neutral || 0, k = ev.contradict || 0;
    if (this.rounds[ev.hop]) { Object.assign(this.rounds[ev.hop], { measured: true, baqd: O.isNum(ev.baqd) ? ev.baqd : null, support: s, contradict: k, neutral: n, skew: ev.skew }); this.updateJourney(); }
    var drift = O.isNum(ev.baqd)
      ? h('div', { class: 'metric' },
        h('div', { class: 'metric-label' }, 'Drift toward the belief (BAQD)'),
        O.baqdBar(ev.baqd),
        h('div', { class: 'metric-val' }, ev.baqd.toFixed(3) + (ev.baqd > 0.05 ? ', above 0.05, so this counts as drift' : ', at or below 0.05, so no drift')))
      : h('div', { class: 'metric' }, h('div', { class: 'metric-label' }, 'Drift toward the belief (BAQD)'), h('div', { class: 'metric-val' }, 'Not measured, there is no earlier belief in round 1'));
    var balance = h('div', { class: 'metric' },
      h('div', { class: 'metric-label' }, 'Balance of the passages'),
      O.balanceBar(s, n, k),
      h('div', { class: 'metric-val' }, s + ' agree, ' + n + ' neutral, ' + k + ' go against' +
        (O.isNum(ev.skew) ? ', one-sidedness ' + Math.abs(ev.skew).toFixed(2) + ' (0 is balanced, 1 is all one way)' : '')));
    var foot = (O.isNum(ev.domains) ? ev.domains + ' websites' : '') + (O.isNum(ev.sources) ? ' across ' + O.plural(ev.sources, 'source type') : '');
    c.metrics = h('div', { class: 'hop-metrics' }, drift, balance, foot ? h('p', { class: 'hop-foot' }, foot) : null);
    c.li.append(c.metrics);
  };

  Turn.prototype.on_cqi = function (ev) {
    var c = this.hops[ev.hop]; if (!c) return;
    if (ev.hop < this.hopsPlanned) this.steps.activate(2);
    if (this.rounds[ev.hop]) { this.rounds[ev.hop].cqi = ev; this.updateJourney(); }
    this.setLive('The balance check is adding a search for the other side');
    var trig = ev.trigger || {}, why = [];
    if (O.isNum(trig.baqd) && trig.baqd > 0.05) why.push('the search was drifting toward the belief');
    if (O.isNum(trig.skew) && Math.abs(trig.skew) >= 0.5) why.push('the evidence was leaning one way');
    c.banner = h('div', { class: 'cqi' },
      h('div', { class: 'cqi-title' }, 'Counter-search added after round ' + ev.hop),
      why.length ? h('p', { class: 'cqi-why' }, 'Because ' + why.join(' and ') + '.') : null,
      ev.why ? h('p', { class: 'cqi-why' }, ev.why) : null,
      h('div', { class: 'cqi-pair' },
        h('div', null, h('span', { class: 'hop-label' }, 'The search it planned'), h('code', { class: 'hop-code' }, ev.original_query || '')),
        h('div', null, h('span', { class: 'hop-label' }, 'The search it ran instead'), h('code', { class: 'hop-code' }, ev.counter_query || ''))));
    c.li.append(c.banner);
  };

  Turn.prototype.on_synthesis = function (ev) {
    this.answered = true;
    this.cites.setAnswer(ev.answer || '');
    this.renderSources();
    this.steps.activate(4);
    this.setLive('Checking every claim in the answer against the passages');
    O.clear(this.answerHost).append(
      ev.one_line ? h('p', { class: 'answer-lead' }, ev.one_line) : null,
      O.answerBlock(ev.answer || '', this.cites));
    O.clear(this.confHost);
    this.stated = ev.confidence;
  };

  Turn.prototype.on_audit = function (ev) {
    var r = ev.report || {};
    this.report = r;
    O.clear(this.evidenceHost).append(O.evBlock(r, { stated: this.stated, mode: this.guarded ? 'guarded' : 'standard' }));
    O.clear(this.reportHost).append(
      h('p', { class: 'report-lead' }, 'Each claim from the answer, checked against the passages the agent retrieved. Not verified means we found nothing that covers the claim. It does not mean the claim is false.'),
      O.claimRows(r, { cites: this.cites }));
    this.tabs.setCount('report', (r.claims || []).length);
    var self = this;
    O.clear(this.mapHost).append(O.evidenceMap(r, { onSource: function (d) {
      if (O.$('.passage[data-pid="' + d.pid + '"]', self.el)) { self.cites.jump(d.pid); return true; }
      return false;
    } }));
  };

  Turn.prototype.updateJourney = function () {
    var self = this;
    this.journey.update({ threshold: O.isNum(this.cfg.baqd_threshold) ? this.cfg.baqd_threshold : 0.05,
      rounds: Object.keys(this.rounds).map(function (k) { return self.rounds[k]; }) });
  };

  /* The real counts behind "How this answer was made". Everything comes from the events this turn received. */
  Turn.prototype.xrayModel = function () {
    var self = this, rs = Object.keys(this.rounds).map(function (k) { return self.rounds[k]; }).sort(function (a, b) { return a.hop - b.hop; });
    var fetched = {}, total = 0, types = {}, pool = null;
    rs.forEach(function (r) {
      Object.keys(r.fetched || {}).forEach(function (k) { if (O.isNum(r.fetched[k])) { fetched[k] = (fetched[k] || 0) + r.fetched[k]; total += r.fetched[k]; if (r.fetched[k] > 0) types[k] = 1; } });
      if (O.isNum(r.pool)) pool = r.pool;
    });
    var rep = this.report || {}, sc = rep.scores || {}, claims = rep.claims || [];
    if (O.isNum(rep.pool_size)) pool = rep.pool_size;
    var sites = {}, read = Object.keys(this.readPids);
    read.forEach(function (pid) { sites[domainOf(self.readPids[pid].domain)] = 1; });
    return {
      question: this.question, rounds: rs.length, searches: rs.length, guarded: this.guarded,
      own: rs.filter(function (r) { return r.origin === 'model'; }).length,
      counter: rs.filter(function (r) { return r.origin === 'counter'; }).length,
      fetched: fetched, fetchedTotal: total, fetchedTypes: Object.keys(types).length,
      pool: pool, read: read.length, sites: Object.keys(sites).length,
      claims: { n: claims.length, supported: countBy(claims, 'supported'), mixed: countBy(claims, 'mixed'), contradicted: countBy(claims, 'contradicted'), not_verified: countBy(claims, 'not_verified') },
      seconds: this.seconds
    };
  };

  Turn.prototype.on_done = function (ev) {
    var self = this;
    this.finished = true;
    this.runId = ev.run_id || null;
    this.seconds = ev.seconds;
    this.steps.finish();
    var docs = Object.keys(this.readPids), sites = {};
    if (!this.cites.sources().length) this.renderSources();
    docs.forEach(function (pid) { sites[domainOf(self.readPids[pid].domain)] = 1; });
    var xr = null;
    if (this.report) {
      xr = h('button', { type: 'button', class: 'xr-open', onclick: function () { O.answerXray(self.xrayModel(), xr); } }, O.icon('layers', 16), 'How this answer was made');
    }
    O.clear(this.progress).append(h('p', { class: 'turn-done' },
      O.plural(this.hopCount, 'round') + ', ' + O.plural(docs.length, 'passage') + ' read, from ' + O.plural(Object.keys(sites).length, 'website')), xr);
    this.thread.turnFinished(this);
  };

  Turn.prototype.on_error = function (ev) { this.fail(ev.message); };

  Turn.prototype.fail = function (message) {
    if (this.finished) return;
    this.finished = true;
    var self = this, idx = 0;
    O.$$('.step', this.steps.el).forEach(function (li, i) { if (li.getAttribute('data-state') === 'active') idx = i; });
    this.steps.fail(idx);
    O.clear(this.progress);
    O.clear(this.errorHost).append(h('div', { class: 'run-error', role: 'alert' },
      h('strong', null, 'This research could not finish. '), message || 'Something went wrong.',
      h('div', { class: 'run-error-actions' }, h('button', { type: 'button', class: 'btn btn-quiet', onclick: function () { self.thread.retry(self); } }, O.icon('refresh', 16), 'Try again'))));
    var empty = !this.cites.sources().length;
    if (!this.answered || empty) O.clear(this.answerHost).append(h('p', { class: 'muted' }, 'No answer was written.'));
    if (empty) this.renderSources();
    O.clear(this.evidenceHost);
    this.thread.turnFinished(this, true);
  };

  Turn.prototype.stopped = function () {
    if (this.finished) return;
    this.finished = true;
    if (this.stream) this.stream.stop();
    O.clear(this.progress);
    O.clear(this.errorHost).append(h('div', { class: 'note note-warn' }, 'You stopped this research before it finished.'));
    if (!this.answered) O.clear(this.answerHost).append(h('p', { class: 'muted' }, 'No answer was written.'));
    O.clear(this.evidenceHost);
    this.thread.turnFinished(this, true);
  };

  /* ---------- sources ---------- */
  Turn.prototype.renderSources = function () {
    var items = this.cites.sources();
    O.clear(this.sourcesList);
    if (!items.length) {
      this.sourcesList.append(h('p', { class: 'muted' }, this.finished ? 'No sources were found for this question.' : 'Sources appear here as they are read.'));
      return;
    }
    this.tabs.setCount('sources', items.length);
    var self = this;
    items.forEach(function (s) {
      var d = s.doc, st = STANCE[d.stance] || STANCE.neutral, url = O.safeUrl(d.url);
      var text = d.text ? h('div', { class: 'passage-text', hidden: true },
        h('p', null, O.trunc(d.text, 420)),
        h('p', { class: 'passage-stance' }, 'Compared with the agent’s belief at that point: ', h('span', { class: 'stance ' + st.cls }, st.label.toLowerCase()), '.')) : null;
      var tog = d.text ? h('button', { type: 'button', class: 'passage-toggle', 'aria-expanded': 'false', 'aria-label': 'Show the passage from ' + (d.title || siteLabel(d)),
        onclick: function () { row.setOpen(tog.getAttribute('aria-expanded') !== 'true'); } }, O.icon('chevron-down', 18)) : null;
      var row = h('article', { class: 'passage' + (s.cited ? ' is-cited' : ''), 'data-pid': d.pid },
        h('span', { class: 'passage-n' }, String(s.n)),
        h('div', { class: 'passage-main' },
          url ? h('a', { class: 'passage-title', href: url, target: '_blank', rel: 'noopener noreferrer' }, d.title || 'Untitled') : h('span', { class: 'passage-title' }, d.title || 'Untitled'),
          h('div', { class: 'passage-meta' }, metaLine(d), s.cited ? h('span', { class: 'passage-cited' }, 'cited') : null),
          text),
        tog);
      row.setOpen = function (open) {
        if (!tog) return;
        tog.setAttribute('aria-expanded', open ? 'true' : 'false'); text.hidden = !open;
      };
      self.sourcesList.append(row);
    });
  };

  /* ====================================================================== Thread */
  function Thread(el) {
    var self = this;
    this.el = el; this.turns = []; this.opts = { guarded: true, hops: 4 }; this.busy = null;
    this.list = h('div', { class: 'thread-list' });
    this.composer = O.composer({
      options: false, placeholder: 'Ask a follow-up', label: 'Ask a follow-up question',
      onSubmit: function (q) { self.ask(q); },
      onStop: function () { if (self.busy) self.busy.stopped(); }
    });
    this.dock = h('div', { class: 'thread-dock' }, h('div', { class: 'thread-dock-in' }, this.composer.el));
    this.dock.hidden = true;
    el.append(h('div', { class: 'thread page' }, this.list), this.dock);
  }

  Thread.prototype.reset = function () {
    if (this.busy && this.busy.stream) this.busy.stream.stop();
    this.busy = null; this.turns = [];
    O.clear(this.list);
    this.composer.setValue(''); this.composer.setBusy(false);
  };

  Thread.prototype.addTurn = function (o) {
    var t = new Turn(this, Object.assign({ first: this.turns.length === 0 }, o));
    this.turns.push(t);
    this.list.append(t.el);
    this.dock.hidden = false;
    return t;
  };

  Thread.prototype.lastRunId = function () {
    for (var i = this.turns.length - 1; i >= 0; i--) if (this.turns[i].runId) return this.turns[i].runId;
    return null;
  };

  Thread.prototype.runLive = function (t) {
    var self = this;
    var url = '/api/research/stream?q=' + encodeURIComponent(t.question) + '&mode=' + (t.guarded ? 'guarded' : 'standard') + '&hops=' + t.hopsPlanned + (t.prev ? '&prev=' + encodeURIComponent(t.prev) : '');
    this.busy = t; this.composer.setBusy(true);
    t.steps.activate(0);
    t.setLive('Starting');
    t.stream = O.sse(url, function (ev) { t.handle(ev); });
    t.stream.done.then(function () {
      if (!t.finished) t.fail('The connection closed before the research finished. Please try again.');
    }).catch(function (err) {
      if (err && err.name === 'AbortError') return;
      t.fail(O.friendlyError(err));
    });
  };

  Thread.prototype.start = function (req) {
    this.reset();
    this.opts = { guarded: req.guarded !== false, hops: req.hops || 4 };
    var t = this.addTurn({ question: req.question, guarded: this.opts.guarded, hops: this.opts.hops, first: true });
    O.setTitle(O.trunc(req.question, 60));
    this.runLive(t);
  };

  Thread.prototype.ask = function (question) {
    if (this.busy) return;
    var t = this.addTurn({ question: question, guarded: this.opts.guarded, hops: this.opts.hops, prev: this.lastRunId() });
    this.composer.setValue('');
    this.runLive(t);
    var el = t.el;
    setTimeout(function () { el.scrollIntoView({ block: 'start', behavior: O.REDUCED ? 'auto' : 'smooth' }); }, 30);
  };

  Thread.prototype.retry = function (t) {
    if (this.busy) return;
    var fresh = new Turn(this, { question: t.question, guarded: t.guarded, hops: t.hopsPlanned, prev: t.prev, first: t.first });
    var i = this.turns.indexOf(t);
    this.turns[i] = fresh;
    t.el.replaceWith(fresh.el);
    this.runLive(fresh);
  };

  Thread.prototype.turnFinished = function (t, failed) {
    if (this.busy === t) { this.busy = null; this.composer.setBusy(false); }
    if (!failed) { O.refreshRuns(); if (!t.first) { /* keep the new turn in view */ } }
  };

  Thread.prototype.showRun = function (run) {
    this.reset();
    this.opts = { guarded: run.mode !== 'standard', hops: (run.config && run.config.hops) || 4 };
    var t = this.addTurn({ question: run.question, guarded: run.mode !== 'standard', hops: this.opts.hops, first: true });
    O.setTitle(O.trunc(run.question, 60));
    var evs = O.recordToEvents(run);
    evs.forEach(function (ev) { if (ev.type === 'done') ev.run_id = run.run_id; t.handle(ev); });
    this.dock.hidden = false;
  };

  /* ====================================================================== routes */
  O.route('thread', {
    title: 'Research',
    init: function (el) { el._thread = new Thread(el); },
    hide: function (el) { var b = el._thread && el._thread.busy; if (b) b.stopped(); },
    show: function (el) {
      var req = O.takePending();
      if (req) { el._thread.start(req); return; }
      if (!el._thread.turns.length) O.go('/ask');
    }
  });

  O.route('r', {
    title: 'Saved research',
    init: function (el) { el._thread = new Thread(el); },
    show: function (el, p) {
      var th = el._thread;
      if (th.loadedId === p.id && th.turns.length) return;
      th.loadedId = p.id;
      th.reset();
      O.clear(th.list).append(h('div', { class: 'thread-loading muted' }, O.spinner(), 'Opening saved research'));
      th.dock.hidden = true;
      O.api('/api/runs/' + encodeURIComponent(p.id)).then(function (run) {
        if (th.loadedId !== p.id) return;
        O.clear(th.list);
        th.showRun(run);
      }).catch(function (err) {
        th.loadedId = null;
        O.clear(th.list).append(h('div', { class: 'run-error', role: 'alert' }, 'This saved research could not be opened. ' + O.friendlyError(err)),
          h('p', null, h('a', { class: 'btn-link', href: O.href('/ask') }, 'Back to the ask page')));
      });
    }
  });
})();
