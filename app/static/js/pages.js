/* Pages: Check an AI answer (#/audit), Compare agents (#/compare), Benchmark (#/benchmark), How it works (#/how).
   Uses only the shared O.* helpers from core.js. Styles are in css/pages.css (prefix pg-). */
(function () {
  'use strict';
  var h = O.h;

  /* ---------- small shared bits ---------- */
  function pageHead(title, lead) {
    return h('header', { class: 'page-head' }, h('h1', null, title), lead ? h('p', null, lead) : null);
  }
  function errorBox(msg) { return h('div', { class: 'run-error', role: 'alert' }, msg); }
  function busyBox(msg) { return h('div', { class: 'pg-busy', role: 'status' }, O.spinner(), h('span', null, msg)); }
  /* One quiet line of numbers in place of a row of tiles. */
  function statLine(pairs) {
    return h('p', { class: 'pg-statline' }, pairs.map(function (p) { return p[0] + ' ' + p[1]; }).join(', '));
  }
  function num(v, d) { return O.isNum(v) ? String(Math.round(v * Math.pow(10, d == null ? 3 : d)) / Math.pow(10, d == null ? 3 : d)) : 'n/a'; }
  function section(title, lead, kids) {
    return h('section', { class: 'pg-section' }, h('h2', null, title), lead ? h('p', { class: 'pg-lead' }, lead) : null, kids);
  }
  function plural(n, w, pl) { return O.plural(n, w, pl); }

  /* =====================================================================
     CHECK AN AI ANSWER
     ===================================================================== */
  var EXAMPLE_ANSWER = 'Intermittent fasting is one of the most effective ways to lose weight. Studies show it burns more body fat than ordinary calorie cutting, and it speeds up your metabolism by a large amount. It is safe for everyone, including people with diabetes.';

  function auditPage() {
    var token = 0, source = null; // source: null (a model chosen above) or 'plain'
    var seg = h('fieldset', { class: 'seg', 'aria-label': 'Which AI wrote the answer' },
      O.AI_MODELS.map(function (m, i) {
        return h('label', null, h('input', { type: 'radio', name: 'pg-model', value: m, checked: i === 0 }), h('span', null, m));
      }));
    var q = h('input', { class: 'input', id: 'pg-aq', type: 'text', maxlength: '500', placeholder: 'The question you asked the AI', value: O.EXAMPLES[0] });
    var a = h('textarea', { class: 'textarea', id: 'pg-aa', rows: '5', placeholder: 'Paste the answer here', maxlength: '12000' });
    a.value = EXAMPLE_ANSWER;
    var tag = h('span', { class: 'pill pill-primary', hidden: true }, 'Unguarded answer');
    var hintEx = h('p', { class: 'hint', id: 'pg-hint' }, 'Example text, replace it with an answer you want checked.');
    var btn = h('button', { type: 'submit', class: 'btn btn-primary btn-lg' }, 'Check this answer');
    var plain = h('button', { type: 'button', class: 'btn btn-quiet', title: 'A plain model answers with no search, so you can see how a typical AI answer compares.' }, 'Get an unguarded answer to compare');
    var out = h('div', { class: 'pg-report', 'aria-live': 'polite' });

    function chosen() { var r = seg.querySelector('input:checked'); return r ? r.value : 'Other'; }
    function setBusy(b) { btn.disabled = b; plain.disabled = b; }
    function userEdit() { source = null; tag.hidden = true; hintEx.hidden = true; }
    a.addEventListener('input', userEdit);

    function showReport(report, label, stated, note) {
      O.clear(out);
      out.append(h('h2', null, 'Report on ' + label));
      if (note) out.append(note);
      out.append(O.evBlock(report, { stated: stated }));
      var linked = (report.claims || []).some(function (c) { return (c.evidence || []).length; });
      if (linked) out.append(h('h3', { class: 'pg-claims-h' }, 'Evidence map'),
        h('p', { class: 'pg-map-lead' }, 'Which sources back which claims. Claims with no line found nothing that covers them.'), O.evidenceMap(report));
      out.append(h('h3', { class: 'pg-claims-h' }, 'Claim by claim'), O.claimRows(report));
      out.scrollIntoView({ behavior: O.REDUCED ? 'auto' : 'smooth', block: 'start' });
    }
    function fail(err, what) { O.clear(out).append(errorBox(what + ' ' + O.friendlyError(err))); setBusy(false); }

    var form = h('form', { class: 'pg-form', novalidate: true },
      h('div', { class: 'field' }, h('span', { class: 'field-label', id: 'pg-model-l' }, 'Which AI wrote it?'), seg),
      h('div', { class: 'field' }, h('label', { class: 'field-label', for: 'pg-aq' }, 'The question'), q),
      h('div', { class: 'field' },
        h('div', { class: 'row between' }, h('label', { class: 'field-label', for: 'pg-aa' }, 'The answer to check'), tag),
        a, hintEx),
      h('div', { class: 'row pg-actions' }, btn, plain));

    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var qq = q.value.trim(), aa = a.value.trim();
      if (!qq) { q.focus(); O.clear(out).append(errorBox('Type the question first.')); return; }
      if (!aa) { a.focus(); O.clear(out).append(errorBox('Paste the answer you want to check.')); return; }
      var my = ++token; setBusy(true);
      var label = source === 'plain' ? 'the unguarded answer' : chosen() + '’s answer';
      O.clear(out).append(busyBox('Splitting the answer into claims, then searching for evidence on each one.'));
      O.postJSON('/api/audit', { question: qq, answer: aa, model_name: source === 'plain' ? 'Other' : chosen() }).then(function (rep) {
        if (my !== token) return;
        showReport(rep.report || rep, label, rep.stated_confidence); setBusy(false);
      }).catch(function (err) { if (my === token) fail(err, 'The check could not finish.'); });
    });

    plain.addEventListener('click', function () {
      var qq = q.value.trim();
      if (!qq) { q.focus(); O.clear(out).append(errorBox('Type the question first, then ask for an unguarded answer.')); return; }
      var my = ++token; setBusy(true);
      O.clear(out).append(busyBox('Getting an answer with no search, then checking it.'));
      O.postJSON('/api/plain', { question: qq }).then(function (r) {
        if (my !== token) return;
        a.value = r.answer || ''; source = 'plain'; tag.hidden = false; hintEx.hidden = true;
        var rep = r.audit || r.report;
        if (!rep) { fail(new Error('No report came back.'), 'The check could not finish.'); return; }
        var note = h('div', { class: 'note note-info' }, 'This answer came from a plain model with no search' + (O.isNum(r.confidence) ? '. It said it was ' + Math.round(r.confidence) + '% sure.' : '.') + ' It is now in the answer box, so you can edit it and check again.');
        showReport(rep, 'the unguarded answer', r.confidence, note); setBusy(false);
      }).catch(function (err) { if (my === token) fail(err, 'We could not get an unguarded answer.'); });
    });

    return h('div', { class: 'page page-narrow' },
      pageHead('Check an AI answer', 'We split the answer into claims, look for evidence, and mark each one backed, contradicted, mixed or not verified.'),
      form, out);
  }

  /* =====================================================================
     COMPARE
     ===================================================================== */
  var COMPARE_EXAMPLES = [O.EXAMPLES[0], O.EXAMPLES[2]];

  function makeLane(mode) {
    var cites = new O.Citations(), rounds = {}, nRounds = 0, nCqi = 0, report = null, finished = false;
    var status = h('div', { class: 'pg-lane-status' });
    var list = h('ol', { class: 'pg-rounds' });
    var foldSum = h('summary', null, 'Searches');
    var fold = h('details', { class: 'pg-fold', hidden: true }, foldSum, list);
    var answerHost = h('div', { class: 'pg-lane-answer' });
    var evHost = h('div', { class: 'pg-lane-ev' });
    var el = h('section', { class: 'pg-lane pg-lane-' + mode, 'aria-label': O.MODE_LABEL[mode] },
      h('h2', null, O.MODE_LABEL[mode]),
      h('p', { class: 'pg-lane-sub' }, mode === 'guarded' ? 'Swaps in an opposing search when the evidence leans one way.' : 'Follows its own next search every round, with no check.'),
      status, evHost, answerHost, fold);
    function setStatus(t, busy) { O.clear(status); if (t) { if (busy) status.append(O.spinner()); status.append(h('span', null, t)); } }
    function sumText() { foldSum.textContent = 'Searches, ' + plural(nRounds, 'round') + (nCqi ? ', ' + plural(nCqi, 'counter-search', 'counter-searches') : ''); }
    function reset() { cites = new O.Citations(); rounds = {}; nRounds = 0; nCqi = 0; report = null; finished = false; O.clear(list); O.clear(answerHost); O.clear(evHost); fold.hidden = true; fold.open = false; setStatus('Waiting to start', true); }
    function round(n) { return rounds[n]; }
    function handle(ev) {
      switch (ev.type) {
        case 'hop_query':
          setStatus('Round ' + ev.hop + ': searching', true);
          var meta = h('div', { class: 'pg-round-meta' });
          var li = h('li', { class: 'pg-round' + (ev.origin === 'counter' ? ' is-counter' : '') },
            h('div', { class: 'pg-round-top' }, h('strong', null, 'Round ' + ev.hop), ev.origin === 'counter' ? h('span', { class: 'pg-round-tag' }, 'Counter-search') : null),
            h('code', { class: 'pg-query' }, ev.query), meta);
          rounds[ev.hop] = { li: li, meta: meta }; list.append(li);
          nRounds = Math.max(nRounds, ev.hop); fold.hidden = false; sumText(); break;
        case 'hop_read':
          cites.addAll(ev.passages); setStatus('Round ' + ev.hop + ': reading', true);
          if (round(ev.hop)) round(ev.hop).meta.append(h('span', null, plural((ev.passages || []).length, 'passage') + ' read'));
          break;
        case 'hop_metrics':
          setStatus('Round ' + ev.hop + ': checking for bias', true);
          if (round(ev.hop)) {
            var m = round(ev.hop).meta;
            m.append(h('span', null, ev.support + ' for, ' + ev.contradict + ' against, ' + ev.neutral + ' neutral'));
            if (O.isNum(ev.baqd)) m.append(h('span', { title: 'Query drift (BAQD): how far this search moved toward the agent’s own belief' }, 'Drift ' + ev.baqd.toFixed(3)));
            round(ev.hop).li.append(O.balanceBar(ev.support, ev.neutral, ev.contradict));
          }
          break;
        case 'cqi':
          nCqi++; sumText();
          if (round(ev.hop)) round(ev.hop).li.append(h('div', { class: 'pg-cqi' }, h('strong', null, 'Balance check fired. '), ev.why || 'The next search is swapped for an opposing one.'));
          break;
        case 'synthesis':
          cites.setAnswer(ev.answer); setStatus('Checking every claim', true);
          O.clear(answerHost).append(O.answerBlock(ev.answer, cites));
          break;
        case 'audit':
          report = ev.report; O.clear(evHost).append(O.evBlock(report, { mode: mode })); break;
        case 'done': finished = true; setStatus('', false); break;
        case 'error': finished = true; O.clear(status).append(errorBox(ev.message || 'Something went wrong.')); break;
      }
    }
    return { el: el, reset: reset, handle: handle, setStatus: setStatus, report: function () { return report; }, finished: function () { return finished; } };
  }

  function comparePage() {
    var lanes = { standard: makeLane('standard'), guarded: makeLane('guarded') };
    var stream = null;
    var q = h('input', { class: 'input', id: 'pg-cq', type: 'text', maxlength: '500', 'aria-label': 'Question', placeholder: 'Ask a question to run both agents on it', value: COMPARE_EXAMPLES[0] });
    var go = h('button', { type: 'submit', class: 'btn btn-primary btn-lg', title: 'A new question runs both agents live, so it takes longer than a saved example.' }, 'Compare');
    var stop = h('button', { type: 'button', class: 'btn btn-quiet', hidden: true }, 'Stop');
    var tableHost = h('div', { class: 'pg-table-host' });
    var lanesEl = h('div', { class: 'pg-lanes', hidden: true }, lanes.standard.el, lanes.guarded.el);

    var examples = h('ul', { class: 'ex-list', 'aria-label': 'Saved examples' }, COMPARE_EXAMPLES.map(function (t) {
      return h('li', null, h('button', { type: 'button', class: 'ex-item', onclick: function () { q.value = t; q.focus(); } }, h('span', null, t), O.icon('arrow-right', 18)));
    }));
    var form = h('form', { class: 'pg-form', novalidate: true },
      q, examples,
      h('div', { class: 'row pg-actions' }, go, stop));

    function summaryTable(sum) {
      var S = sum.standard || {}, G = sum.guarded || {};
      function contra(k) { var r = lanes[k].report(); return r && r.scores ? O.pct(r.scores.contradicted_share, 0) : 'n/a'; }
      function score(k) { var r = lanes[k].report(); return r && r.scores && O.isNum(r.scores.evidence_support_score) ? Math.round(r.scores.evidence_support_score) + '%' : O.pct(sum[k] && sum[k].evidence_support_score, 0); }
      function n(v) { return O.isNum(v) ? String(v) : 'n/a'; }
      var rows = [
        ['Evidence Support Score', 'Share of the answer’s claims backed by the evidence', score('standard'), score('guarded')],
        ['Claims contradicted', 'Share of claims the evidence pushes against', contra('standard'), contra('guarded')],
        ['Counter-searches', 'Times an opposing search was swapped in', n(S.cqi_count), n(G.cqi_count)],
        ['Websites read', 'Different websites among the passages used', n(S.domains_total), n(G.domains_total)],
        ['Query drift (BAQD), average', 'How far searches bent toward the agent’s belief, rounds 2 on', O.fmt(S.mean_baqd, 3), O.fmt(G.mean_baqd, 3)],
        ['Query drift (BAQD), highest', 'The single most drifted search', O.fmt(S.max_baqd, 3), O.fmt(G.max_baqd, 3)],
        ['Final evidence lean', 'Backing minus opposing passages in the last round, from minus 1 to 1', O.fmt(S.final_skew, 2), O.fmt(G.final_skew, 2)]
      ];
      O.clear(tableHost).append(h('section', { class: 'pg-cmp' },
        h('h2', null, 'Side by side'),
        h('div', { class: 'tbl-wrap' }, h('table', null,
          h('thead', null, h('tr', null, h('th', null, 'Measure'), h('th', { class: 'num' }, 'Standard search'), h('th', { class: 'num' }, 'Balanced search'))),
          h('tbody', null, rows.map(function (r) {
            return h('tr', null, h('td', null, h('strong', null, r[0]), h('div', { class: 'pg-sub' }, r[1])), h('td', { class: 'num' }, r[2]), h('td', { class: 'num' }, r[3]));
          })))),
        h('p', { class: 'honesty' }, 'One question is one example, not a result. These numbers describe this pair of runs only. The lean and the counts come from the agent’s own reading of each passage. A higher score for one side here does not prove it is better in general.')));
    }
    function run() {
      var text = q.value.trim();
      if (!text) { q.focus(); return; }
      if (stream) stream.stop();
      lanes.standard.reset(); lanes.guarded.reset(); O.clear(tableHost); lanesEl.hidden = false;
      lanesEl.scrollIntoView({ behavior: O.REDUCED ? 'auto' : 'smooth', block: 'start' });
      go.disabled = true; stop.hidden = false;
      var s = stream = O.sse('/api/compare/stream?q=' + encodeURIComponent(text) + '&hops=4', function (ev) {
        if (ev.type === 'compare_done') { summaryTable(ev.summary || {}); O.refreshRuns && O.refreshRuns(); return; }
        var l = lanes[ev.lane];
        if (l) l.handle(ev);
        else if (ev.type === 'error') { lanes.standard.handle(ev); lanes.guarded.handle(ev); }
      });
      s.done.catch(function (err) {
        var aborted = err && err.name === 'AbortError';
        ['standard', 'guarded'].forEach(function (k) {
          if (lanes[k].finished()) return;
          if (aborted) lanes[k].setStatus('Stopped', false); else lanes[k].handle({ type: 'error', message: O.friendlyError(err) });
        });
      }).then(function () { if (stream === s) { go.disabled = false; stop.hidden = true; stream = null; } });
    }
    form.addEventListener('submit', function (e) { e.preventDefault(); run(); });
    stop.addEventListener('click', function () { if (stream) stream.stop(); });

    var page = h('div', { class: 'page' },
      pageHead('Compare', 'Two agents answer the same question, one with the balance check.'),
      form, lanesEl, tableHost);
    page.stopRun = function () { if (stream) stream.stop(); };
    return page;
  }

  /* =====================================================================
     BENCHMARK
     ===================================================================== */
  var QLABELS = { ev_cost: 'Electric vehicle cost', vitamin_d: 'Vitamin D supplements', remote_work: 'Remote work', min_wage: 'Minimum wage', fasting: 'Intermittent fasting', nuclear: 'Nuclear power', smoking: 'Smoking and cancer', vaccines_measles: 'Measles vaccine' };
  function qLabel(id) { return QLABELS[id] || String(id).replace(/_/g, ' '); }
  var GROUP_LABEL = { 'contested/standard': 'Contested, standard search', 'contested/guarded': 'Contested, balanced search', 'settled/standard': 'Settled, standard search', 'settled/guarded': 'Settled, balanced search' };

  function legendItem(color, dash, text) {
    var s = O.svg('svg', { width: 28, height: 10, 'aria-hidden': 'true' });
    s.append(O.svg('line', { x1: 1, x2: 27, y1: 5, y2: 5, stroke: color, 'stroke-width': 3, 'stroke-dasharray': dash || 'none', 'stroke-linecap': 'round' }));
    return h('span', null, s, text);
  }

  function phase1(p1) {
    var sec = section('Phase I: scripted searches on a small fixed collection', null, []);
    sec.append(h('p', { class: 'pg-lead' }, 'The first version. The searches that were meant to drift were typed into a file in advance, and the passages came from a small fixed collection. ',
      h('strong', null, 'A null result. '), 'Because the searches were scripted, no agent ever wrote a search from its own belief, so the loop was never closed. These numbers test the measure and the benchmark, not whether real agents drift. Phase II was built to fix that.'));
    if (!p1) { sec.append(h('p', { class: 'muted' }, 'No Phase I results were found on the server.')); return sec; }
    sec.append(statLine([[String(p1.n_questions), 'questions'], [String(p1.hops), 'rounds each'], [String(p1.n_trace_rows), 'recorded searches'], [String((p1.arms || []).length), 'search styles']]));
    var means = Array.isArray(p1.mean_by_type_arm_hop) ? p1.mean_by_type_arm_hop : [];
    if (means.length) {
      var groups = {}, order = [];
      means.forEach(function (t) { var k = t.arm + '/' + t.type; if (!groups[k]) { groups[k] = []; order.push(k); } groups[k].push(t); });
      var colors = { contested: 'var(--primary)', settled: 'var(--neutral)' };
      var armName = { drift: 'Scripted drift searches', neutral: 'Neutral searches' };
      var maxHop = Math.max.apply(null, means.map(function (t) { return t.hop; }));
      function build(field) {
        return order.map(function (k) {
          var arm = k.split('/')[0], ty = k.split('/')[1];
          return { name: (armName[arm] || arm) + ', ' + ty + ' questions', color: colors[ty] || 'var(--ink-2)', dash: arm === 'neutral' ? '6 4' : null,
            points: groups[k].slice().sort(function (a, b) { return a.hop - b.hop; }).map(function (t) { return { x: t.hop, y: t[field] }; }) };
        });
      }
      var c1 = h('div'), c2 = h('div');
      var legend = h('div', { class: 'chart-legend' }, order.map(function (k) {
        var arm = k.split('/')[0], ty = k.split('/')[1];
        return legendItem(colors[ty] || 'var(--ink-2)', arm === 'neutral' ? '6 4' : null, (armName[arm] || arm) + ', ' + ty);
      }));
      var draw = function () {
        O.lineChart(c1, { series: build('mean_balance_loss'), xmin: 1, xmax: maxHop, yTitle: 'Balance loss', fixedY: [0, 1], aria: 'Average balance loss at each round, Phase I' });
        O.lineChart(c2, { series: build('mean_baqd'), xmin: 1, xmax: maxHop, yTitle: 'Query drift (BAQD)', aria: 'Average query drift at each round, Phase I' });
      };
      sec.append(h('div', { class: 'pg-grid2' },
        h('div', { class: 'pg-chart' }, h('p', { class: 'pg-chart-t' }, 'Balance loss at each round'), c1),
        h('div', { class: 'pg-chart' }, h('p', { class: 'pg-chart-t' }, 'Query drift at each round'), c2)), legend,
        h('p', { class: 'honesty' }, 'Each point averages the questions of one type. Balance loss is how far the passages found sit from an even split of backing and opposing ones: 0 is even, 1 is entirely one side. Settled questions are true claims, so a high balance loss there is correct. Dashed lines are the neutral searches.'));
      setTimeout(function () { draw(); O.watchResize(c1, draw); }, 0);
    }
    var diag = Array.isArray(p1.diagnostic) ? p1.diagnostic : (p1.diagnostic && p1.diagnostic.rows) || [];
    if (diag.length) {
      var cols = Object.keys(diag[0]);
      sec.append(h('div', { class: 'pg-block' }, h('h3', null, 'Does the measure separate opposing beliefs?'),
        h('p', { class: 'muted' }, 'A check on hand-picked beliefs. A measure that works should score a supporting belief and an opposing one differently.'),
        h('div', { class: 'tbl-wrap' }, h('table', null,
          h('thead', null, h('tr', null, cols.map(function (c) { return h('th', { class: c === 'id' ? '' : 'num' }, c === 'id' ? 'Question' : c.replace(/_/g, ' ')); }))),
          h('tbody', null, diag.map(function (r) { return h('tr', null, cols.map(function (c) { return h('td', { class: c === 'id' ? '' : 'num' }, c === 'id' ? qLabel(r[c]) : num(r[c])); })); }))))));
    }
    var fh = p1.final_hop_mean_balance_loss;
    if (fh && typeof fh === 'object') {
      var rows = [];
      Object.keys(fh).forEach(function (arm) { Object.keys(fh[arm]).forEach(function (ty) { rows.push(h('tr', null, h('td', null, armName[arm] || arm), h('td', null, ty), h('td', { class: 'num' }, O.fmt(fh[arm][ty], 2)))); }); });
      sec.append(h('div', { class: 'pg-block' }, h('h3', null, 'Balance loss at the last round'),
        h('div', { class: 'tbl-wrap' }, h('table', null, h('thead', null, h('tr', null, h('th', null, 'Search style'), h('th', null, 'Question type'), h('th', { class: 'num' }, 'Balance loss'))), h('tbody', null, rows)))));
    }
    return sec;
  }

  function phase2(p2) {
    var sec = section('Phase II: a live agent on the same collection',
      'A real model reads the passages, states a belief and writes its own next search. Standard and balanced runs are compared on each question. Balance loss here uses the correct labels stored in the benchmark file, not the model’s own judgement.', []);
    if (!p2) {
      sec.append(h('div', { class: 'note note-info' }, h('strong', null, 'Not run yet. '), 'There is no Phase II result on this machine yet, so there is nothing to show here.'));
      return sec;
    }
    var runs = Array.isArray(p2.runs) ? p2.runs : [];
    var sum = p2.summary && typeof p2.summary === 'object' ? p2.summary : {};
    var keys = Object.keys(sum).filter(function (g) { return sum[g] && typeof sum[g] === 'object'; });
    sec.append(statLine([[String(runs.length), 'runs'], [String(p2.hops), 'rounds each'], [String(p2.k), 'passages per round'], [String(keys.length ? 2 : 0), 'search modes']]));
    if (keys.length) {
      var cols = [['runs', 'Runs'], ['mean_last_hop_balance_loss', 'Last round'], ['mean_all_hop_balance_loss', 'All rounds'], ['mean_baqd_hops_2_4', 'Drift, rounds 2 to 4'], ['mean_cqi', 'Counter-searches'], ['mean_final_confidence', 'Confidence']];
      sec.append(h('div', { class: 'pg-block' }, h('h3', null, 'Results by question type and search mode'),
        h('div', { class: 'tbl-wrap' }, h('table', null,
          h('thead', null, h('tr', null, h('th', null, 'Group'), cols.map(function (c) { return h('th', { class: 'num' }, c[1]); }))),
          h('tbody', null, keys.map(function (g) { return h('tr', null, h('td', null, GROUP_LABEL[g] || g), cols.map(function (c) { return h('td', { class: 'num' }, num(sum[g][c[0]])); })); }))))));
    }
    if (p2.design_limitation) sec.append(h('div', { class: 'note note-warn pg-block', role: 'note' }, h('strong', null, 'Limit of this experiment. '), p2.design_limitation));
    var concl = (Array.isArray(p2.conclusions) ? p2.conclusions : []).filter(function (c) { return c !== p2.design_limitation; });
    if (concl.length) sec.append(h('div', { class: 'pg-block' }, h('h3', null, 'What the experiment reported'), h('ul', { class: 'pg-list' }, concl.map(function (c) { return h('li', null, c); })),
      h('p', { class: 'honesty' }, 'These lines come straight from the experiment’s own output file. Here, “guarded” means the balanced search and “CQI” means a counter-search.')));
    if (runs.length) {
      var rows = runs.map(function (r) {
        var hp = r.hops || [], bl = hp.map(function (x) { return x.true_balance_loss; }).filter(O.isNum);
        return h('tr', null, h('td', null, qLabel(r.qid)), h('td', null, r.type), h('td', null, O.MODE_LABEL[r.mode] || r.mode),
          h('td', { class: 'mono' }, hp.map(function (x, i) { return O.isNum(x.baqd) ? x.baqd.toFixed(3) : 'n/a'; }).join('  ')),
          h('td', { class: 'num' }, bl.length ? O.fmt(bl[bl.length - 1], 2) : 'n/a'),
          h('td', { class: 'num' }, O.isNum(r.cqi_count) ? String(r.cqi_count) : String((r.cqi_events || []).length)));
      });
      sec.append(h('details', { class: 'pg-fold pg-block' }, h('summary', null, 'Every run, one by one (' + runs.length + ')'),
        h('div', { class: 'tbl-wrap' }, h('table', null,
          h('thead', null, h('tr', null, h('th', null, 'Question'), h('th', null, 'Type'), h('th', null, 'Search mode'), h('th', null, 'Drift per round'), h('th', { class: 'num' }, 'Final balance loss'), h('th', { class: 'num' }, 'Counter-searches'))),
          h('tbody', null, rows)))));
    }
    return sec;
  }

  function readFirst(p2) {
    var sum = (p2 && p2.summary) || {}, cs = sum['contested/standard'], cg = sum['contested/guarded'];
    var same = cs && cg && O.isNum(cs.mean_last_hop_balance_loss) && O.isNum(cg.mean_last_hop_balance_loss);
    return h('div', { class: 'note note-warn pg-readfirst', role: 'note' },
      h('h2', null, 'Read this first'),
      h('ul', { class: 'pg-list' },
        h('li', null, 'Neither experiment shows the balanced agent beating the standard one. We report that as it is.'),
        h('li', null, 'Phase I used searches typed in advance, so it never tested a real agent. It tests the measure only.'),
        h('li', null, same
          ? 'In Phase II both modes ended with the same balance loss on contested questions (' + O.fmt(cs.mean_last_hop_balance_loss, 3) + ' for standard, ' + O.fmt(cg.mean_last_hop_balance_loss, 3) + ' for balanced). The small collection runs out of passages by round 4, so it cannot tell them apart.'
          : 'Phase II is a live experiment. Its collection is small, so it may not be able to tell the two modes apart.'),
        h('li', null, 'The next step is a much larger collection of passages, where a different search can actually change what is read.')));
  }

  function benchmarkPage() {
    var host = h('div', { class: 'pg-bench-body' }, busyBox('Loading results'));
    function load() {
      O.api('/api/benchmark').then(function (d) {
        d = d || {}; O.clear(host).append(readFirst(d.phase2), phase1(d.phase1), phase2(d.phase2));
      }).catch(function (err) { O.clear(host).append(errorBox('Could not load the results. ' + O.friendlyError(err))); loaded = false; });
    }
    var loaded = false;
    var el = h('div', { class: 'page' },
      pageHead('Benchmark', 'Two experiments test whether an agent’s searches drift toward its own belief, and whether the balance check helps. Here is what each one found, including what it could not show.'),
      host);
    return { el: el, ensure: function () { if (!loaded) { loaded = true; load(); } } };
  }

  /* =====================================================================
     HOW IT WORKS
     ===================================================================== */
  var NODES = [
    { n: 1, t: 'Ask a question', s: ['Type any question,', 'in plain words'] },
    { n: 2, t: 'Search 5 source types', s: ['Wikipedia, OpenAlex, arXiv,', 'PubMed and the open web'] },
    { n: 3, t: 'Rank the passages', s: ['Our own ranking scores', 'each passage found'] },
    { n: 4, t: 'Read and update belief', s: ['The agent notes what it', 'learned and plans its search'] },
    { n: 5, t: 'Bias check', s: ['Is the search drifting or', 'the evidence one-sided?'] },
    { n: 6, t: 'Counter-search if needed', s: ['Swap in a search for the', 'opposite view'] },
    { n: 7, t: 'Write the answer', s: ['Short, with numbered', 'sources beside each claim'] },
    { n: 8, t: 'Check each claim', s: ['Every claim is looked up in', 'the passages we found'] },
    { n: 9, t: 'Evidence report', s: ['Score, grade and a card', 'for every claim'] },
    { n: 10, t: 'Follow-up', s: ['Ask the next question in', 'the same conversation'] }
  ];
  // Three columns, four rows. Big enough that text stays readable when the diagram is scaled to fit.
  var NW = 250, NH = 116, GAPX = 40, GAPY = 58, X0 = 36, Y0 = 16;
  var GRID = [[0, 0], [1, 0], [2, 0], [2, 1], [1, 1], [0, 1], [1, 2], [2, 2], [2, 3], [1, 3]]; // [col, row] per step
  function nodePos(i) { return { x: X0 + GRID[i][0] * (NW + GAPX), y: Y0 + GRID[i][1] * (NH + GAPY) }; }
  function wireflowSvg() {
    var W = X0 * 2 + 3 * NW + 2 * GAPX, H = Y0 * 2 + 4 * NH + 3 * GAPY;
    var svg = O.svg('svg', { viewBox: '0 0 ' + W + ' ' + H, role: 'img', class: 'pg-wf', 'aria-label': 'User flow: ask, search five source types, rank, read, bias check, counter-search loop, write answer, check claims, evidence report, follow-up.' });
    var defs = O.svg('defs');
    var mk = O.svg('marker', { id: 'pg-ah', viewBox: '0 0 10 10', refX: 8.5, refY: 5, markerWidth: 8, markerHeight: 8, orient: 'auto' });
    mk.append(O.svg('path', { d: 'M0 1 L9 5 L0 9 z', class: 'wf-head' }));
    var mk2 = O.svg('marker', { id: 'pg-ah2', viewBox: '0 0 10 10', refX: 8.5, refY: 5, markerWidth: 8, markerHeight: 8, orient: 'auto' });
    mk2.append(O.svg('path', { d: 'M0 1 L9 5 L0 9 z', class: 'wf-head loop' }));
    defs.append(mk, mk2); svg.append(defs);
    function line(d, loop) { svg.append(O.svg('path', { d: d, class: 'wf-line' + (loop ? ' loop' : ''), 'marker-end': 'url(#' + (loop ? 'pg-ah2' : 'pg-ah') + ')' })); }
    function txt(x, y, s, cls, anchor) { svg.append(O.svg('text', { x: x, y: y, class: cls, 'text-anchor': anchor || 'start' }, s)); }
    var c = function (i) { var p = nodePos(i); return { l: p.x, r: p.x + NW, t: p.y, b: p.y + NH, cx: p.x + NW / 2, cy: p.y + NH / 2 }; };
    // arrows first so nodes sit on top
    line('M' + c(0).r + ' ' + c(0).cy + ' H' + (c(1).l - 2));
    line('M' + c(1).r + ' ' + c(1).cy + ' H' + (c(2).l - 2));
    line('M' + c(2).cx + ' ' + c(2).b + ' V' + (c(3).t - 2));          // rank to read
    line('M' + c(3).l + ' ' + c(3).cy + ' H' + (c(4).r + 2));          // read to bias check
    line('M' + c(4).l + ' ' + c(4).cy + ' H' + (c(5).r + 2));          // bias check to counter-search
    line('M' + c(4).cx + ' ' + c(4).b + ' V' + (c(6).t - 2));          // enough rounds: write answer
    txt(c(4).cx + 12, c(4).b + GAPY / 2 + 5, 'enough rounds done', 'wf-lbl');
    line('M' + c(6).r + ' ' + c(6).cy + ' H' + (c(7).l - 2));
    line('M' + c(7).cx + ' ' + c(7).b + ' V' + (c(8).t - 2));
    line('M' + c(8).l + ' ' + c(8).cy + ' H' + (c(9).r + 2));
    // counter-search loops back to the search step
    var ym = c(1).b + GAPY * 0.62;
    line('M' + c(5).cx + ' ' + c(5).t + ' V' + ym + ' H' + c(1).cx + ' V' + (c(1).b + 2), true);
    txt(c(5).cx + 12, ym - 8, 'search again with the opposite view', 'wf-lbl loop');
    // follow-up returns to ask
    line('M' + c(9).l + ' ' + c(9).cy + ' H14 V' + c(0).cy + ' H' + (c(0).l - 2), true);
    txt(X0 + 4, c(9).cy - 34, 'A follow-up goes back to step 1', 'wf-lbl loop');
    txt(X0 + 4, c(9).cy - 14, 'in the same thread', 'wf-lbl loop');
    // legend, in the empty corner
    var ly = c(6).t + 30;
    svg.append(O.svg('path', { d: 'M' + (X0 + 4) + ' ' + ly + ' H' + (X0 + 50), class: 'wf-line', 'marker-end': 'url(#pg-ah)' }));
    txt(X0 + 62, ly + 5, 'normal path', 'wf-lbl');
    svg.append(O.svg('path', { d: 'M' + (X0 + 4) + ' ' + (ly + 30) + ' H' + (X0 + 50), class: 'wf-line loop', 'marker-end': 'url(#pg-ah2)' }));
    txt(X0 + 62, ly + 35, 'loop back', 'wf-lbl');
    // nodes
    NODES.forEach(function (nd, i) {
      var p = nodePos(i), g = O.svg('g', { class: 'wf-node' + (i === 5 ? ' is-loop' : '') + (i === 8 ? ' is-final' : '') });
      g.append(O.svg('rect', { x: p.x, y: p.y, width: NW, height: NH, rx: 8 }));
      g.append(O.svg('circle', { cx: p.x + 26, cy: p.y + 26, r: 14, class: 'wf-num' }));
      g.append(O.svg('text', { x: p.x + 26, y: p.y + 32, 'text-anchor': 'middle', class: 'wf-numt' }, String(nd.n)));
      g.append(O.svg('text', { x: p.x + 16, y: p.y + 62, class: 'wf-title' }, nd.t));
      nd.s.forEach(function (ln, k) { g.append(O.svg('text', { x: p.x + 16, y: p.y + 84 + k * 19, class: 'wf-sub' }, ln)); });
      svg.append(g);
    });
    return svg;
  }
  function wireflowList() {
    return h('ol', { class: 'pg-wf-list' }, NODES.map(function (nd) {
      return h('li', null, h('span', { class: 'pg-mini-n' }, String(nd.n)), h('div', null, h('strong', null, nd.t), h('p', null, nd.s.join(' '))),
        nd.n === 6 ? h('div', { class: 'pg-wf-loop' }, 'Then go back to step 2 and search again with the opposite view.') : null,
        nd.n === 10 ? h('div', { class: 'pg-wf-loop' }, 'A follow-up goes back to step 1.') : null);
    }));
  }

  var STAGES = [
    ['Search', 'For each question the agent searches five kinds of source: Wikipedia, OpenAlex, arXiv, PubMed and the open web.'],
    ['Rank', 'Our own ranking scores every passage against the search, mixing word matching with a diversity step so the top results do not repeat each other.'],
    ['Read and plan', 'The agent reads the best passages, writes down what it now believes, and writes its own next search. This repeats for two to six rounds.'],
    ['Balance check', 'After each round we measure whether the next search is leaning toward the agent’s belief, and whether the evidence is one-sided. If so, a counter-search looks for the opposite view.'],
    ['Audit', 'The answer is written with numbered sources. Then every claim in it is looked up in the passages we found and marked supported, contradicted, mixed or not verified.']
  ];
  function sub(base, s) { return h('span', null, base, h('sub', null, s)); }

  function howPage() {
    var checkLine = h('p', { class: 'pg-checks muted small' });
    function renderTests(rep) {
      var auto = Array.isArray(rep.automated) ? rep.automated : [];
      var total = O.isNum(rep.total) ? rep.total : auto.length;
      var fails = O.isNum(rep.failures) ? rep.failures : auto.filter(function (t) { return String(t.status).toUpperCase() !== 'PASS'; }).length;
      if (!total) { checkLine.hidden = true; return; }
      checkLine.hidden = false;
      checkLine.textContent = fails ? (total - fails) + ' of ' + total + ' automated checks pass.' : total + ' automated checks pass.';
    }
    checkLine.hidden = true;

    var stageRow = h('ol', { class: 'pg-stages' }, STAGES.map(function (s, i) {
      return h('li', null, h('span', { class: 'pg-stage-n', 'aria-hidden': 'true' }, '0' + (i + 1)),
        h('div', null, h('div', { class: 'pg-stage-t' }, s[0]), h('p', null, s[1])));
    }));

    var baqd = h('div', { class: 'pg-math', role: 'math', 'aria-label': 'BAQD at round n equals the cosine of the round n search and the previous belief, minus the cosine of the original question and the previous belief.' },
      h('span', { class: 'pg-math-l' }, 'BAQD', h('sub', null, 'n')), h('span', { class: 'pg-math-op' }, '='),
      h('span', { class: 'pg-math-t' }, 'cos(', sub('search', 'n'), ', ', sub('belief', 'n−1'), ')'),
      h('span', { class: 'pg-math-t' }, h('span', { class: 'pg-math-op' }, '− '), 'cos(question, ', sub('belief', 'n−1'), ')'));
    var lean = h('div', { class: 'pg-math', role: 'math', 'aria-label': 'Lean equals backing minus opposing, divided by backing plus opposing.' },
      h('span', { class: 'pg-math-l' }, 'lean'), h('span', { class: 'pg-math-op' }, '='),
      h('span', { class: 'pg-frac' }, h('span', null, 'backing − opposing'), h('span', null, 'backing + opposing')));

    var el = h('div', { class: 'page' },
      pageHead('How it works', 'Ouroboros does not answer from memory. It searches, reads, checks itself for bias, writes a cited answer and then checks that answer against the evidence it found.'),
      section('The five stages', 'What happens between your question and the report.', stageRow),
      section('The user flow', 'From the moment you ask a question to the report you read at the end.', [
        h('div', { class: 'pg-wf-card' }, wireflowSvg(), wireflowList())]),
      section('Measuring drift', 'Why the name: a snake eating its own tail. The agent’s searches feed its belief, and its belief shapes its next search.', h('div', { class: 'pg-two' },
        h('div', { class: 'prose' },
          h('p', null, 'An agent that searches in rounds can slowly bend its own searches toward what it already believes. We measure this with BAQD, short for Belief-Aligned Query Drift.'),
          h('p', null, 'In plain words: each round the agent writes its next search. We ask how close that search is to the agent’s current belief, then subtract how close the original question was to that same belief. Near zero means the agent is still searching neutrally. A rising number means its searches are bending toward its belief.'),
          h('p', null, 'The balance check also looks at the evidence itself: backing passages minus opposing passages, divided by all of them. When drift is above 0.05, or the evidence leans 0.5 or more to one side, the balanced search swaps its next search for one that looks for the opposite view.')),
        h('div', { class: 'stack' },
          h('div', { class: 'pg-formula' }, h('div', { class: 'pg-formula-t' }, 'Query drift'), baqd),
          h('div', { class: 'pg-formula' }, h('div', { class: 'pg-formula-t' }, 'Evidence lean'), lean),
          h('div', { class: 'pg-formula' }, h('div', { class: 'pg-formula-t' }, 'Evidence Support Score'), h('p', { class: 'pg-score-def' }, 'The share of the answer’s claims backed by the evidence we retrieved. It is not the chance the answer is true.'))))),
      checkLine);

    return {
      el: el,
      ensure: function () {
        if (el.dataset.ready) return; el.dataset.ready = '1';
        var wide = window.matchMedia('(min-width: 1200px)');
        var svg = O.$('.pg-wf', el), list = O.$('.pg-wf-list', el);
        function fit() { svg.style.display = wide.matches ? 'block' : 'none'; list.style.display = wide.matches ? 'none' : 'block'; }
        fit(); if (wide.addEventListener) wide.addEventListener('change', fit);
        O.api('/api/tests').then(renderTests).catch(function () { checkLine.hidden = true; });
      }
    };
  }

  /* ---------- routes ---------- */
  O.route('audit', { title: 'Check an AI answer', init: function (el) { el.append(auditPage()); }, show: function () {} });
  O.route('compare', { title: 'Compare agents', init: function (el) { el._page = comparePage(); el.append(el._page); }, show: function () {}, hide: function (el) { if (el._page) el._page.stopRun(); } });
  var bench;
  O.route('benchmark', { title: 'Benchmark', init: function (el) { bench = benchmarkPage(); el.append(bench.el); }, show: function () { bench.ensure(); } });
  var how;
  O.route('how', { title: 'How it works', init: function (el) { how = howPage(); el.append(how.el); }, show: function () { how.ensure(); } });
})();
