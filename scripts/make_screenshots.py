"""Render the captured terminal output into screenshot images.

The text in evidence/raw_*.txt is real stdout from running the project. This
script only renders it, it never writes or edits the content.

Run:  python3 scripts/make_screenshots.py
"""

import html
import os
import re
import subprocess

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EV = os.path.join(HERE, "evidence")
CHROME = ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")

SHOTS = [
    ("tests", "raw_tests.txt", "python3 run_tests.py", 1180, "ok"),
    ("experiment", "raw_experiment.txt", "python3 run_experiment.py", 1180, "ok"),
    ("diagnostic", "raw_diagnostic.txt", "python3 run_diagnostic.py", 1180, "ok"),
    ("tc36_before", "raw_tc36_before_short.txt",
     "python3 -m unittest tests.test_experiment.TestRetrieverEdges -v   # guard removed",
     1020, "bad"),
    ("tc36_after", "raw_tc36_after_short.txt",
     "python3 -m unittest tests.test_experiment.TestRetrieverEdges -v   # guard restored",
     1020, "good"),
]

CSS = """
body{margin:0;background:#1E2227;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;}
.win{margin:0;background:#12161A;border-radius:10px;overflow:hidden;
     box-shadow:0 10px 36px rgba(0,0,0,.5);}
.bar{background:#2B3239;padding:11px 16px;display:flex;align-items:center;gap:9px;}
.dot{width:12px;height:12px;border-radius:50%;}
.r{background:#FF5F57;} .y{background:#FEBC2E;} .g{background:#28C840;}
.title{color:#9AA4AE;font-size:12.5px;margin-left:12px;letter-spacing:.03em;}
pre{margin:0;padding:18px 22px 24px;color:#D7DEE5;font-size:13.2px;line-height:1.58;
    white-space:pre;overflow:hidden;}
.cmd{color:#7FD4A0;font-weight:700;}
.prompt{color:#5FA8E0;}
.pass{color:#4ED17E;font-weight:700;}
.fail{color:#FF6B5B;font-weight:700;}
.num{color:#F0C674;}
.dim{color:#7C8894;}
.hl{color:#FFFFFF;font-weight:700;}
"""


def colourise(text, kind):
    t = html.escape(text)
    t = re.sub(r"\b(OK)\b", r'<span class="pass">\1</span>', t)
    t = re.sub(r"\b(ok)$", r'<span class="pass">\1</span>', t, flags=re.M)
    t = re.sub(r"\b(FAIL|FAILED|AssertionError|Traceback)\b",
               r'<span class="fail">\1</span>', t)
    t = re.sub(r"(\+2\.00|94\.8%|4\.2%|\b43\b|\b48\b)", r'<span class="num">\1</span>', t)
    t = re.sub(r"^(=+)$", r'<span class="dim">\1</span>', t, flags=re.M)
    t = re.sub(r"^(-{10,})$", r'<span class="dim">\1</span>', t, flags=re.M)
    t = re.sub(r"^(OUROBOROS .*)$", r'<span class="hl">\1</span>', t, flags=re.M)
    return t


def build(name, src, cmd, width, kind):
    with open(os.path.join(EV, src)) as f:
        body = f.read().rstrip("\n")
    lines = body.count("\n") + 1
    height = 86 + int(lines * 20.9) + 46

    page = (f"<!DOCTYPE html><html><head><meta charset='utf-8'><style>{CSS}</style></head>"
            f"<body><div class='win'><div class='bar'>"
            f"<span class='dot r'></span><span class='dot y'></span><span class='dot g'></span>"
            f"<span class='title'>ouroboros &mdash; zsh</span></div>"
            f"<pre><span class='prompt'>$</span> <span class='cmd'>{html.escape(cmd)}</span>\n\n"
            f"{colourise(body, kind)}</pre></div></body></html>")

    tmp = os.path.join(EV, f"_{name}.html")
    with open(tmp, "w") as f:
        f.write(page)

    out = os.path.join(EV, f"{name}.png")
    subprocess.run([CHROME, "--headless", "--disable-gpu", "--hide-scrollbars",
                    "--force-device-scale-factor=2",
                    f"--window-size={width},{height}",
                    f"--screenshot={out}", "--virtual-time-budget=1800",
                    f"file://{tmp}"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.remove(tmp)
    return out, lines


def main():
    for name, src, cmd, w, kind in SHOTS:
        out, lines = build(name, src, cmd, w, kind)
        size = os.path.getsize(out) // 1024 if os.path.exists(out) else 0
        print(f"  {os.path.basename(out):<22} {lines:>3} lines   {size:>4} KB")
    print("screenshots written to evidence/")


if __name__ == "__main__":
    main()
