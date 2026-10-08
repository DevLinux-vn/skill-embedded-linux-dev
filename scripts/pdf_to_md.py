#!/usr/bin/env python3
"""Convert a PDF into small markdown chunks that are easy to retrieve (RAG).

    pdf_to_md.py INPUT.pdf --out boards/<board>/manual
                 [--split chapters|none] [--level 1] [--dpi 200]
                 [--max-words 500] [--min-words 80] [--min-coverage 0.97]

Needs:  pip install pymupdf4llm

Chapters come from the PDF bookmarks (one chapter if there are none). Each chapter is
cut at its headings into chunks of about --max-words words (a table, code block or
figure is never split, and one very long sentence can reach twice that); tiny sections
are merged into a neighbour and a heading always stays with its first paragraph. Under --out:

    <doc>/<NN-chapter>/<NNN-section>.md   one chunk: front matter + original text
    chunks.jsonl                          one JSON line per chunk (id, path, doc, chapter,
                                          section, headings, pages, words, coverage)
    INDEX.md                              chapters, chunk counts, pages, text coverage
    images/                               figure images and figures.todo.md

Several PDFs can share one --out; re-running a PDF replaces only its own chunks.
Nothing is summarised. Text found inside a figure is kept beside it. An ASCII redraw
of a figure is read from images/<figure>.md when that file exists and embedded.
Find chunks with scripts/search_docs.py. Exit status: 1 if a chapter's text coverage
is below --min-coverage.
"""
import argparse
import collections
import json
import os
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
PAGE = re.compile(r"<!--page:(\d+)-->")
HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
TOKEN = re.compile(r"[0-9a-zµ]+")


def slugify(text):
    text = re.sub(r"^\s*(chapter\s+)?\d+(\.\d+)*[.)]?\s+", "", text.strip(), flags=re.I)
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:40].strip("-") or "part"


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


def embed_figures(md, name_prefix, img_out, rel):
    """Copy figures to img_out, link them from `rel`, keep figure text and redraws."""
    count = 0

    def repl(m):
        nonlocal count
        src = Path(m.group(1))
        if not src.is_file():
            return m.group(0)
        count += 1
        name = f"{name_prefix}-fig{count:02d}"
        shutil.copy(src, img_out / f"{name}.png")
        parts = [f"![Figure {count}]({rel}/{name}.png)"]
        text = clean_picture_text(m.group(2))
        if text:
            parts.append(details("Text found in figure", text))
        redraw = img_out / f"{name}.md"
        if redraw.is_file():
            art = redraw.read_text(encoding="utf-8").strip()
            if "```" not in art:
                art = f"```text\n{art}\n```"
            parts.append(details("ASCII redraw (transcribed from the image; the image is authoritative)", art))
        return "\n\n".join(parts) + "\n"

    md = IMG_WITH_TEXT.sub(repl, md)
    # picture text that was not attached to an image is still content: keep it
    md = PIC_TEXT.sub(lambda m: clean_picture_text(m.group(1)), md)
    return md, count


def split_blocks(md):
    """Paragraph-level blocks with their page. Fences, <details> and tables stay whole."""
    blocks, cur, fence, det, page = [], [], False, 0, None

    def flush():
        if cur:
            blocks.append(("\n".join(cur).strip("\n"), page))
            cur.clear()

    for line in md.split("\n"):
        s = line.strip()
        m = PAGE.fullmatch(s)
        if m and not fence and not det:
            flush()
            page = int(m.group(1))
            continue
        if s.startswith("```"):
            fence = not fence
        if s.startswith("<details"):
            det += 1
        if not s and not fence and not det:
            flush()
            continue
        cur.append(line)
        if s.startswith("</details"):
            det = max(0, det - 1)
    flush()
    return [b for b in blocks if b[0].strip()]


def words(text):
    return len(text.split())


def sections(blocks):
    """Group blocks under their heading; keep the heading path (breadcrumb)."""
    stack, out, cur = [], [], None
    for text, page in blocks:
        m = HEADING.match(text.split("\n", 1)[0])
        if m and len(m.group(2).split()) > 15:
            m = None  # a whole paragraph styled as a heading is not a section title
        if m:
            level, title = len(m.group(1)), re.sub(r"[*_`]+", "", m.group(2)).strip()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))
            cur = {"path": " > ".join(t for _, t in stack), "title": title, "blocks": []}
            out.append(cur)
        elif cur is None:
            cur = {"path": "", "title": "", "blocks": []}
            out.append(cur)
        cur["blocks"].append((text, page))
    return out


