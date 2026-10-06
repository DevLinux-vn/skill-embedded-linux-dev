#!/usr/bin/env python3
"""Convert a PDF into markdown chapters, keeping the content and the figures.

    pdf_to_md.py INPUT.pdf --out boards/<board>/manual [--split chapters|none]
                 [--level 1] [--dpi 200] [--min-coverage 0.97]

Needs:  pip install pymupdf4llm

Writes, under --out:
    NN-<chapter>.md        one file per chapter (PDF bookmarks, or one file if none)
    images/                figure images, <chapter>-figNN.png
    INDEX.md               chapter, file, pages, words, figures, text coverage
    figures.todo.txt       figures that still have no ASCII redraw

Nothing is summarised or rewritten. Text found inside a figure is kept next to it.
An ASCII redraw of a figure is read from images/<chapter>-figNN.txt when that file
exists (written by a person, or by Claude from the image); re-run to embed it.
Exit status: 0 ok, 1 if any chapter's text coverage is below --min-coverage.
"""
import argparse
import collections
import re
import shutil
import sys
import tempfile
from pathlib import Path

try:
    import pymupdf
    import pymupdf4llm
except ImportError:
    sys.exit("Needs pymupdf4llm: pip install pymupdf4llm")

IMG_WITH_TEXT = re.compile(
    r"!\[[^\]]*\]\(([^)]+)\)"
    r"(?:\s*<!-- Start of picture text -->(.*?)<!-- End of picture text -->)?", re.S)
PIC_TEXT = re.compile(r"<!-- Start of picture text -->(.*?)<!-- End of picture text -->", re.S)
TOKEN = re.compile(r"[0-9a-zµ]+")


def slugify(text):
    text = re.sub(r"^\s*(chapter\s+)?\d+(\.\d+)*[.)]?\s+", "", text.strip(), flags=re.I)
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:40].strip("-") or "chapter"


def chapters(doc, level):
    """Return [(title, first_page, last_page)], pages 1-based, from PDF bookmarks."""
    n = len(doc)
    starts = {}
    for lvl, title, page in doc.get_toc():
        if lvl <= level and 1 <= page <= n:
            starts.setdefault(page, title.strip())
    if not starts:
        return None
    pages = sorted(starts)
    out = []
    if pages[0] > 1:  # keep anything before the first bookmark
        out.append(("front matter", 1, pages[0] - 1))
    for i, p in enumerate(pages):
        out.append((starts[p], p, pages[i + 1] - 1 if i + 1 < len(pages) else n))
    return out


def details(summary, body):
    return f"<details><summary>{summary}</summary>\n\n{body}\n\n</details>"


def clean_picture_text(text):
    return re.sub(r"\s*<br>\s*", "\n", text or "").strip()


def fix_text(md):
    # A replacement character between a number and a unit is the micro sign.
    md, n = re.subn(r"(?<=\d)\s?�(?=[A-Za-z])", "µ", md)
    md = re.sub(r"([^\n])\n(#{1,6} )", r"\1\n\n\2", md)
    return re.sub(r"\n{3,}", "\n\n", md), n


def embed_figures(md, slug, img_out, todo):
    count = 0

    def repl(m):
        nonlocal count
        src = Path(m.group(1))
        if not src.is_file():
            return m.group(0)
        count += 1
        name = f"{slug}-fig{count:02d}"
        shutil.copy(src, img_out / f"{name}.png")
        parts = [f"![Figure {count}](images/{name}.png)"]
        text = clean_picture_text(m.group(2))
        if text:
            parts.append(details("Text found in figure", text))
        redraw = img_out / f"{name}.txt"
        if redraw.is_file():
            art = redraw.read_text(encoding="utf-8").rstrip()
            parts.append(details("ASCII redraw (transcribed from the image; the image is authoritative)",
                                 f"```text\n{art}\n```"))
        else:
            todo.append(f"images/{name}.png")
        return "\n\n".join(parts) + "\n"

    md = IMG_WITH_TEXT.sub(repl, md)
    # picture text that was not attached to an image is still content: keep it
    md = PIC_TEXT.sub(lambda m: clean_picture_text(m.group(1)), md)
    return md, count


def tokens(text):
    return collections.Counter(TOKEN.findall(text.lower()))


def coverage(doc, first, last, md):
    pdf = tokens(" ".join(doc[i].get_text() for i in range(first - 1, last)))
    got = tokens(md)
    total = sum(pdf.values()) or 1
    return sum(min(c, got[t]) for t, c in pdf.items()) / total


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("pdf")
    ap.add_argument("--out", required=True)
    ap.add_argument("--split", choices=("chapters", "none"), default="chapters")
    ap.add_argument("--level", type=int, default=1, help="deepest bookmark level that starts a chapter")
    ap.add_argument("--dpi", type=int, default=200)
    ap.add_argument("--min-coverage", type=float, default=0.97)
    a = ap.parse_args()

    out, img_out = Path(a.out), Path(a.out) / "images"
    img_out.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open(a.pdf)
    chs = chapters(doc, a.level) if a.split == "chapters" else None
    if chs is None:
        if a.split == "chapters":
            print("No PDF bookmarks found: writing the whole document as one file.")
        chs = [(Path(a.pdf).stem, 1, len(doc))]

    tmp = Path(tempfile.mkdtemp())
    rows, todo, low = [], [], []
    for i, (title, first, last) in enumerate(chs, 1):
        slug = f"{i:02d}-{slugify(title)}"
        md = pymupdf4llm.to_markdown(
            doc, pages=list(range(first - 1, last)), write_images=True,
            image_path=str(tmp / slug), image_format="png", dpi=a.dpi)
        md, fixed = fix_text(md)
        md, nfig = embed_figures(md, slug, img_out, todo)
        cov = coverage(doc, first, last, md)
        (out / f"{slug}.md").write_text(md.strip() + "\n", encoding="utf-8")
        rows.append((title, f"{slug}.md", f"{first}-{last}", len(md.split()), nfig, cov))
        if cov < a.min_coverage:
            low.append((title, cov))
        if "�" in md:
            print(f"warning: {slug}.md still has replacement characters; check the original")
        if fixed:
            print(f"{slug}.md: restored {fixed} micro sign(s)")
    shutil.rmtree(tmp, ignore_errors=True)

    lines = ["# Manual index", "",
             f"Generated from `{Path(a.pdf).name}` by `pdf_to_md.py`. Titles come from the PDF bookmarks.", "",
             "| Chapter | File | Pages | Words | Figures | Text coverage |", "|---|---|---|---|---|---|"]
    lines += [f"| {t} | {f} | {p} | {w} | {n} | {c:.1%} |" for t, f, p, w, n, c in rows]
    (out / "INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    todo_file = out / "figures.todo.txt"
    if todo:
        todo_file.write_text("\n".join(todo) + "\n", encoding="utf-8")
    elif todo_file.exists():
        todo_file.unlink()

    print(f"{len(rows)} chapter file(s), {sum(r[4] for r in rows)} figure(s) -> {out}")
    if todo:
        print(f"{len(todo)} figure(s) have no ASCII redraw yet: see {todo_file}")
    for title, cov in low:
        print(f"LOW COVERAGE {cov:.1%}: {title} (text may be missing; compare with the PDF)")
    return 1 if low else 0


if __name__ == "__main__":
    sys.exit(main())
