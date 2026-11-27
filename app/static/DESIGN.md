# Ouroboros design system

Identity: "Ouroboros. Research answers you can check." A calm, quiet, premium brown look, like a leather notebook in a university library. Minimal by rule: hairlines and whitespace instead of cards and badges, one accent. Plain HTML, CSS and JS. No framework, no build step.

## Files and owners
- index.html, css/tokens.css, css/base.css, js/core.js, img/: FOUNDATION.
- css/home.css, css/thread.css, js/home.js, js/thread.js: HOME and THREAD.
- css/pages.css, js/pages.js: PAGES (audit, compare, benchmark, how).
- landing.html, css/landing.css, js/landing.js: LANDING, a separate standalone document served at `/` (own head, tokens.css, base.css, landing.css, landing.js, a tiny theme script reading `ouro-theme`). It does not load core.js; landing.js carries small copies of the h/logo/arrow helpers. Its links go into the app at `/app#/ask`, `/app#/audit`, `/app#/benchmark`, `/app#/how`.
- Routes: `/` landing, `/app` the chat SPA (hash routes `/app#/ask`, `/app#/r/<id>`, `/app#/audit`, `#/compare`, `#/benchmark`, `#/how`; an empty hash or unknown route goes to `#/ask`), `/favicon.ico` the 64px PNG. The sidebar has a quiet "About Ouroboros" link to `/`.
- Add `?mock=1` to the address to replay fixtures in app/static/mock with no server.
- Script order is fixed: core, home, thread, pages. Page scripts call `O.route()` while loading. Boot runs on DOMContentLoaded.

## Rules
- Never write a raw colour. Use tokens from tokens.css. Dark mode redefines tokens only, so no `@media dark` in page CSS.
- Semantic colours (support green, contradict red, mixed amber, neutral grey) mean evidence only. Brown and brass are brand.
- Minimal rules: one accent (saddle brown `--primary`) for the one primary button, links, the active tab underline and the active nav item. Brass is only the focus ring. No cards: use hairlines (`--line`) and space. Shadows only on the composer, popovers and toasts. At most one filled primary control per screen. `.card`, `.pill`, `.badge`, `.note`, `.eyebrow` degrade to hairline or plain-text forms (`.badge` and `.eyebrow` are hidden).
- Avoid: teal, purple, blue gradients, neon, glass, emoji, gradients on heroes, a shadow on every block, centring everything.
- 16px root, 15px body, answer text 16px, reading width 66ch (`--measure`). Tap targets 44px (`--tap`). Visible brass focus ring is global.
- Respect reduced motion (global rule exists).
- Copy: plain friendly English, no em dashes, no "->" arrows, no emoji. Never name the model, provider, key or sign-in. The score is "the share of the answer's claims backed by the evidence we retrieved", never accuracy or "% correct". Unsupported is "not verified", never "false". Every number comes from real data.
- Internal words to avoid on screen: guarded (say "Balanced search"), hop (say "round" in prose; "Hop n" is fine in the Research steps tab and charts), CQI (say "counter-search"), BAQD only with an explanation.

## Tokens (tokens.css)
Colour: --ground --surface --surface-2 --ink --ink-2 --muted --line --line-strong --primary --primary-hover --primary-soft --on-primary --brass --focus --sidebar* --support(-soft) --contradict(-soft) --mixed(-soft) --neutral(-soft) --av-1..6 --overlay --code-bg.
Type: --font-serif (Newsreader, headings and hero), --font-sans (Figtree, UI), --font-mono (JetBrains Mono, queries and ids). Sizes --text-xs/sm/base/answer/lg/xl/2xl/3xl/hero.
Space --s-1..--s-9 (4, 8, 12, 16, 24, 32, 56, 96, 140). Radii --r-sm 6, --r 10, --r-lg 14, --r-xl 20, --r-pill. Shadows --shadow-1 (none) /2 (composer) /3 (popovers). Layout --sidebar-w 248px, --topbar-h 52px, --tap. Serif headings are weight 400 with -0.02em tracking. The sidebar is a warm stone panel in light and near-black in dark.
Theme: `:root` light; dark via `@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) }` and `:root[data-theme="dark"]`. Toggle in the sidebar (three icon buttons: Auto, Light, Dark), saved in localStorage key `ouro-theme`.