def split_long(block, max_words):
    """Cut an oversized plain-text paragraph at sentence ends. Tables, code, figures stay whole."""
    text, page = block
    plain = not text.lstrip().startswith(("|", "```", "<", "![", "#")) and "\n|" not in text
    if not plain or words(text) <= max_words:
        return [block]
    units = []
    for sent in (x.strip() for x in re.split(r"(?<=[.!?])\s+", text)):
        w = sent.split()
        if len(w) > 2 * max_words:  # no sentence ends in sight: fall back to word slices
            units += [" ".join(w[i:i + max_words]) for i in range(0, len(w), max_words)]
        elif w:
            units.append(sent)
    out, cur = [], []
    for u in units:
        if cur and words(" ".join(cur + [u])) > max_words:
            out.append((" ".join(cur), page))
            cur = []
        cur.append(u)
    if cur:
        out.append((" ".join(cur), page))
    return out


def pieces(sec, max_words):
    res, cur, n = [], [], 0
    for b in (x for blk in sec["blocks"] for x in split_long(blk, max_words)):
        w = words(b[0])
        heading_only = len(cur) == 1 and HEADING.match(cur[0][0].split("\n", 1)[0])
        if cur and n + w > max_words and not heading_only:  # a heading stays with its first paragraph
            res.append(cur)
            cur, n = [], 0
        cur.append(b)
        n += w
    if cur:
        res.append(cur)
    return [{"path": sec["path"], "titles": [sec["title"]], "blocks": p,
             "words": sum(words(b[0]) for b in p)} for p in res]


def make_chunks(md, max_words, min_words):
    blocks = [b for b in split_blocks(md) if not re.fullmatch(r"\d{1,3}", b[0].strip())]  # page numbers
    units = [u for s in sections(blocks) for u in pieces(s, max_words)]
    out = []
    for u in units:
        if out and out[-1]["words"] < min_words and out[-1]["words"] + u["words"] <= max_words * 1.3:
            out[-1]["blocks"] += u["blocks"]
            out[-1]["words"] += u["words"]
            out[-1]["titles"] += u["titles"]
        else:
            out.append(u)
    return out


def tokens(text):
    return collections.Counter(TOKEN.findall(text.lower()))


def coverage(doc, first, last, md):
    pdf = tokens(" ".join(doc[i].get_text() for i in range(first - 1, last)))
    got = tokens(PAGE.sub(" ", md))
    total = sum(pdf.values()) or 1
    return sum(min(c, got[t]) for t, c in pdf.items()) / total


def load_records(out):
    f = out / "chunks.jsonl"
    if not f.is_file():
        return []
    return [json.loads(line) for line in f.read_text(encoding="utf-8").splitlines() if line.strip()]


def drop_doc(out, records, doc_name, doc_slug):
    """Remove the earlier chunks and figures of this PDF so a re-run leaves no stale copies."""
    for r in records:
        if r["doc"] == doc_name:
            (out / r["path"]).unlink(missing_ok=True)
    shutil.rmtree(out / doc_slug, ignore_errors=True)
    for png in (out / "images").glob(f"{doc_slug}-*.png"):
        png.unlink()
    return [r for r in records if r["doc"] != doc_name]


