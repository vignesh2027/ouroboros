/* Landing page: a standalone document (landing.html, served at /). It does not load the app scripts; the small helpers below
   (element builder, logo, arrow icon) mirror the ones in core.js. Links into the app go to /app#/....
   A full-width marketing page with its own slim top bar and no app sidebar.
   Everything is drawn with inline SVG and plain HTML, with colours from tokens only (see css/landing.css).
   Sections: hero with a wireframe of the answer screen, the problem, the system diagram, three ideas,
   check any AI's answer, honest results, final call to action.
   Numbers on this page are real constants only: five source types, 2 to 6 rounds, four verdicts. */
(function () {
  'use strict';
  var O = {};
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
    for (var i = 2; i < arguments.length; i++) add(el, arguments[i]);
    return el;
  };
  function add(el, kid) {
    if (kid == null || kid === false) return;
    if (Array.isArray(kid)) { kid.forEach(function (k) { add(el, k); }); return; }
    el.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  }
  var h = O.h;
  O.href = function (path) { return '/app#' + path; };
  O.icon = function (name, size) {
    var s = size || 20, NS = 'http://www.w3.org/2000/svg';
    var el = document.createElementNS(NS, 'svg');
    var attrs = { viewBox: '0 0 24 24', width: s, height: s, fill: 'none', stroke: 'currentColor', 'stroke-width': 1.6, 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'aria-hidden': 'true', focusable: 'false', class: 'icon icon-' + name };
    Object.keys(attrs).forEach(function (k) { el.setAttribute(k, attrs[k]); });
    var path = document.createElementNS(NS, 'path');
    path.setAttribute('d', 'M5 12h14M13 6l6 6-6 6');
    el.append(path);
    return el;
  };
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
  var reduce = function () { return window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches; };

  /* ---------- small helpers ---------- */
  function frag(html) { var d = document.createElement('div'); d.innerHTML = html.trim(); return d.firstElementChild; }
  function esc(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }
  function scrollToId(id) {
    var t = document.getElementById(id);
    if (!t) return;
    t.scrollIntoView({ behavior: reduce() ? 'auto' : 'smooth', block: 'start' });
    try { t.focus({ preventScroll: true }); } catch (e) {}
  }
  function anchor(id, cls, children) {
    return h('a', { class: cls, href: '#' + id, 'data-anchor': id, onclick: function (e) { e.preventDefault(); scrollToId(id); } }, children);
  }
  function section(id, cls, inner) {
    return h('section', { class: 'ld-sec ' + (cls || ''), id: id, tabindex: '-1', 'aria-labelledby': id + '-h' }, h('div', { class: 'ld-wrap' }, inner));
  }
  function title(id, text, lead) {
    return h('header', { class: 'ld-head' }, h('h2', { id: id + '-h', class: 'ld-h2' }, text), lead ? h('p', { class: 'ld-lead' }, lead) : null);
  }

  /* ---------- top bar ---------- */
  function topbar() {
    return h('header', { class: 'ld-top' },
      h('div', { class: 'ld-wrap ld-top-in' },
        h('a', { class: 'ld-brand', href: '#top', 'aria-label': 'Ouroboros, top of page', onclick: function (e) { e.preventDefault(); window.scrollTo({ top: 0, behavior: reduce() ? 'auto' : 'smooth' }); } },
          O.logo(22), h('span', { class: 'wordmark' }, 'Ouroboros')),
        h('nav', { class: 'ld-nav', 'aria-label': 'Page' },
          anchor('connected', 'ld-navlink', 'How it works'),
          h('a', { class: 'ld-navlink', href: O.href('/audit') }, 'Check an AI answer'),
          anchor('results', 'ld-navlink', 'Results')),
        h('a', { class: 'btn btn-primary ld-cta', href: O.href('/ask') }, 'Start researching')));
  }

  /* ---------- hero wireframe of the answer screen ---------- */
  function bar(w, cls) { return '<i class="ld-bar ' + (cls || '') + '" style="width:' + w + '%"></i>'; }
  function cite(n) { return '<b class="ld-cite">' + n + '</b>'; }
  function wireframe() {
    var ring = '<svg class="ld-ring" viewBox="0 0 56 56" width="56" height="56" aria-hidden="true" focusable="false">' +
      '<circle cx="28" cy="28" r="22" fill="none" stroke="var(--line-strong)" stroke-width="5"/>' +
      '<circle cx="28" cy="28" r="22" fill="none" stroke="var(--support)" stroke-width="5" stroke-linecap="round" stroke-dasharray="118 138" transform="rotate(-90 28 28)"/>' +
      '<path d="M20 28.5l5.5 5.5L36.5 22" fill="none" stroke="var(--support)" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg>';
    var src = function (n, name, w) {
      return '<div class="ld-src">' + cite(n) + '<span class="ld-chip">' + name + '</span>' + bar(w) + '</div>';
    };
    var html =
      '<figure class="ld-shot">' +
        '<div class="ld-shot-bar" aria-hidden="true"><span></span><span></span><span></span><em>Answer screen</em></div>' +
        '<div class="ld-shot-body">' +
          '<div class="ld-shot-side" aria-hidden="true">' +
            '<span class="ld-sk ld-sk-brand"></span><span class="ld-sk ld-sk-btn"></span><span class="ld-sk-gap"></span>' + bar(70) + bar(86) + bar(58) + bar(76) +
          '</div>' +
          '<div class="ld-shot-main">' +
            '<div class="ld-blk"><span class="ld-tag">Question</span><div class="ld-qline">Is intermittent fasting effective for weight loss?</div></div>' +
            '<div class="ld-blk"><span class="ld-tag">Answer</span><div class="ld-ans">' +
              '<p><span class="ld-real">The answer is written here in plain sentences, with a numbered citation after each claim.' + cite(1) + cite(2) + '</span>' + bar(88) + '<span class="ld-endline">' + bar(34) + '</span></p>' +
              '<p>' + bar(92) + bar(80) + '<span class="ld-endline">' + bar(52) + cite(3) + '</span></p>' +
            '</div></div>' +
            '<div class="ld-blk"><span class="ld-tag">Evidence</span><div class="ld-ev">' + ring +
              '<div class="ld-ev-text"><strong>Well supported</strong><span class="ld-real">Share of claims backed by the evidence</span></div>' +
              '<span class="ld-pillbtn">Details</span></div></div>' +
            '<div class="ld-blk"><span class="ld-tag">Sources</span><div class="ld-srcs">' +
              '<div class="ld-tabs" aria-hidden="true"><b>Sources</b><span>Evidence map</span><span>Research path</span><span>Evidence report</span></div>' +
              src(1, 'Wikipedia', 62) + src(2, 'PubMed', 48) + src(3, 'arXiv', 56) +
            '</div></div>' +
          '</div>' +
        '</div>' +
        '<figcaption>An illustration of the answer screen, drawn as a wireframe. It shows the layout, not real data.</figcaption>' +
      '</figure>';
    return frag(html);
  }

  /* ---------- hero ---------- */
  function hero() {
    return h('section', { class: 'ld-hero', 'aria-labelledby': 'hero-h' },
      h('div', { class: 'ld-wrap ld-hero-in' },
        h('div', { class: 'ld-hero-mark' }, O.logo(64, { word: true, rule: true })),
        h('h1', { id: 'hero-h', class: 'ld-h1' }, 'Research you can check.'),
        h('p', { class: 'ld-sub' },
          'Ouroboros is an agentic RAG system. It searches many kinds of sources, watches itself for one-sided searching, ',
          'and checks every claim against the evidence it found.'),
        h('div', { class: 'ld-actions' },
          h('a', { class: 'btn btn-primary btn-lg', href: O.href('/ask') }, 'Start researching'),
          anchor('connected', 'ld-textlink', ['See how it works', O.icon('arrow-right', 16)])),
        wireframe()));
  }

  /* ---------- the problem ---------- */
  function loopSvg() {
    var cx = 120, cy = 100, r = 64;
    function pt(a) { var t = a * Math.PI / 180; return [(cx + r * Math.cos(t)).toFixed(1), (cy + r * Math.sin(t)).toFixed(1)]; }
    var nodes = [
      { a: -90, t: 'Search' },
      { a: 30, t: 'Belief' },
      { a: 150, t: 'Next search' }
    ];
    var arcs = '';
    for (var i = 0; i < 3; i++) {
      var a = pt(nodes[i].a + 38), b = pt(nodes[(i + 1) % 3].a - 40);
      arcs += '<path d="M' + a[0] + ' ' + a[1] + ' A' + r + ' ' + r + ' 0 0 1 ' + b[0] + ' ' + b[1] + '" class="ld-line" marker-end="url(#ld-loop-ar)"/>';
    }
    var boxes = nodes.map(function (n) {
      var p = pt(n.a), w = n.t.length > 8 ? 92 : 68;
      return '<g class="ld-node"><rect x="' + (p[0] - w / 2) + '" y="' + (p[1] - 14) + '" width="' + w + '" height="28" rx="6"/><text class="ld-lab" x="' + p[0] + '" y="' + (+p[1] + 4.5) + '" text-anchor="middle">' + n.t + '</text></g>';
    }).join('');
    return frag('<svg class="ld-loop" viewBox="0 0 240 200" role="img" aria-label="A loop: the agent searches, updates its belief, and its next search follows that belief">' +
      '<defs><marker id="ld-loop-ar" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M1.5 1.5L8 5L1.5 8.5" class="ld-ar"/></marker></defs>' +
      arcs + boxes + '<text class="ld-note" x="120" y="104" text-anchor="middle">the ouroboros</text></svg>');
  }
  function problem() {
    return section('problem', 'ld-problem', [
      title('problem', 'Two problems, one loop'),
      h('div', { class: 'ld-prob' },
        h('div', { class: 'ld-prob-col' },
          h('h3', null, 'Answers you cannot inspect'),
          h('p', null, 'AI answers sound sure, but you cannot see what backs them. A fluent paragraph can hide a claim that no source supports.')),
        h('div', { class: 'ld-prob-fig' }, loopSvg()),
        h('div', { class: 'ld-prob-col' },
          h('h3', null, 'Agents that drift'),
          h('p', null, 'Research agents drift: each search follows what they already believe, so the evidence piles up on one side. That loop is the ouroboros, a snake eating its own tail.')))
    ]);
  }

  /* ---------- system diagram ---------- */
  var SOURCES = ['Wikipedia', 'OpenAlex', 'arXiv', 'PubMed', 'The open web'];

  function node(x, y, w, hgt, label, sub, num, o) {
    o = o || {};
    var subs = sub ? (Array.isArray(sub) ? sub : [sub]) : [];
    var lines = 1 + subs.length, cy = y + hgt / 2, first = cy - (lines - 1) * 8.5 + 4.5;
    var t = '<text class="ld-lab" x="' + (x + w / 2) + '" y="' + first + '" text-anchor="middle">' + label + '</text>';
    subs.forEach(function (s, i) { t += '<text class="ld-sub-t" x="' + (x + w / 2) + '" y="' + (first + 17 * (i + 1)) + '" text-anchor="middle">' + s + '</text>'; });
    var badge = num ? '<g class="ld-badge' + (o.dashed ? ' is-ext' : '') + '"><circle cx="' + x + '" cy="' + y + '" r="10"/><text x="' + x + '" y="' + (y + 4) + '" text-anchor="middle">' + num + '</text></g>' : '';
    return '<g class="ld-node' + (o.dashed ? ' is-ext' : '') + (o.guard ? ' is-guard' : '') + '"><rect x="' + x + '" y="' + y + '" width="' + w + '" height="' + hgt + '" rx="6"/>' + t + '</g>' + badge;
  }
  function chip(x, y, w, hgt, text) {
    return '<g class="ld-chip-g"><rect x="' + x + '" y="' + y + '" width="' + w + '" height="' + hgt + '" rx="5"/><text class="ld-sub-t ld-chip-t" x="' + (x + w / 2) + '" y="' + (y + hgt / 2 + 4.5) + '" text-anchor="middle">' + text + '</text></g>';
  }
  function defs(p) {
    function m(id, cls) { return '<marker id="' + p + id + '" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M1.5 1.5L8 5L1.5 8.5" class="ld-ar ' + cls + '"/></marker>'; }
    return '<defs>' + m('ar', '') + m('arb', 'is-guard') + m('ard', 'is-ext') + '</defs>';
  }
  function ln(d, kind, p) {
    var mk = kind === 'guard' ? 'arb' : kind === 'ext' ? 'ard' : 'ar';
    return '<path d="' + d + '" class="ld-line' + (kind === 'guard' ? ' is-guard' : kind === 'ext' ? ' is-ext' : '') + '" marker-end="url(#' + p + mk + ')"/>';
  }
  function dots(paths) {
    if (reduce()) return '';
    return paths.map(function (d) {
      return '<circle r="3.6" class="ld-dot' + (d.guard ? ' is-guard' : '') + '"><animateMotion dur="' + d.dur + 's" begin="' + d.begin + 's" repeatCount="indefinite" path="' + d.d + '"/></circle>';
    }).join('');
  }

  function desktopDiagram() {
    var p = 'dd-', s = '';
    /* connectors first so the boxes sit on top of them */
    s += ln('M140 154 H208', '', p);
    var cys = [66, 110, 154, 198, 242];
    cys.forEach(function (cy) {
      s += '<path d="M360 154 C415 154 415 ' + cy + ' 470 ' + cy + '" class="ld-line ld-fan" marker-end="url(#' + p + 'ar)"/>';
      var ey = (154 + (cy - 154) * 0.3).toFixed(1);
      s += '<path d="M610 ' + cy + ' C662 ' + cy + ' 662 ' + ey + ' 708 ' + ey + '" class="ld-line ld-fan" marker-end="url(#' + p + 'ar)"/>';
    });
    s += ln('M795 189 V373', '', p);
    s += ln('M710 410 H622', '', p);
    s += ln('M420 410 H362', '', p);
    s += ln('M250 375 V191', '', p);
    s += ln('M340 375 V311 H468', 'guard', p);
    s += '<path d="M470 262 V269 H610 V262" class="ld-line is-guard ld-thin"/>';
    s += ln('M540 292 V270', 'guard', p);
    s += ln('M265 445 V528', '', p);
    s += ln('M760 445 V490 H535 V518', '', p);
    s += ln('M360 560 H428', '', p);
    s += ln('M640 560 H708', '', p);
    s += ln('M535 640 V602', 'ext', p);
    s += dots([
      { d: 'M140 154 H360 C415 154 420 110 470 110 H610 C662 110 662 141 710 141 H795 V410 H250 V154', dur: 9, begin: 0 },
      { d: 'M140 154 H360 C415 154 420 110 470 110 H610 C662 110 662 141 710 141 H795 V410 H250 V154', dur: 9, begin: -4.5 },
      { d: 'M340 375 V311 H470 V270', dur: 3.2, begin: -1, guard: true },
      { d: 'M265 445 V560 H430 H710', dur: 5, begin: -2 }
    ]);
    /* nodes */
    s += node(20, 124, 120, 60, 'QUESTION', null, 1);
    s += node(210, 124, 150, 60, 'AGENT', 'plans the search', 2);
    s += '<text class="ld-cap" x="540" y="36" text-anchor="middle">FIVE SOURCE TYPES</text>';
    SOURCES.forEach(function (n, i) { s += chip(470, cys[i] - 16, 140, 32, n); });
    s += '<g class="ld-badge"><circle cx="470" cy="50" r="10"/><text x="470" y="54" text-anchor="middle">3</text></g>';
    s += node(710, 119, 170, 70, 'RAG RANKER', ['BM25 + TF-IDF,', 'diversity re-ranking'], 4);
    s += node(710, 375, 170, 70, 'EVIDENCE POOL', 'ranked passages', 5);
    s += node(420, 375, 200, 70, 'READER', ['updates belief,', 'writes next search'], 6);
    s += node(170, 375, 190, 70, 'BALANCE GUARD', ['BAQD drift +', 'evidence skew'], 7, { guard: true });
    s += node(470, 292, 140, 38, 'COUNTER-QUERY', null, 8, { guard: true });
    s += node(170, 530, 190, 60, 'WRITER', 'cited answer', 9);
    s += node(430, 520, 210, 80, 'CLAIM AUDIT', ['supported, contradicted,', 'mixed, not verified'], 10);
    s += node(710, 525, 170, 70, 'EVIDENCE REPORT', ['score, grade,', 'claim verdicts'], 11);
    s += node(430, 640, 210, 56, 'PASTED ANSWER', 'ChatGPT, Claude or Gemini', 'A', { dashed: true });
    /* labels */
    s += '<text class="ld-edge" x="240" y="282" text-anchor="end">on track</text>';
    s += '<text class="ld-edge ld-edge-s" x="240" y="300" text-anchor="end">next round, 2 to 6 rounds</text>';
    s += '<text class="ld-edge is-guard" x="350" y="303">drifting</text>';
    s += '<text class="ld-edge ld-edge-s" x="276" y="492">after the last round</text>';
    s += '<text class="ld-edge ld-edge-s" x="770" y="482">retrieved passages</text>';
    s += '<text class="ld-edge is-guard" x="550" y="284">searches all five again</text>';
    s += '<text class="ld-edge ld-edge-s" x="545" y="626">checked against our evidence</text>';
    /* key */
    s += '<g class="ld-key" transform="translate(700 646)"><path d="M0 0 H36" class="ld-line"/><text x="48" y="4">Main path</text>' +
         '<path d="M0 22 H36" class="ld-line is-guard"/><text x="48" y="26">Balance guard path</text>' +
         '<path d="M0 44 H36" class="ld-line is-ext"/><text x="48" y="48">Pasted answer</text></g>';
    return frag('<svg class="ld-diagram ld-d-wide" viewBox="0 0 900 710" role="img" aria-labelledby="dd-t dd-d">' +
      '<title id="dd-t">How Ouroboros is connected</title>' +
      '<desc id="dd-d">A question goes to the agent, which searches five source types. Our ranker orders the passages into an evidence pool. The reader updates its belief and writes the next search. The balance guard either sends the agent into another round, 2 to 6 rounds in all, or sends a counter-query back to the sources. After the last round the writer produces a cited answer, and the claim audit produces the evidence report. An answer pasted from ChatGPT, Claude or Gemini goes to the claim audit, which checks it against evidence retrieved for the question.</desc>' +
      defs(p) + s + '</svg>');
  }

  function mobileDiagram() {
    var p = 'dm-', s = '';
    var X = 56, W = 184, CX = 148;
    s += ln('M' + CX + ' 60 V90', '', p);
    s += ln('M' + CX + ' 142 V172', '', p);
    s += ln('M' + CX + ' 338 V370', '', p);
    s += ln('M' + CX + ' 442 V472', '', p);
    s += ln('M' + CX + ' 524 V554', '', p);
    s += ln('M' + CX + ' 622 V652', '', p);
    s += '<path d="M56 687 H30 V117 H54" class="ld-line" marker-end="url(#' + p + 'ar)"/>';
    s += ln('M240 687 H306 V646', 'guard', p);
    s += ln('M306 580 V256 H242', 'guard', p);
    s += ln('M' + CX + ' 720 V770', '', p);
    s += ln('M' + CX + ' 818 V848', '', p);
    s += ln('M' + CX + ' 930 V956', '', p);
    s += ln('M262 888 H242', 'ext', p);
    /* nodes */
    s += node(X, 16, W, 44, 'QUESTION', null, 1);
    s += node(X, 92, W, 50, 'AGENT', 'plans the search', 2);
    /* sources list box */
    s += '<g class="ld-node"><rect x="' + X + '" y="174" width="' + W + '" height="164" rx="6"/>' +
         '<text class="ld-cap" x="' + CX + '" y="198" text-anchor="middle">FIVE SOURCE TYPES</text>';
    SOURCES.forEach(function (n, i) {
      var y = 208 + i * 26;
      s += '<path d="M' + (X + 14) + ' ' + y + ' H' + (X + W - 14) + '" class="ld-hair"/><text class="ld-sub-t" x="' + CX + '" y="' + (y + 18) + '" text-anchor="middle">' + n + '</text>';
    });
    s += '</g><g class="ld-badge"><circle cx="' + X + '" cy="174" r="10"/><text x="' + X + '" y="178" text-anchor="middle">3</text></g>';
    s += node(X, 372, W, 70, 'RAG RANKER', ['BM25 + TF-IDF,', 'diversity re-ranking'], 4);
    s += node(X, 474, W, 50, 'EVIDENCE POOL', 'ranked passages', 5);
    s += node(X, 556, W, 66, 'READER', ['updates belief,', 'writes next search'], 6);
    s += node(X, 654, W, 66, 'BALANCE GUARD', ['BAQD drift +', 'evidence skew'], 7, { guard: true });
    s += '<g class="ld-node is-guard"><rect x="262" y="580" width="88" height="64" rx="6"/><text class="ld-lab" x="306" y="608" text-anchor="middle">COUNTER-</text><text class="ld-lab" x="306" y="626" text-anchor="middle">QUERY</text></g><g class="ld-badge"><circle cx="262" cy="580" r="10"/><text x="262" y="584" text-anchor="middle">8</text></g>';
    s += node(X, 772, W, 46, 'WRITER', 'cited answer', 9);
    s += node(X, 850, W, 80, 'CLAIM AUDIT', ['supported, contradicted,', 'mixed, not verified', 'checked against the pool (5)'], 10);
    s += node(X, 958, W, 66, 'EVIDENCE REPORT', ['score, grade,', 'claim verdicts'], 11);
    s += '<g class="ld-node is-ext"><rect x="262" y="838" width="88" height="100" rx="6"/>' +
         ['PASTED', 'ANSWER'].map(function (t, i) { return '<text class="ld-lab" x="306" y="' + (862 + i * 15) + '" text-anchor="middle">' + t + '</text>'; }).join('') +
         ['ChatGPT', 'Claude', 'Gemini'].map(function (t, i) { return '<text class="ld-sub-t" x="306" y="' + (902 + i * 15) + '" text-anchor="middle">' + t + '</text>'; }).join('') +
         '</g><g class="ld-badge is-ext"><circle cx="262" cy="838" r="10"/><text x="262" y="842" text-anchor="middle">A</text></g>';
    /* labels */
    s += '<text class="ld-edge ld-edge-s" x="16" y="400" text-anchor="middle" transform="rotate(-90 16 400)">on track: next round, 2 to 6 rounds</text>';
    s += '<text class="ld-edge is-guard" x="250" y="680">drifting</text>';
    s += '<text class="ld-edge ld-edge-s" x="158" y="752">after the last round</text>';
    return frag('<svg class="ld-diagram ld-d-tall" viewBox="0 0 360 1040" role="img" aria-labelledby="dm-t dm-d">' +
      '<title id="dm-t">How Ouroboros is connected</title>' +
      '<desc id="dm-d">The same flow drawn top to bottom: question, agent, five source types, ranker, evidence pool, reader, balance guard. On track returns to the agent for another round, 2 to 6 rounds in all. Drifting goes through a counter-query back to the sources. After the last round, the writer, the claim audit and the evidence report follow. A pasted answer from ChatGPT, Claude or Gemini goes to the claim audit, which checks it against evidence retrieved for the question.</desc>' +
      defs(p) + s + '</svg>');
  }

  var LEGEND = [
    ['1', 'Question', 'What you ask, in your own words.'],
    ['2', 'Agent', 'Plans the first search, and each search after it.'],
    ['3', 'Five source types', 'Wikipedia (background), OpenAlex (scholarly works), arXiv (preprints), PubMed (biomedical) and the open web (reports and news) all feed the pool.'],
    ['4', 'RAG ranker', 'Our own retrieval code scores passages with BM25 and TF-IDF, then re-ranks for diversity so one viewpoint does not crowd out the rest.'],
    ['5', 'Evidence pool', 'The ranked passages gathered so far, round after round.'],
    ['6', 'Reader', 'Reads the passages, updates what it believes, and writes its own next search.'],
    ['7', 'Balance guard', 'After every round it measures BAQD drift and evidence skew.'],
    ['8', 'Counter-query', 'If either crosses a threshold, a search for opposing evidence is added.'],
    ['9', 'Writer', 'After the last round, writes the answer with numbered citations.'],
    ['10', 'Claim audit', 'Checks every claim against the evidence pool: supported, contradicted, mixed or not verified.'],
    ['11', 'Evidence report', 'The Evidence Support Score, a grade, and a verdict for every claim.'],
    ['A', 'Pasted answer', 'An answer from ChatGPT, Claude or Gemini goes to the claim audit, which checks it against evidence retrieved for your question.']
  ];

  function connected() {
    var legend = h('ol', { class: 'ld-legend', 'aria-label': 'What each part does' }, LEGEND.map(function (r) {
      return h('li', null, h('span', { class: 'ld-ln' + (r[0] === 'A' ? ' is-ext' : '') }, r[0]), h('div', null, h('strong', null, r[1]), h('span', null, r[2])));
    }));
    var wide = desktopDiagram(), tall = mobileDiagram();
    return section('connected', 'ld-connected', [
      title('connected', 'How everything is connected',
        'One question runs a loop of two to six rounds. After each round a balance guard checks the agent is still looking at the question, not just at what it already believes.'),
      h('div', { class: 'ld-dia-box' }, wide, tall),
      legend,
      h('p', { class: 'ld-more' }, h('a', { class: 'ld-textlink', href: O.href('/how') }, ['Read the full walk-through', O.icon('arrow-right', 16)]))
    ]);
  }

  /* ---------- inside our RAG system ---------- */
  function mini(label, inner) {
    return frag('<svg class="ld-mini" viewBox="0 0 240 110" role="img" aria-label="' + label + '">' + inner + '</svg>');
  }
  function ragDoc() {
    var s = '<rect x="20" y="8" width="200" height="22" rx="4" class="ld-po"/>' +
      '<text class="ld-mini-t" x="120" y="23" text-anchor="middle">one document</text>' +
      '<path d="M120 34 V50" class="ld-line ld-thin" marker-end="url(#ld-r1-ar)"/>';
    [0, 1, 2, 3].forEach(function (i) {
      var x = 20 + i * 52;
      s += '<rect x="' + x + '" y="58" width="44" height="34" rx="4" class="ld-po"/>' +
        '<rect x="' + (x + 6) + '" y="66" width="32" height="4" rx="2" class="ld-sk-r"/><rect x="' + (x + 6) + '" y="75" width="24" height="4" rx="2" class="ld-sk-r"/>' +
        '<text class="ld-mini-t" x="' + (x + 22) + '" y="104" text-anchor="middle">passage ' + (i + 1) + '</text>';
    });
    return mini('One document cut into four passages', '<defs><marker id="ld-r1-ar" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M1.5 1.5L8 5L1.5 8.5" class="ld-ar"/></marker></defs>' + s);
  }
  function ragScore() {
    function row(y, label, w, cls) {
      return '<text class="ld-mini-t" x="4" y="' + (y - 4) + '">' + label + '</text><rect x="4" y="' + y + '" width="232" height="9" rx="4" class="ld-po"/><rect x="4" y="' + y + '" width="' + w + '" height="9" rx="4" class="' + cls + '"/>';
    }
    return mini('Two scores for one passage, averaged into one', row(22, 'keyword match (BM25)', 160, 'ld-blk-a') + row(56, 'term weight (TF-IDF)', 110, 'ld-blk-a') +
      '<path d="M4 82 H236" class="ld-hair-s"/>' + row(100, 'combined, half each', 135, 'ld-brass-f').replace('y="96"', 'y="96"'));
  }
  function ragDiverse() {
    function row(y, label, letters) {
      var s = '<text class="ld-mini-t" x="4" y="' + (y - 6) + '">' + label + '</text>';
      letters.forEach(function (l, i) {
        var x = 4 + i * 46;
        s += '<rect x="' + x + '" y="' + y + '" width="40" height="22" rx="4" class="ld-po' + (l === 'A' ? ' is-dim' : '') + '"/><text class="ld-mini-t ld-mini-l" x="' + (x + 20) + '" y="' + (y + 15) + '" text-anchor="middle">site ' + l + '</text>';
      });
      return s;
    }
    return mini('Ranked by score, one site fills the top; after re-ranking, different sites share it',
      row(16, 'ranked by score alone', ['A', 'A', 'A', 'B', 'C']) +
      '<path d="M120 42 V56" class="ld-line is-guard ld-thin" marker-end="url(#ld-r3-ar)"/>' +
      row(80, 'after diversity re-ranking', ['A', 'B', 'C', 'A', 'A']) +
      '<defs><marker id="ld-r3-ar" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M1.5 1.5L8 5L1.5 8.5" class="ld-ar is-guard"/></marker></defs>');
  }
  function ragPool() {
    var s = '';
    [[3, 0], [6, 3], [11, 6]].forEach(function (r, ri) {
      var y = 12 + ri * 32;
      s += '<text class="ld-mini-t" x="4" y="' + (y + 10) + '">round ' + (ri + 1) + '</text>';
      for (var i = 0; i < r[0]; i++) {
        s += '<rect x="' + (52 + i * 16) + '" y="' + y + '" width="12" height="14" rx="2" class="' + (i < r[1] ? 'ld-blk-a' : 'ld-brass-f') + '"/>';
      }
    });
    return mini('The pool grows each round: earlier passages stay, new ones are added', s +
      '<rect x="4" y="99" width="9" height="9" rx="2" class="ld-blk-a"/><text class="ld-mini-t" x="18" y="107">kept</text><rect x="52" y="99" width="9" height="9" rx="2" class="ld-brass-f"/><text class="ld-mini-t" x="66" y="107">new this round</text>');
  }
  function ragCite() {
    return mini('A numbered citation in a sentence points to one exact passage',
      '<rect x="4" y="22" width="104" height="6" rx="3" class="ld-sk-r"/><rect x="4" y="36" width="88" height="6" rx="3" class="ld-sk-r"/>' +
      '<rect x="96" y="31" width="16" height="16" rx="4" fill="none" class="ld-chipbox"/><text class="ld-mini-t ld-mini-c" x="104" y="42.5" text-anchor="middle">1</text>' +
      '<path d="M112 39 H138" class="ld-line ld-thin" marker-end="url(#ld-r5-ar)"/>' +
      '<rect x="142" y="12" width="94" height="86" rx="5" class="ld-po"/>' +
      '<rect x="150" y="22" width="78" height="5" rx="2" class="ld-sk-r"/><rect x="150" y="34" width="78" height="5" rx="2" class="ld-brass-f"/><rect x="150" y="46" width="62" height="5" rx="2" class="ld-brass-f"/><rect x="150" y="58" width="78" height="5" rx="2" class="ld-sk-r"/><rect x="150" y="70" width="50" height="5" rx="2" class="ld-sk-r"/>' +
      '<text class="ld-mini-t" x="189" y="92" text-anchor="middle">exact passage</text>' +
      '<defs><marker id="ld-r5-ar" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M1.5 1.5L8 5L1.5 8.5" class="ld-ar"/></marker></defs>');
  }
  function ragAudit() {
    var s = '', claims = [[14, 'support'], [42, 'contradict'], [70, 'mixed']];
    claims.forEach(function (c) {
      s += '<circle cx="10" cy="' + (c[0] + 4) + '" r="5" fill="var(--' + c[1] + ')"/><rect x="22" y="' + (c[0] + 1) + '" width="66" height="6" rx="3" class="ld-sk-r"/>';
    });
    for (var r = 0; r < 3; r++) for (var q = 0; q < 4; q++) {
      s += '<rect x="' + (140 + q * 24) + '" y="' + (10 + r * 28) + '" width="18" height="22" rx="3" class="ld-po"/>';
    }
    s += '<path d="M92 18 L138 21" class="ld-line ld-thin"/><path d="M92 46 L190 49" class="ld-line ld-thin is-guard"/><path d="M92 74 L162 77" class="ld-line ld-thin"/>';
    s += '<text class="ld-mini-t" x="188" y="102" text-anchor="middle">the same pool</text>';
    return mini('Claims in the answer checked against the same pool of passages', s);
  }
  var RAG_STEPS = [
    ['Documents become passages', 'We fetch Wikipedia articles, abstracts from OpenAlex, arXiv and PubMed, and pages from the open web. Each one is cut into passages of whole sentences, about a hundred words long, with any short tail folded back in so there are no stubs. A passage keeps its source, title, link and year.', ragDoc],
    ['Every passage gets two scores', 'A keyword score (BM25) rewards passages that use the rare words in the search. A term-weight score (TF-IDF) measures how close the whole passage is to the search. Each counts for half. A passage that shares no words with the search is left out.', ragScore],
    ['Diversity re-ranking', 'Before each pick, a passage loses some of its score for every passage already chosen from the same website, and a little more for the same document. One site, or one viewpoint, cannot take every place at the top.', ragDiverse],
    ['The evidence pool grows', 'New documents from each round are added to the same pool, and a document that is already there is never added twice. The ranking is recalculated over the whole pool, so late evidence competes fairly with early evidence.', ragPool],
    ['Every citation points to one passage', 'A passage is identified by its document and its position in it. The writer cites those passages, and each numbered citation on the page opens the exact text it came from.', ragCite],
    ['The audit reuses the same pool', 'Each claim in the final answer is checked against the passages the agent actually read, so a verdict can always be traced to text you can open. A pasted answer is checked against evidence retrieved for your question in the same way.', ragAudit]
  ];
  function inside() {
    return section('rag', 'ld-rag', [
      title('rag', 'Inside our RAG system',
        'Retrieval is our own code, not a search box bolted on. This is what happens to every document, in plain words.'),
      h('ol', { class: 'ld-rag-list' }, RAG_STEPS.map(function (st, i) {
        return h('li', { class: 'ld-rag-row' },
          h('div', { class: 'ld-rag-text' }, h('span', { class: 'ld-idea-n' }, '0' + (i + 1)), h('h3', null, st[0]), h('p', null, st[1])),
          h('div', { class: 'ld-idea-fig' }, st[2]()));
      }))
    ]);
  }

  /* ---------- see inside every answer ---------- */
  function miniMap() {
    var claims = [22, 48, 74], srcs = [12, 32, 52, 72, 92];
    var edges = [[0, 0, 'support'], [0, 1, 'support'], [1, 1, 'contradict'], [1, 2, 'support'], [2, 3, 'mixed'], [2, 4, 'support']];
    var s = '';
    edges.forEach(function (e) {
      s += '<path d="M72 ' + claims[e[0]] + ' C130 ' + claims[e[0]] + ' 130 ' + srcs[e[1]] + ' 188 ' + srcs[e[1]] + '" fill="none" stroke="var(--' + e[2] + ')" stroke-width="1.5" stroke-linecap="round"/>';
    });
    claims.forEach(function (y) { s += '<rect x="8" y="' + (y - 9) + '" width="64" height="18" rx="4" class="ld-po"/><rect x="14" y="' + (y - 2) + '" width="40" height="4" rx="2" class="ld-sk-r"/>'; });
    srcs.forEach(function (y) { s += '<circle cx="194" cy="' + y + '" r="6" class="ld-po"/>'; });
    s += '<text class="ld-mini-t" x="40" y="104" text-anchor="middle">claims</text><text class="ld-mini-t" x="194" y="108" text-anchor="middle">sources</text>';
    return mini('Claims on the left joined by coloured lines to the sources that back or challenge them', s);
  }
  function miniJourney() {
    var xs = [30, 86, 142, 198], ys = [74, 62, 36, 28];
    var s = '<path d="M16 88 H226" class="ld-hair-s"/><polyline points="' + xs.map(function (x, i) { return x + ',' + ys[i]; }).join(' ') + '" class="ld-line ld-nomark"/>';
    xs.forEach(function (x, i) {
      s += '<circle cx="' + x + '" cy="' + ys[i] + '" r="4" class="ld-dotf"/><text class="ld-mini-t" x="' + x + '" y="102" text-anchor="middle">round ' + (i + 1) + '</text>';
    });
    s += '<path d="M170 20 V88" class="ld-line is-guard ld-thin" stroke-dasharray="4 3"/><text class="ld-mini-t ld-mini-g" x="170" y="14" text-anchor="middle">guard steps in</text>';
    s += '<text class="ld-mini-t" x="16" y="14">belief</text>';
    return mini('A belief line across four rounds, with a marker where the balance guard stepped in', s);
  }
  function miniMade() {
    var cols = [[8, 'chatbot', 1], [86, 'typical RAG', 2], [164, 'ours', 4]], s = '';
    cols.forEach(function (c, ci) {
      s += '<text class="ld-mini-t' + (ci === 2 ? ' ld-mini-g' : '') + '" x="' + (c[0] + 34) + '" y="14" text-anchor="middle">' + c[1] + '</text>';
      if (ci === 2) s += '<rect x="' + c[0] + '" y="22" width="68" height="84" rx="5" fill="none" stroke="var(--brass)" stroke-width="1.25"/>';
      for (var r = 0; r < 4; r++) {
        var y = 32 + r * 18;
        s += r < c[2] ? '<rect x="' + (c[0] + 8) + '" y="' + y + '" width="52" height="8" rx="3" class="' + (ci === 2 ? 'ld-brass-f' : 'ld-sk-r') + '"/>'
                      : '<rect x="' + (c[0] + 8) + '" y="' + y + '" width="52" height="8" rx="3" class="ld-po" stroke-dasharray="3 2"/>';
      }
    });
    return mini('Three columns, a chatbot, a typical RAG search and ours, with more of the process visible in ours', s);
  }
  function seeInside() {
    function item(num, name, fig, text) {
      return h('article', { class: 'ld-idea' }, h('div', { class: 'ld-idea-fig' }, fig), h('span', { class: 'ld-idea-n' }, num), h('h3', null, name), h('p', null, text));
    }
    return section('inside', 'ld-inside', [
      title('inside', 'See inside every answer',
        'An answer is only the last step. Three views open up the rest of it.'),
      h('div', { class: 'ld-idea-grid' },
        item('01', 'Evidence map', miniMap(), 'Every claim is joined to the passages that back it or push against it, so you can see which claims rest on several sources and which on one.'),
        item('02', 'Belief journey', miniJourney(), 'Follow the agent round by round: what it believed, what it searched for next, and the moment the balance guard added a counter-search.'),
        item('03', 'How this answer was made', miniMade(), 'A button on every answer opens the real figures for that run, and shows how it differs from a typical chatbot and from a typical RAG search.'))
    ]);
  }

  /* ---------- three ideas ---------- */
  function miniBaqd() {
    return frag('<svg class="ld-mini" viewBox="0 0 240 110" role="img" aria-label="A line rising round by round and crossing a dashed threshold">' +
      '<path d="M24 14 V92 H226" class="ld-hair-s"/>' +
      '<path d="M24 38 H226" class="ld-line is-guard ld-thin" stroke-dasharray="5 4"/>' +
      '<polyline points="40,82 80,76 120,64 160,44 200,26" class="ld-line ld-nomark"/>' +
      '<g class="ld-pts"><circle cx="40" cy="82" r="3.5"/><circle cx="80" cy="76" r="3.5"/><circle cx="120" cy="64" r="3.5"/><circle cx="160" cy="44" r="3.5"/><circle cx="200" cy="26" r="5" class="is-hit"/></g>' +
      '<text class="ld-mini-t" x="30" y="32">threshold</text>' +
      '<text class="ld-mini-t" x="226" y="106" text-anchor="end">round</text>' +
      '<text class="ld-mini-t" x="20" y="14" text-anchor="end">drift</text></svg>');
  }
  function miniCqi() {
    function row(y, label, items) {
      var s = '<text class="ld-mini-t" x="4" y="' + (y - 6) + '">' + label + '</text>';
      items.forEach(function (k, i) {
        s += '<rect x="' + (4 + i * 44) + '" y="' + y + '" width="38" height="22" rx="3" class="' + (k ? 'ld-blk-a' : 'ld-blk-b') + '"/>';
      });
      return s;
    }
    return frag('<svg class="ld-mini" viewBox="0 0 240 110" role="img" aria-label="Evidence blocks that all lean one way, then a counter-query adds opposing blocks">' +
      row(22, 'before: one-sided', [1, 1, 1, 1, 1]) +
      '<path d="M120 52 V66" class="ld-line is-guard ld-thin" marker-end="url(#ld-mini-arb)"/>' +
      row(88, 'after the counter-query', [1, 1, 1, 0, 0]) +
      '<defs><marker id="ld-mini-arb" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M1.5 1.5L8 5L1.5 8.5" class="ld-ar is-guard"/></marker></defs></svg>');
  }
  var VERDICTS = [['support', 'supported'], ['contradict', 'contradicted'], ['mixed', 'mixed'], ['neutral', 'not verified']];
  function claimRows(widths, big) {
    var s = '';
    VERDICTS.forEach(function (v, i) {
      var y = 12 + i * 24;
      s += '<circle cx="10" cy="' + (y + 6) + '" r="5" fill="var(--' + v[0] + ')"/>' +
           '<rect x="26" y="' + (y + 1) + '" width="' + widths[i] + '" height="10" rx="3" class="ld-sk-r"/>' +
           '<text class="ld-mini-t" x="236" y="' + (y + 10) + '" text-anchor="end">' + v[1] + '</text>';
    });
    return s;
  }
  function miniAudit() {
    return frag('<svg class="ld-mini" viewBox="0 0 240 110" role="img" aria-label="Four claims, each with a verdict dot: supported, contradicted, mixed, not verified">' + claimRows([92, 70, 84, 62]) + '</svg>');
  }

  function ideas() {
    function idea(num, name, svg, text) {
      return h('article', { class: 'ld-idea' }, h('div', { class: 'ld-idea-fig' }, svg), h('span', { class: 'ld-idea-n' }, num), h('h3', null, name), h('p', null, text));
    }
    var formula = frag('<div class="ld-formula" role="group" aria-label="The BAQD formula">' +
      '<div class="ld-fx"><span class="ld-fn">BAQD(n)</span><span class="ld-eq">=</span>' +
      '<span class="ld-term">cos(q<sub>n</sub>, belief<sub>n&minus;1</sub>)</span><span class="ld-eq">&minus;</span>' +
      '<span class="ld-term">cos(q<sub>0</sub>, belief<sub>n&minus;1</sub>)</span></div>' +
      '<p>In words: how much closer the agent’s next search is to what it already believes than the original question is. When that gap, or the skew in the evidence, crosses a threshold, the guard adds a counter-query.</p></div>');
    return section('ideas', 'ld-ideas', [
      title('ideas', 'Three ideas that make it different'),
      h('div', { class: 'ld-idea-grid' },
        idea('01', 'BAQD, measure the drift', miniBaqd(), 'Belief-Aligned Query Drift measures how far each new search leans toward what the agent already believes instead of the question.'),
        idea('02', 'Counter-Query Injection', miniCqi(), 'When the searches or the evidence lean one way, the guard adds a search that looks for opposing evidence.'),
        idea('03', 'Claim-level audit', miniAudit(), 'Every claim in the answer is checked against the retrieved passages and given one of four verdicts.')),
      formula
    ]);
  }

  /* ---------- check any AI answer ---------- */
  function checkAny() {
    var claims = frag('<figure class="ld-claims"><svg viewBox="0 0 240 110" role="img" aria-label="Wireframe of a claim list with a verdict dot beside each claim">' +
      claimRows([100, 78, 92, 66]) + '</svg><figcaption>An illustration of a claim list.</figcaption></figure>');
    return section('check', 'ld-check', h('div', { class: 'ld-split' },
      h('div', null,
        h('h2', { id: 'check-h', class: 'ld-h2' }, 'Check any AI’s answer'),
        h('p', { class: 'ld-lead' }, 'Paste an answer from ChatGPT, Claude or Gemini, or any other assistant, with the question you asked. Ouroboros retrieves its own evidence and checks each claim in the answer against it.'),
        h('p', { class: 'ld-lead' }, 'You get a verdict for every claim, and the share of claims the evidence backs. It tells you what is backed, not whether the answer is true.'),
        h('p', { class: 'ld-actions ld-actions-l' }, h('a', { class: 'btn btn-outline', href: O.href('/audit') }, 'Check an AI answer'))),
      claims));
  }

  /* ---------- honest results ---------- */
  function results() {
    return section('results', 'ld-results', [
      title('results', 'Honest results', 'We report what we found, including the parts that did not work.'),
      h('div', { class: 'ld-res' },
        h('div', { class: 'ld-res-col' },
          h('span', { class: 'ld-tag' }, 'Phase I'),
          h('h3', null, 'Scripted queries: a null result'),
          h('p', null, 'In the first study the searches were written in advance, so the agent never chose its own next search. We saw no effect. That is why we built the live loop, where the agent writes each search itself.')),
        h('div', { class: 'ld-res-col' },
          h('span', { class: 'ld-tag' }, 'Phase II'),
          h('h3', null, 'The live platform'),
          h('p', null, 'This site. In the live comparison of balanced search against standard search on a small closed corpus we did not see a difference yet. The next step is a larger corpus.'))),
      h('p', { class: 'ld-more' }, h('a', { class: 'ld-textlink', href: O.href('/benchmark') }, ['Read the full results', O.icon('arrow-right', 16)]))
    ]);
  }

  /* ---------- final call and footer ---------- */
  function finalCta() {
    return h('section', { class: 'ld-final', 'aria-labelledby': 'final-h' }, h('div', { class: 'ld-wrap' },
      h('h2', { id: 'final-h', class: 'ld-h2' }, 'Ask a question. See what the evidence says.'),
      h('div', { class: 'ld-actions' },
        h('a', { class: 'btn btn-primary btn-lg', href: O.href('/ask') }, 'Start researching'),
        h('a', { class: 'ld-textlink', href: O.href('/audit') }, ['Check an AI answer', O.icon('arrow-right', 16)]))));
  }
  function foot() {
    return h('footer', { class: 'ld-foot' }, h('div', { class: 'ld-wrap' },
      h('div', { class: 'ld-foot-top' },
        h('span', { class: 'ld-foot-brand' }, O.logo(18), h('span', { class: 'wordmark' }, 'Ouroboros')),
        h('nav', { class: 'ld-foot-nav', 'aria-label': 'Pages' },
          h('a', { href: O.href('/ask') }, 'Ask'), h('a', { href: O.href('/audit') }, 'Check an AI answer'), h('a', { href: O.href('/compare') }, 'Compare'),
          h('a', { href: O.href('/benchmark') }, 'Benchmark'), h('a', { href: O.href('/how') }, 'How it works'))),
      h('p', null, 'Ouroboros, a final-year project. The Evidence Support Score is the share of an answer’s claims backed by the evidence we retrieved. It does not say whether an answer is true.')));
  }

  function build(el) {
    el.append(h('div', { class: 'ld' }, topbar(), h('main', { class: 'ld-main', id: 'main' }, hero(), problem(), connected(), inside(), ideas(), seeInside(), checkAny(), results(), finalCta()), foot()));
  }

  function boot() {
    var host = document.getElementById('landing');
    if (!host) return;
    build(host);
    if (location.hash.length > 1) {
      var t = document.getElementById(decodeURIComponent(location.hash.slice(1)));
      if (t) t.scrollIntoView();
    }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
})();