## Components (base.css class names)
Layout: `.page` and `.page-narrow` (one 840px column, 728px of content, gutters 56 / 16 on phones, 96px top air; every screen shares this left edge, `.pg-wide` lets wide content opt out), `.page-head` (h1 + lead p), `.eyebrow`, `.card`, `.card-flat`, `.card-soft`, `.card-title`, `.row`, `.stack`, `.stack-lg`, `.grow`, `.between`, `.center`, `.muted`, `.small`, `.serif`, `.hide-sm`, `.only-sm`, `.sr`.
Buttons: `.btn`, `.btn-primary`, `.btn-soft`, `.btn-quiet`, `.btn-lg`, `.btn-icon`, `.btn-ask` (round arrow), `.btn-link`.
Forms: `.field`, `.field-label`, `.hint`, `.input`, `.textarea`, `.select`, `.seg` (radio options as plain text with the chosen one underlined: `<fieldset class="seg"><label><input type=radio><span>Label</span></label></fieldset>`), `.switch`, `.chips` + `.chip` (plain text options), `.ex-list` + `.ex-item` (hairline example question rows, one `<li><button class="ex-item">` each, used on Home and Compare), `.opt-btn` + `.opt-menu` (the composer options line).
Status: `.pill` + `.pill-support|contradict|mixed|neutral|primary`, `.pill.v-<verdict>`, `.pill.g-well|partly|weak|contra`, `.grade-pill`, `.badge` + `.badge-guarded|standard|counter`, `.note` (+ `.note-warn`, `.note-info`), `.run-error`, `.honesty`, `.spinner`, `.skeleton`, `.toast`.
Evidence: `.evidence-card` (O.evidenceCard), `.ring` (O.scoreRing), `.claim-list` + `.claim-card.v-<verdict>` (O.claimCards), `.source-row` + `.source-card` + `.src-badge|src-domain|src-num|src-title|src-meta` (O.sourceRow/O.sourceCard), `.cite` (numbered chip), `.popover`, `.answer` (O.answerBlock), `.steps` (O.steps), `.bal` and `.bar` (O.balanceBar, O.baqdBar), `.tabs` + `.tab` (O.tabs), `.composer` (O.composer: a textarea and a round send button; Balanced search and Depth live in one quiet "Balanced, Standard" menu, same `{guarded, depth, hops}` output).
Data: `.tbl-wrap table` (right-align numbers with `.num`), `.formula`, `.prose`, `.chart` + `.chart-legend` (O.lineChart), `.pass`, `.fail`, `.flash` (highlight after a citation jump).
Shell: `.app` grid, `.sidebar` (`.sb-*`), `.topbar` (phones), `.main-col`, `#view` holding one `section.view` per route (`.is-active` shows it), `.site-foot`, `.mock-banner`.

## JS API
The full list with signatures is the header comment of js/core.js. Summary: O.h, O.svg, O.clear, O.esc, O.fmt/pct/plural/safeUrl/trunc/sleep, O.api, O.postJSON, O.sse, O.recordToEvents, O.runSummary, O.route, O.go, O.href, O.startThread, O.takePending, O.openRun, O.logo, O.icon, O.gradePill, O.verdictPill, O.modeBadge, O.scoreRing, O.evidenceCard, O.claimCards, O.sourceCard, O.sourceRow, O.domainBadge, O.balanceBar, O.baqdBar, O.steps, O.tabs, O.composer, O.answerBlock, O.Citations, O.citationsFromRun, O.popover, O.lineChart, O.watchResize, O.refreshRuns, O.theme, O.health, O.toast.

Router: `O.route('name', {title, init(el), show(el, params), hide(el)})`. `init` runs once per page, `show` on every entry (also when `O.go` is called for the hash already showing). Pages stay mounted, so a running stream keeps going while someone looks at another page. Routes: ask `#/ask` (also the empty hash), thread `#/thread`, saved run `#/r/<run_id>` (params.id), audit, compare, benchmark, how.
Ask flow: home composer `onSubmit(q, {guarded, depth, hops})` calls `O.startThread({question: q, guarded, hops})`. Thread `show()` calls `O.takePending()`; mode is `guarded ? 'guarded' : 'standard'`. After a run finishes call `O.refreshRuns()`.
Citations: build one `O.Citations` per thread. `add` every passage from `hop_read` events, call `setAnswer(synthesis.answer)` when the answer arrives, then render with `answerBlock` and `sourceRow`. Source cards and passage list items must carry `data-pid="<pid>"` so chips can jump to them. Set `cites.onJump` to switch tabs first when the target is in a hidden tab, return true to skip the default scroll.

## Event stream (GET /api/research/stream?q=&mode=guarded|standard&hops=1..6)
JSON events, same shape as `O.recordToEvents(run)` for saved runs:
- start {question, mode, config{hops,baqd_threshold,skew_threshold,...}}
- hop_query {hop, query, origin: question|model|counter}
- hop_sources {hop, fetched{wikipedia,openalex,arxiv,pubmed,web}, pool_size}
- hop_read {hop, passages[{pid,title,url,domain,source,year,text,stance,reason}], belief, confidence, next_query}
- hop_metrics {hop, baqd (null at hop 1), support, contradict, neutral, skew, balance_loss, domains, sources}
- cqi {hop, trigger{baqd,skew}, original_query, counter_query, why}
- synthesis {answer (with [pid] citations), confidence, one_line}
- audit {report: {claims[{cid,text,verdict,note,evidence[{pid,relation,title,url,domain,source}],independent_sources}], scores{evidence_support_score,multi_source_share,contradicted_share,unverified_share,citation_faithfulness,distinct_domains,calibration_gap,stated_confidence}, grade, pool_size}}
- done {run_id, usage, seconds} (usage is internal: do not show model names, tokens or cost)
- error {message} (plain words already)
Compare: /api/compare/stream sends the same events with `lane: standard|guarded`, then compare_done {summary{standard,guarded}}.
Other: POST /api/audit {question, answer, model_name} returns the report. POST /api/plain {question} returns {answer, confidence, audit}. GET /api/runs, /api/runs/<id>, /api/benchmark, /api/tests. The server still has /api/code endpoints, but the UI never calls them: no code, file names or paths are shown anywhere.
Status mapping for the five thread steps: 0 Searching sources = start / hop_query / hop_sources; 1 Reading passages = hop_read; 2 Checking the search for bias = hop_metrics / cqi; 3 Writing the answer = after the last hop_metrics until synthesis; 4 Checking every claim = synthesis until audit; finish on done.