def write_index(out, records):
    rows = collections.OrderedDict()
    for r in records:
        k = (r["doc"], r["chapter"])
        d = rows.setdefault(k, {"chunks": 0, "words": 0, "pages": [], "cov": r.get("coverage", 0)})
        d["chunks"] += 1
        d["words"] += r["words"]
        d["pages"] += [int(p) for p in str(r["pages"]).split("-") if p]
    lines = ["# Manual index", "",
             "Chunks are in `<doc>/<chapter>/`; metadata for every chunk is in `chunks.jsonl`.",
             "Find the right chunk with `search_docs.py <this folder> \"query\"`, then open only that chunk.", "",
             "| Document | Chapter | Chunks | Words | Pages | Text coverage |", "|---|---|---|---|---|---|"]
    for (doc, chapter), d in rows.items():
        pg = f"{min(d['pages'])}-{max(d['pages'])}" if d["pages"] else ""
        lines.append(f"| {doc} | {chapter} | {d['chunks']} | {d['words']} | {pg} | {d['cov']:.1%} |")
    (out / "INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_todo(img_out):
    todo = sorted(p for p in img_out.glob("*.png") if not p.with_suffix(".md").exists()
                  and p.name != "figures.todo.md")
    f = img_out / "figures.todo.md"
    if todo:
        f.write_text("# Figures without an ASCII redraw\n\n" +
                     "\n".join(f"- `{p.name}` (write `{p.stem}.md` beside it, then re-run)" for p in todo) + "\n",
                     encoding="utf-8")
    else:
        f.unlink(missing_ok=True)
    return len(todo)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("pdf")
    ap.add_argument("--out", required=True)
    ap.add_argument("--split", choices=("chapters", "none"), default="chapters")
    ap.add_argument("--level", type=int, default=1, help="deepest bookmark level that starts a chapter")
    ap.add_argument("--dpi", type=int, default=200)
    ap.add_argument("--max-words", type=int, default=500, help="largest chunk, in words")
    ap.add_argument("--min-words", type=int, default=80, help="smaller sections are merged into a neighbour")
    ap.add_argument("--min-coverage", type=float, default=0.97)
    a = ap.parse_args()

    out = Path(a.out)
    img_out = out / "images"
    img_out.mkdir(parents=True, exist_ok=True)
    pdf = Path(a.pdf)
    doc = pymupdf.open(pdf)
    doc_slug = slugify(pdf.stem)
    chs = chapters(doc, a.level) if a.split == "chapters" else None
    if chs is None:
        if a.split == "chapters":
            print("No PDF bookmarks found: treating the whole document as one chapter.")
        chs = [(pdf.stem, 1, len(doc))]

    records = drop_doc(out, load_records(out), pdf.name, doc_slug)
    tmp = Path(tempfile.mkdtemp())
    low, nchunks, nfig = [], 0, 0
    for i, (title, first, last) in enumerate(chs, 1):
        chap = f"{i:02d}-{slugify(title)}"
        chunk_dir = out / doc_slug / chap
        chunk_dir.mkdir(parents=True, exist_ok=True)
        page_md = pymupdf4llm.to_markdown(
            doc, pages=list(range(first - 1, last)), page_chunks=True, write_images=True,
            image_path=str(tmp / chap), image_format="png", dpi=a.dpi)
        md = "\n\n".join(f"<!--page:{first + k}-->\n\n{p['text']}" for k, p in enumerate(page_md))
        md, fixed = fix_text(md)
        rel = os.path.relpath(img_out, chunk_dir).replace(os.sep, "/")
        md, figs = embed_figures(md, f"{doc_slug}-{chap}", img_out, rel)
        nfig += figs
        cov = coverage(doc, first, last, md)
        if cov < a.min_coverage:
            low.append((title, cov))
        if "�" in md:
            print(f"warning: {chap} still has replacement characters; check the original")
        if fixed:
            print(f"{chap}: restored {fixed} micro sign(s)")
        for n, ch in enumerate(make_chunks(md, a.max_words, a.min_words), 1):
            pages = [p for _, p in ch["blocks"] if p]
            pg = f"{min(pages)}-{max(pages)}" if pages and min(pages) != max(pages) else str(pages[0] if pages else first)
            section = ch["path"] or title
            heads = [t for t in ch["titles"] if t]
            cid = f"{doc_slug}/{chap}/{n:03d}"
            name = f"{n:03d}-{slugify(heads[0] if heads else title)}.md"
            body = "\n\n".join(b for b, _ in ch["blocks"])
            front = ["---", f"id: {cid}", f"doc: {json.dumps(pdf.name)}", f"chapter: {json.dumps(title)}",
                     f"section: {json.dumps(section)}", f"pages: {pg}", "---", ""]
            (chunk_dir / name).write_text("\n".join(front) + body + "\n", encoding="utf-8")
            records.append({"id": cid, "path": f"{doc_slug}/{chap}/{name}", "doc": pdf.name, "chapter": title,
                            "section": section, "headings": heads, "pages": pg, "words": ch["words"],
                            "coverage": round(cov, 4)})
            nchunks += 1
    shutil.rmtree(tmp, ignore_errors=True)

    (out / "chunks.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
    write_index(out, records)
    todo = write_todo(img_out)

    print(f"{len(chs)} chapter(s), {nchunks} chunk(s), {nfig} figure(s) -> {out}")
    if todo:
        print(f"{todo} figure(s) have no ASCII redraw yet: see {img_out / 'figures.todo.md'}")
    for title, cov in low:
        print(f"LOW COVERAGE {cov:.1%}: {title} (text may be missing or out of order; compare with the PDF)")
    return 1 if low else 0


if __name__ == "__main__":
    sys.exit(main())
