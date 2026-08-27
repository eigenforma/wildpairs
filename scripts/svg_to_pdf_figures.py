"""Render docs/figures/fig{1..5}*.svg to docs/arxiv/figures/*.pdf for the LaTeX build.

Route: each SVG is wrapped in an HTML shell and printed to a PDF page whose size equals
the SVG's pixel size (1 px = 0.75 pt, so fig1 at 780x414 px becomes 585x310.5 pt). Text
stays selectable. The SVG sources stay the sources; the PDFs are build artifacts committed
for the arXiv build (submission checklist box 7).

NOTE 2026-08-27. The original route drove desktop Edge headless. With Edge's resident
background processes alive, every print silently produced the same letter-sized junk page
at exit 0, five junk figures shipped into a compiled manuscript, and nothing failed. Two
fixes, in the lab's standing pattern that detection must be external: the renderer is now
Playwright's bundled Chromium (its own binary and profile, no collision with a desktop
browser), and every output is verified against the SVG's declared pixel size before this
script will exit 0. A desktop-browser CLI fallback remains for machines without Playwright,
behind the same verification.

Run: python scripts/svg_to_pdf_figures.py   (pip install playwright; python -m playwright install chromium)
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs" / "figures"
OUT = ROOT / "docs" / "arxiv" / "figures"

FIGS = [
    "fig1_word_counting_baseline.svg",
    "fig2_dilution_decay.svg",
    "fig3_no_source_inverted.svg",
    "fig4_scorecard.svg",
    "fig5_llm_judge_dilution.svg",
]

BROWSER_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "/usr/bin/chromium", "/usr/bin/google-chrome",
]


def shell_html(svg: str, w: str, h: str) -> str:
    return ("<!doctype html><html><head><meta charset='utf-8'><style>"
            f"@page{{size:{w}px {h}px;margin:0}}html,body{{margin:0;padding:0}}"
            "svg{display:block}</style></head><body>" + svg + "</body></html>")


def verify(pdf: Path, w: str, h: str) -> None:
    """A print that produced the wrong page is a failure even at exit 0."""
    b = pdf.read_bytes()
    boxes = re.findall(rb"/MediaBox\s*\[([^\]]+)\]", b)
    if not boxes:
        sys.exit(f"{pdf.name}: no MediaBox found; output is not a usable PDF")
    got = [float(x) for x in sorted(set(boxes))[0].split()]
    want_w, want_h = float(w) * 0.75, float(h) * 0.75
    if abs(got[2] - want_w) > 1.5 or abs(got[3] - want_h) > 1.5:
        sys.exit(f"{pdf.name}: page is {got[2]}x{got[3]} pt, expected {want_w}x{want_h} pt "
                 f"(the 2026-08-27 failure printed 612x792 letter junk); refusing to ship it")


def render_playwright() -> bool:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False
    with sync_playwright() as p, tempfile.TemporaryDirectory() as td:
        browser = p.chromium.launch()
        page = browser.new_page()
        for name in FIGS:
            svg = (SRC / name).read_text(encoding="utf-8")
            w, h = re.search(r"width='(\d+)' height='(\d+)'", svg).groups()
            shell = Path(td) / "fig.html"
            shell.write_text(shell_html(svg, w, h), encoding="utf-8")
            page.goto(shell.as_uri())
            pdf = OUT / name.replace(".svg", ".pdf")
            page.pdf(path=str(pdf), width=f"{w}px", height=f"{h}px", print_background=True,
                     margin={"top": "0", "bottom": "0", "left": "0", "right": "0"})
            verify(pdf, w, h)
            print(f"{name} -> {pdf.name} ({w}x{h} px) verified")
        browser.close()
    return True


def render_browser_cli() -> None:
    exe = next((c for c in BROWSER_CANDIDATES if Path(c).exists()), None)
    if exe is None:
        sys.exit("no renderer: install playwright (preferred) or a Chromium-family browser")
    for name in FIGS:
        svg = (SRC / name).read_text(encoding="utf-8")
        w, h = re.search(r"width='(\d+)' height='(\d+)'", svg).groups()
        with tempfile.TemporaryDirectory() as td:
            shell = Path(td) / "fig.html"
            shell.write_text(shell_html(svg, w, h), encoding="utf-8")
            pdf = OUT / name.replace(".svg", ".pdf")
            subprocess.run(
                [exe, "--headless", "--disable-gpu", "--no-first-run",
                 "--no-default-browser-check", "--no-pdf-header-footer",
                 f"--user-data-dir={Path(td) / 'profile'}",
                 f"--print-to-pdf={pdf}", str(shell)],
                check=True, capture_output=True, timeout=180,
            )
            verify(pdf, w, h)
            print(f"{name} -> {pdf.name} ({w}x{h} px) verified")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    if not render_playwright():
        render_browser_cli()


if __name__ == "__main__":
    main()
