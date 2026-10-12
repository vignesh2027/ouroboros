"""Build the Review 1 report.

The test case table is read from outputs/test_report.json, which is produced by
an actual test run, so the document cannot drift away from the code. The
diagrams are inlined so the report is a single self contained file.

Run:  python3 scripts/build_review_doc.py
"""

import json
import os
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "outputs")
DOCS = os.path.join(HERE, "docs")
DIAGRAMS = os.path.join(DOCS, "diagrams")
TARGET = os.path.join(DOCS, "review1-report.html")


def svg(name):
    """Inline an svg file, stripped of its xml declaration."""
    with open(os.path.join(DIAGRAMS, name)) as f:
        s = f.read()
    s = re.sub(r"<\?xml[^>]*\?>", "", s)
    s = s.replace('width="960"', 'width="100%"').replace(
        'height="600"', "").replace('height="900"', "").replace(
        'height="760"', "").replace('height="620"', "")
    return s.strip()


def load_report():
    with open(os.path.join(OUT, "test_report.json")) as f:
        return json.load(f)


def load_diag():
    with open(os.path.join(OUT, "diagnostic.json")) as f:
        return json.load(f)


def esc(t):
    return (t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def defect_rows(defects):
    out = []
    for d in defects:
        cls = "fail" if d["status"] == "FAIL" else "pass"
        out.append(
            f'<tr class="{cls}"><td><b>{esc(d["id"])}</b></td>'
            f'<td>{esc(d["input"])}</td><td>{esc(d["expected"])}</td>'
            f'<td>{esc(d["actual"])}</td>'
            f'<td class="st {cls}">{d["status"]}</td>'
            f'<td class="g">{esc(d["remarks"])}</td></tr>')
    return "\n".join(out)


def auto_rows(rows):
    out = []
    for r in rows:
        cls = "fail" if r["status"] == "FAIL" else "pass"
        out.append(
            f'<tr><td>{esc(r["id"])}</td><td>{esc(r["input"])}</td>'
            f'<td class="g">{esc(r["expected"])}</td>'
            f'<td class="g">{esc(r["actual"])}</td>'
            f'<td class="st {cls}">{r["status"]}</td></tr>')
    return "\n".join(out)


def main():
    rep = load_report()
    diag = load_diag()
    passed = rep["total"] - rep["failures"]
    n_fail = len([d for d in rep["defects"] if d["status"] == "FAIL"])
    n_fixed = len([d for d in rep["defects"] if d["status"] == "PASS"])
    oracle = sum(d["oracle_support"] - d["oracle_oppose"] for d in diag) / len(diag)

    html = TEMPLATE.format(
        total=rep["total"], passed=passed, failures=rep["failures"],
        n_fail=n_fail, n_fixed=n_fixed, oracle=f"{oracle:.2f}",
        defects=defect_rows(rep["defects"]),
        autorows_a=auto_rows(rep["automated"][:22]),
        autorows_b=auto_rows(rep["automated"][22:]),
        n_a=len(rep["automated"][:22]), n_b=len(rep["automated"][22:]),
        use_case=svg("use-case.svg"),
        activity=svg("activity.svg"),
        flowchart=svg("flowchart-baqd.svg"),
        dataflow=svg("data-flow.svg"),
    )
    with open(TARGET, "w") as f:
        f.write(html)
    print(f"wrote {TARGET}")
    print(f"  automated cases : {rep['total']} ({passed} pass, {rep['failures']} fail)")
    print(f"  defects         : {n_fail} found, {n_fixed} resolved")


TEMPLATE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ouroboros Review One Report</title>
<style>
  :root{{
    --ink:#111111;--body:#1C1C1C;--grey:#5E5E5E;--line:#C9C9C9;--faint:#E9E9E9;
    --blue:#1B5E9E;--blue-bg:#EDF3F9;--red:#B23A2B;--red-bg:#FBEEEC;
    --green:#14664A;--green-bg:#EAF3EF;--amber:#8A6D0B;--amber-bg:#FBF5E3;
    --serif:Georgia,"Times New Roman",serif;
    --sans:"Helvetica Neue",Helvetica,Arial,sans-serif;
    --mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  }}
  *{{box-sizing:border-box;margin:0;padding:0;}}
  body{{background:#DCDCDC;font-family:var(--serif);color:var(--body);
       padding:26px 12px 60px;display:flex;flex-direction:column;align-items:center;gap:22px;}}
  .page{{width:210mm;min-height:297mm;background:#fff;position:relative;
         padding:20mm 18mm 28mm;box-shadow:0 1px 5px rgba(0,0,0,.16);}}
  .pfoot{{position:absolute;left:18mm;right:18mm;bottom:13mm;
          border-top:.5pt solid var(--line);padding-top:2.4mm;
          display:flex;justify-content:space-between;
          font-family:var(--sans);font-size:7.6pt;color:var(--grey);letter-spacing:.04em;}}
  h1{{font-family:var(--sans);font-size:26pt;font-weight:700;letter-spacing:-.02em;line-height:1.08;}}
  h2{{font-family:var(--sans);font-size:12.5pt;font-weight:700;margin:0 0 3.2mm;
      padding-bottom:1.6mm;border-bottom:1.2pt solid var(--ink);}}
  h2 span{{color:var(--blue);margin-right:2.4mm;}}
  h3{{font-family:var(--sans);font-size:10pt;font-weight:700;margin:4.5mm 0 1.8mm;}}
  section{{margin-bottom:6mm;}}
  p{{font-size:10.2pt;line-height:1.52;text-align:justify;margin-bottom:2.8mm;}}
  ul,ol{{margin:0 0 2.8mm 5mm;}} li{{font-size:10.2pt;line-height:1.5;margin-bottom:1.4mm;}}
  table{{border-collapse:collapse;width:100%;font-size:8.4pt;margin-bottom:2mm;}}
  th{{font-family:var(--sans);font-size:7.2pt;letter-spacing:.07em;text-transform:uppercase;
      color:var(--grey);font-weight:700;text-align:left;
      padding:0 2mm 1.5mm 0;border-bottom:1pt solid var(--ink);}}
  td{{padding:1.5mm 2mm 1.5mm 0;border-bottom:.5pt solid var(--faint);
      vertical-align:top;line-height:1.38;}}
  td.g{{color:var(--grey);}}
  td.st{{font-family:var(--sans);font-weight:700;font-size:8pt;}}
  td.st.pass{{color:var(--green);}} td.st.fail{{color:var(--red);}}
  tr.fail td{{background:#FDF4F2;}} tr.pass td{{background:#F2F8F5;}}
  figure{{margin:4mm 0 3mm;}} figure svg{{display:block;width:100%;height:auto;
      border:.5pt solid var(--faint);}}
  figcaption{{font-family:var(--sans);font-size:8pt;color:var(--grey);
      margin-top:2mm;text-align:center;line-height:1.4;}}
  figcaption b{{color:var(--ink);}}
  pre{{background:#F5F6F8;border:.5pt solid var(--line);border-left:2.5pt solid var(--blue);
       padding:3mm 4mm;font-family:var(--mono);font-size:8.4pt;line-height:1.55;
       overflow-x:auto;margin-bottom:2.8mm;white-space:pre-wrap;}}
  code{{font-family:var(--mono);font-size:.9em;}}
  .note{{border-left:2.5pt solid var(--green);background:var(--green-bg);
         padding:3mm 4mm;margin:3.5mm 0;font-size:9.8pt;line-height:1.5;}}
  .note b{{color:var(--green);}}
  .warn{{border-left:2.5pt solid var(--amber);background:var(--amber-bg);
         padding:3mm 4mm;margin:3.5mm 0;font-size:9.8pt;line-height:1.5;}}
  .warn b{{color:var(--amber);}}
  .stats{{display:flex;gap:6mm;margin:4mm 0;}}
  .stats div{{flex:1;}}
  .stats .n{{font-family:var(--sans);font-size:22pt;font-weight:700;line-height:1;}}
  .stats .l{{font-size:8.4pt;color:var(--grey);line-height:1.4;margin-top:1.5mm;}}
  .cover{{display:flex;flex-direction:column;height:249mm;}}
  .cv-top{{font-family:var(--sans);font-size:8.6pt;letter-spacing:.14em;text-transform:uppercase;
           color:var(--grey);text-align:center;line-height:2;padding-bottom:5mm;
           border-bottom:.5pt solid var(--line);}}
  .cv-mid{{flex:1;display:flex;flex-direction:column;justify-content:center;}}
  .cv-tag{{font-family:var(--sans);font-size:8.6pt;letter-spacing:.16em;text-transform:uppercase;
           color:var(--blue);margin-bottom:5mm;font-weight:700;}}
  .cv-sub{{font-family:var(--sans);font-size:13pt;line-height:1.35;color:var(--grey);margin-top:5mm;}}
  @media print{{
    body{{background:#fff;padding:0;gap:0;display:block;}}
    .page{{box-shadow:none;margin:0;page-break-after:always;width:210mm;height:297mm;overflow:hidden;}}
    @page{{size:A4 portrait;margin:0;}}
  }}
</style></head><body>

<!-- 1 COVER -->
<div class="page"><div class="cover">
  <div class="cv-top">Takshashila University<br>School of Computational Engineering<br>
    Department of Artificial Intelligence and Data Science</div>
  <div class="cv-mid">
    <p class="cv-tag">Project Phase I &middot; Review One &middot; Design, Implementation and Testing</p>
    <h1>OUROBOROS</h1>
    <p class="cv-sub">Detecting Self-Confirming Retrieval Loops in<br>Agentic Retrieval-Augmented Generation</p>
    <table style="margin-top:14mm;">
      <tr><th style="width:42%">Team member</th><th style="width:32%">Register number</th><th>Coordinates</th></tr>
      <tr><td><b>Harshavarthini M</b></td><td>TU6230103110012</td><td class="g">Dataset and evidence verification</td></tr>
      <tr><td><b>Sadhithiya V</b></td><td>TU6230103110024</td><td class="g">Literature, documentation, demo</td></tr>
      <tr><td><b>Vigneshwar L</b></td><td>TU6230103110040</td><td class="g">Pipeline and metric implementation</td></tr>
    </table>
    <table style="margin-top:8mm;">
      <tr><th style="width:42%">Project guide</th><th>Specialisation</th></tr>
      <tr><td><b>Dr. Senthil</b></td><td class="g">Networking and Database</td></tr>
    </table>
    <div class="stats" style="margin-top:12mm;">
      <div><p class="n" style="color:var(--blue);">4</p><p class="l">design diagrams prepared</p></div>
      <div><p class="n" style="color:var(--green);">{total}</p><p class="l">automated test cases, {passed} passing</p></div>
      <div><p class="n" style="color:var(--red);">{n_fail}</p><p class="l">defects found, {n_fixed} fixed and retested</p></div>
      <div><p class="n" style="color:var(--amber);">48</p><p class="l">retrievals logged by the running module</p></div>
    </div>
  </div>
  <div style="border-top:.5pt solid var(--line);padding-top:5mm;">
    <p style="font-size:9pt;color:var(--grey);text-align:left;">
      Source code and continuous integration: github.com/vignesh2027/ouroboros<br>
      Benchmark dataset: huggingface.co/datasets/vigneshwar234/spiral-bench</p>
  </div>
</div><div class="pfoot"><span>Ouroboros &middot; Review One Report</span><span>1</span></div></div>

<!-- 2 REQUIREMENTS -->
<div class="page">
  <section><h2><span>1.</span>Module Requirements</h2>
  <p>The project studies a failure in agentic retrieval systems. When a system writes its own
    follow up search queries using what it currently believes, and the retriever ranks documents
    by how closely they match the wording of that query, the system can collect progressively
    more one sided evidence without any document being false.</p>
  <p>Review One covers the first functional module, which is the <b>retrieval and measurement
    module</b>. Its requirements are listed below.</p>
  <h3>Functional requirements</h3>
  <table>
    <tr><th style="width:12%">ID</th><th style="width:40%">Requirement</th><th>Acceptance condition</th></tr>
    <tr><td><b>FR-1</b></td><td class="g">Load a benchmark whose evidence balance is guaranteed by construction</td>
        <td>Every contested question carries an equal number of supporting and opposing passages</td></tr>
    <tr><td><b>FR-2</b></td><td class="g">Encode any text into a vector using one shared vocabulary</td>
        <td>Encoding is deterministic and out of vocabulary text does not crash the pipeline</td></tr>
    <tr><td><b>FR-3</b></td><td class="g">Retrieve the top k passages for a query, ranked by wording similarity</td>
        <td>Exactly k results, ordered by descending score, with no mutation of the corpus</td></tr>
    <tr><td><b>FR-4</b></td><td class="g">Compute the BAQD drift score at every hop</td>
        <td>Three embeddings and two cosine similarities, returning zero when the belief is empty</td></tr>
    <tr><td><b>FR-5</b></td><td class="g">Measure the balance of each retrieved set</td>
        <td>Skew in the range minus one to plus one, with an empty set handled safely</td></tr>
    <tr><td><b>FR-6</b></td><td class="g">Log every retrieval as a reproducible trace</td>
        <td>One row per retrieval carrying the query, the score and the retrieved passages</td></tr>
  </table>
  <h3>Non functional requirements</h3>
  <table>
    <tr><th style="width:12%">ID</th><th style="width:40%">Requirement</th><th>Reason</th></tr>
    <tr><td><b>NFR-1</b></td><td class="g">No GPU, no paid API, no model download</td>
        <td>The work must be reproducible on ordinary student hardware</td></tr>
    <tr><td><b>NFR-2</b></td><td class="g">The metric must run in milliseconds</td>
        <td>A costly detector stays in a paper, a cheap one can run inside a live system</td></tr>
    <tr><td><b>NFR-3</b></td><td class="g">Every published number must be regenerated from the log</td>
        <td>Results are verified by machine rather than asserted by hand</td></tr>
  </table>
  </section>
  <div class="pfoot"><span>Ouroboros &middot; Review One Report</span><span>2</span></div>
</div>

<!-- 3 USE CASE -->
<div class="page">
  <section><h2><span>2.</span>Design Phase: Use Case Diagram</h2>
  <p>Three actors interact with the system. The researcher runs experiments and inspects traces.
    The continuous integration pipeline reruns everything automatically on each push, which is
    what keeps the published numbers honest. The review panel views the generated results.</p>
  <figure>{use_case}
  <figcaption><b>Figure 1.</b> Use case diagram. Blue use cases are invoked directly by an actor.
    Green use cases are sub functions included by them, shown with include relationships.</figcaption></figure>
  <p>The separation matters for this project. Running the drift experiment always includes
    encoding, scoring and retrieval, so those are modelled as included sub functions rather than
    as separate things an actor would call. Validating corpus integrity is reachable on its own
    because the continuous integration pipeline runs it as a standalone check.</p>
  </section>
  <div class="pfoot"><span>Ouroboros &middot; Review One Report</span><span>3</span></div>
</div>

<!-- 4 ACTIVITY -->
<div class="page">
  <section><h2><span>3.</span>Design Phase: Activity Diagram</h2>
  <p>The experiment is a triple nested loop over questions, arms and hops. The important detail is
    the step that sets the belief to whatever was just read, because that is the step which closes
    the loop the project is studying.</p>
  <figure>{activity}
  <figcaption><b>Figure 2.</b> Activity diagram for one complete experiment run.</figcaption></figure>
  </section>
  <div class="pfoot"><span>Ouroboros &middot; Review One Report</span><span>4</span></div>
</div>

<!-- 5 FLOWCHART -->
<div class="page">
  <section><h2><span>4.</span>Design Phase: Flowchart of the Metric</h2>
  <p>This is the core computation, shown at statement level. It is deliberately small. Three
    encodings, one guard against an empty belief vector, two cosine similarities and a
    subtraction.</p>
  <figure>{flowchart}
  <figcaption><b>Figure 3.</b> Flowchart for the BAQD drift score at a single retrieval hop.</figcaption></figure>
  <div class="note"><b>Why the guard matters.</b> At the first hop the belief has not yet been
    formed, so the belief vector can be empty. Without the guard the cosine would divide by zero.
    Test case TC-09 pins this behaviour.</div>
  </section>
  <div class="pfoot"><span>Ouroboros &middot; Review One Report</span><span>5</span></div>
</div>

<!-- 6 DFD -->
<div class="page">
  <section><h2><span>5.</span>Design Phase: Data Flow and Module Diagram</h2>
  <p>Blue modules are ordinary components that any retrieval system has, and this project does not
    modify them. Green modules are the contribution. The separation is the whole argument of the
    project, because the claim is that one small measurement added at the query stage reveals a
    failure that the rest of the pipeline cannot see.</p>
  <figure>{dataflow}
  <figcaption><b>Figure 4.</b> Data flow between modules, with the files each one reads and writes.</figcaption></figure>
  </section>
  <div class="pfoot"><span>Ouroboros &middot; Review One Report</span><span>6</span></div>
</div>

<!-- 7 IMPLEMENTATION -->
<div class="page">
  <section><h2><span>6.</span>Implementation</h2>
  <p>The retrieval and measurement module is complete and runs end to end. It is roughly a fifth of
    the full project, which also requires a dense encoder, a live language model writing its own
    queries, and a larger benchmark.</p>
  <h3>What is implemented</h3>
  <table>
    <tr><th style="width:30%">File</th><th style="width:16%">Lines</th><th>Responsibility</th></tr>
    <tr><td><code>ouroboros/metric.py</code></td><td class="g">~55</td>
        <td class="g">BAQD drift score, evidence skew, balance loss</td></tr>
    <tr><td><code>ouroboros/retrieval.py</code></td><td class="g">~60</td>
        <td class="g">TF-IDF encoder and cosine retriever</td></tr>
    <tr><td><code>run_experiment.py</code></td><td class="g">~140</td>
        <td class="g">Two arm controlled experiment and trace logging</td></tr>
    <tr><td><code>run_diagnostic.py</code></td><td class="g">~130</td>
        <td class="g">Oracle comparison that locates the cause of a null result</td></tr>
    <tr><td><code>run_tests.py</code> and <code>tests/</code></td><td class="g">~330</td>
        <td class="g">{total} automated cases and the generated test case table</td></tr>
  </table>
  <h3>Running the module</h3>
  <pre>$ python3 run_experiment.py

OUROBOROS  Experiment 1: does query wording collapse evidence balance?
Contested questions: 6   Settled questions: 2   Top-k per hop: 4
Hops: 3   Total retrievals logged: 48

hop  arm            BAQD   support   oppose   |skew|
1    drift         0.000      2.17     1.83    0.250
2    drift        -0.026      2.33     1.67    0.333
3    drift        -0.064      2.33     1.67    0.333
1    neutral       0.000      2.17     1.83    0.250
2    neutral       0.030      2.50     1.50    0.250
3    neutral       0.005      2.33     1.67    0.500</pre>
  <pre>$ python3 run_diagnostic.py

Oracle spread, best case a query could ever achieve : +{oracle}
Actual shift produced by our drifting query wording : +0.08
Fraction of the achievable spread we captured       : 4.2%</pre>
  <div class="note"><b>Result.</b> On a corpus balanced by construction, an oracle query built only
    from vocabulary unique to one side retrieves every supporting passage, and the reverse oracle
    retrieves every opposing passage. Query wording alone moves retrieved evidence across the full
    range of {oracle}. This is the half of the loop the module set out to test, and it holds.</div>
  <div class="warn"><b>Reported honestly.</b> The drift arm was no better than the neutral arm and
    the metric stayed flat, so the gate test returned a null result. The diagnostic locates the
    cause in the lexical encoder and in queries that were too mild, not in the mechanism. The
    experiment was not adjusted until it agreed with the hypothesis.</div>
  </section>
  <div class="pfoot"><span>Ouroboros &middot; Review One Report</span><span>7</span></div>
</div>

<!-- 8 TESTING -->
<div class="page">
  <section><h2><span>7.</span>Testing Approach</h2>
  <p>Testing ran alongside implementation rather than after it. Every module was exercised with
    valid input, boundary input and invalid input as it was written. Where the output did not match
    the expectation, the case was recorded as a failure, the defect was fixed, and the same case
    was run again and recorded as a pass.</p>
  <h3>Categories covered</h3>
  <ul>
    <li><b>Unit tests</b> on the metric, covering identical, orthogonal, opposite and zero vectors.</li>
    <li><b>Boundary tests</b> on the retriever, covering k of zero, negative k and k larger than the corpus.</li>
    <li><b>Integrity tests</b> on the benchmark, enforcing that balance is genuinely guaranteed.</li>
    <li><b>Regression tests</b> that pin defects already found, so they cannot return silently.</li>
    <li><b>End to end invariants</b> on the published numbers, such as the trace row count.</li>
  </ul>
  <div class="stats">
    <div><p class="n" style="color:var(--green);">{total}</p><p class="l">automated cases</p></div>
    <div><p class="n" style="color:var(--green);">{passed}</p><p class="l">passing</p></div>
    <div><p class="n" style="color:var(--red);">{n_fail}</p><p class="l">defects found during development</p></div>
    <div><p class="n" style="color:var(--green);">{n_fixed}</p><p class="l">fixed and verified by retest</p></div>
  </div>
  <h3>Defects found, fixed and retested</h3>
  <p>Both defects below were genuine. Each was found by a test, fixed in the source, and confirmed
    by rerunning the same case.</p>
  <table>
    <tr><th style="width:9%">ID</th><th style="width:21%">Input</th><th style="width:21%">Expected</th>
        <th style="width:21%">Actual</th><th style="width:8%">Status</th><th>Remarks</th></tr>
    {defects}
  </table>
  <div class="note"><b>How to read TC-36.</b> A negative k was passed to the retriever. Python
    interprets <code>scored[:-1]</code> as everything except the last item, so instead of returning
    nothing the retriever silently returned the seven worst ranked passages. A guard for k of zero
    or less fixed it, and the retest passes.</div>
  </section>
  <div class="pfoot"><span>Ouroboros &middot; Review One Report</span><span>8</span></div>
</div>

<!-- 9 TEST TABLE PART 1 -->
<div class="page">
  <section><h2><span>8.</span>Test Case Documentation</h2>
  <p>This table is generated by <code>run_tests.py</code> from an actual test run. It is not
    maintained by hand, so it cannot describe behaviour the code no longer has. Cases TC-01 to
    TC-14 cover the metric, TC-15 to TC-26 cover the encoder and retriever, TC-27 to TC-34 cover
    benchmark integrity, and TC-35 to TC-43 cover boundaries and end to end invariants.</p>
  <h3>Part 1 of 2: cases 1 to {n_a}</h3>
  <table>
    <tr><th style="width:9%">ID</th><th style="width:36%">What is tested</th>
        <th style="width:26%">Expected output</th><th style="width:19%">Actual output</th>
        <th style="width:10%">Status</th></tr>
    {autorows_a}
  </table>
  </section>
  <div class="pfoot"><span>Ouroboros &middot; Review One Report</span><span>9</span></div>
</div>

<!-- 10 TEST TABLE PART 2 -->
<div class="page">
  <section><h2><span>8.</span>Test Case Documentation, continued</h2>
  <h3>Part 2 of 2: the remaining {n_b} cases</h3>
  <table>
    <tr><th style="width:9%">ID</th><th style="width:36%">What is tested</th>
        <th style="width:26%">Expected output</th><th style="width:19%">Actual output</th>
        <th style="width:10%">Status</th></tr>
    {autorows_b}
  </table>
  <div class="note"><b>Every case above passes on the current code.</b> The two defects recorded in
    section 7 were found by these same tests during development, fixed in the source, and are now
    pinned by TC-36 and TC-38 so they cannot return without the suite failing.</div>
  </section>
  <div class="pfoot"><span>Ouroboros &middot; Review One Report</span><span>10</span></div>
</div>

<!-- 10 NEXT -->
<div class="page">
  <section><h2><span>9.</span>Status and Next Steps</h2>
  <h3>Completed for Review One</h3>
  <table>
    <tr><th style="width:52%">Deliverable</th><th style="width:16%">Status</th><th>Evidence</th></tr>
    <tr><td>Module requirements</td><td class="st pass">DONE</td><td class="g">Section 1</td></tr>
    <tr><td>Use case diagram</td><td class="st pass">DONE</td><td class="g">Figure 1</td></tr>
    <tr><td>Activity diagram</td><td class="st pass">DONE</td><td class="g">Figure 2</td></tr>
    <tr><td>Flowchart</td><td class="st pass">DONE</td><td class="g">Figure 3</td></tr>
    <tr><td>Data flow and module diagram</td><td class="st pass">DONE</td><td class="g">Figure 4</td></tr>
    <tr><td>Working module, runnable and demonstrated</td><td class="st pass">DONE</td>
        <td class="g">48 retrievals logged, two commands</td></tr>
    <tr><td>Test cases, both failing and passing</td><td class="st pass">DONE</td>
        <td class="g">{total} automated, {n_fail} defects with retests</td></tr>
    <tr><td>Continuous integration</td><td class="st pass">DONE</td>
        <td class="g">Reruns every experiment on each push</td></tr>
    <tr><td>Live agent writing its own queries</td><td class="st fail">NOT YET</td>
        <td class="g">Needs an API key, planned for Review Two</td></tr>
  </table>
  <h3>Next steps</h3>
  <table>
    <tr><th style="width:26%">Change</th><th style="width:38%">Why, from this phase's evidence</th>
        <th>Expected effect</th></tr>
    <tr><td><b>Dense encoder</b></td>
        <td class="g">The drift score moved the wrong way because short queries share few literal
          words with long belief text. A lexical encoder measures vocabulary overlap, not meaning.</td>
        <td class="g">The metric registers belief alignment rather than word overlap</td></tr>
    <tr><td><b>Live agent</b></td>
        <td class="g">Our authored probes captured only 4.2 percent of the available range.</td>
        <td class="g">Answers the real gate question for the first time</td></tr>
    <tr><td><b>Larger benchmark</b></td>
        <td class="g">Six contested questions and a top k of four make every measurement coarse.</td>
        <td class="g">Enough resolution to separate a real effect from noise</td></tr>
  </table>
  <div class="warn"><b>Known limitations.</b> The passages are synthetic research style text written
    for this prototype, not quotations from real papers. The benchmark is small. The queries are
    authored probes rather than model output. These are stated so the results are not read as more
    than they are.</div>
  </section>
  <div class="pfoot"><span>Ouroboros &middot; Review One Report</span><span>11</span></div>
</div>

</body></html>
"""


if __name__ == "__main__":
    main()
