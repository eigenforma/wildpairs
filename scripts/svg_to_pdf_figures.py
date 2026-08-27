"""Render docs/figures/fig{1..5}*.svg to docs/arxiv/figures/*.pdf for the LaTeX build.

Route: each SVG is wrapped in an HTML shell whose @page size equals the SVG's pixel
size (margin 0), then printed to PDF by headless Edge/Chromium. Chromium honors
@page in print-to-pdf, so the output page is exactly the figure: no crop step, and
text stays selectable. 1 px = 0.75 pt, so fig1 (780x414 px) becomes 585x310.5 pt.
The SVG sources stay the sources; the PDFs are build artifacts committed for the
arXiv build (SUBMISSION_CHECKLIST box 7).

Usage: python scripts/svg_to_pdf_figures.py
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs" / "figures"
OUT = ROOT / "docs" / "arxiv" / "figures"

EDGE_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/usr/bin/chromium", "/usr/bin/google-chrome",
]

FIGS = [
    "fig1_word_counting_baseline.svg",
    "fig2_dilution_decay.svg",
    "fig3_no_source_inverted.svg",
    "fig4_scorecard.svg",
    "fig5_llm_judge_dilution.svg",
]


def browser() -> str:
    for c in EDGE_CANDIDATES:
        if Path(c).exists():
            return c
    sys.exit("no Chromium-family browser found; install Edge or Chrome")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    exe = browser()
    for name in FIGS:
        svg = (SRC / name).read_text(encoding="utf-8")
        m = re.search(r"width='(\d+)' height='(\d+)'", svg)
        if not m:
            sys.exit(f"{name}: no pixel width/height on the svg root")
        w, h = m.group(1), m.group(2)
        html = (
            "<!doctype html><html><head><meta charset='utf-8'><style>"
            f"@page{{size:{w}px {h}px;margin:0}}html,body{{margin:0;padding:0}}"
            "svg{display:block}</style></head><body>" + svg + "</body></html>"
        )
        with tempfile.TemporaryDirectory() as td:
            shell = Path(td) / "fig.html"
            shell.write_text(html, encoding="utf-8")
            pdf = OUT / name.replace(".svg", ".pdf")
            subprocess.run(
                [exe, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                 f"--print-to-pdf={pdf}", str(shell)],
                check=True, capture_output=True,
            )
        print(f"{name} -> {pdf.name} ({w}x{h} px)")


if __name__ == "__main__":
    main()