## Wireframes
Shell (desktop): 240px sidebar (logo + wordmark, outlined "New question", nav x4: Check an AI answer, Compare, Benchmark, How it works; Recent list of at most six one-line titles, deduped by question, grade and time in the tooltip only; three theme icons; status dot with text only when offline) | main column (page, footer). Phones: top bar (logo, menu button) and the sidebar as a left drawer with a scrim; the drawer closes on link, scrim, close button and Escape.

Home (ask page): no logo lockup in the middle (the sidebar logo stays); serif H1 in two lines ("Ask a question." / "See what the evidence says." in a softer tone), one-line subtitle, composer (textarea, options line, round send button), the six example questions as a hairline `.ex-list`, one line of links (Check an AI answer, How it works), footer. Nothing else: the sources, steps and score meaning live on How it works and in the footer.

Thread: one 728px column. Serif question, one status line, serif lead sentence, the answer with numbered citations, one hairline Evidence block (ring, grade word, one line of facts, a Details disclosure that also holds the stated-confidence sentence), then plain tabs Sources / Research steps / Evidence report | sticky "Ask a follow-up" composer at the bottom. The grade also considers how many independent websites back each claim, so a score of 100 can read "Partly supported, but few sources agree".

Check an AI answer: page head | model chips (ChatGPT, Claude, Gemini, Other) | question input | answer textarea | "Check this answer" and secondary "Get an unguarded answer to compare" | report: Evidence card + claim cards. One prefilled example.

Compare: question + examples | two lanes split by a hairline (Standard, Balanced; the subtitles reserve two lines so both Evidence blocks start at the same height) | side-by-side table with the honest one-example caveat.

Benchmark: "Read this first" note | Phase I null result | Phase II live experiment, reported honestly | charts and tables.

How it works: plain words intro | pipeline diagram | user-flow wireflow (Ask, Search 5 source types, Rank passages with our RAG, Read and update belief, Bias check, Counter-search when needed with loop back, Write answer, Check each claim, Evidence report, Follow-up) | BAQD in words | one quiet line with the automated-check count. No code, file names or paths anywhere in the UI.

## Logo
Bronze ribbon mark from the user's own artwork, transparent PNGs in img/ (logo-mark.png, logo-mark-320.png, logo-mark-128.png, favicon-32/64.png, apple-touch-icon.png), rendered by `O.logo(height, {word, rule})` in core.js. Wordmark OUROBOROS in Jost 400/500, tracked 0.3em, colour `--ink` (`--font-logo`); the hero lockup adds a brass rule with a double-slash ornament (`.logo-rule`).


## Landing page
Served at `/` as landing.html. Sections in order (sections 3b and 4b are new):
1. Hero: bronze mark and wordmark lockup (96px mark), serif headline "Research you can check." up to 44px, two actions, and a wireframe of the answer screen labelled as an illustration (real placeholder question, no invented numbers).
2. The problem: two short columns and a small loop figure (search, belief, next search).
3. How everything is connected: the system diagram (inline SVG; horizontal 900x710 on desktop, vertical 360x1040 on phones and tablets). Numbered nodes 1 to 11 plus A for a pasted answer, with a numbered legend underneath. Main path in ink, balance guard path in brass, pasted answer dashed. The evidence pool feeds the claim audit; the counter-query returns to all five sources. Animated dots are off under reduced motion.
3b. Inside our RAG system: six plain-words steps (documents become passages, two scores BM25 and TF-IDF, diversity re-ranking, the pool grows, every citation points to one passage, the audit reuses the pool), each with a small wireframe. No code or file names.
4. Three ideas (BAQD, counter-query injection, claim-level audit) with mini wireframes and the BAQD formula.
4b. See inside every answer: Evidence map, Belief journey and How this answer was made, three short items with wireframes.
5. Check any AI's answer.
6. Honest results (Phase I null result, Phase II live platform, no difference yet on the small closed corpus).
7. Call to action and footer.
Numbers are real constants only (five source types, 2 to 6 rounds, four verdicts). The top bar links to How it works, Check an AI answer and Results (on phones only How it works), and Start researching.
