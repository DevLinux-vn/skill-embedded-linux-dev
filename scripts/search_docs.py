#!/usr/bin/env python3
"""Find the right manual chunk without reading the whole manual.

    search_docs.py DIR "i2c clock stretching" [-k 5] [--doc NAME]

DIR is a folder written by pdf_to_md.py (it contains chunks.jsonl). Ranks chunks with
BM25 over the chunk text, giving extra weight to the section path and chapter title,
and prints the best matches with a one-line snippet. Open only those chunk files.
Standard library only. Exit status 0 if something matched, 1 if not.
"""
import argparse
import collections
import json
import math
import re
import sys
from pathlib import Path

TOKEN = re.compile(r"[0-9a-z_µ]+")
K1, B = 1.5, 0.75


def tokenize(text):
    """Words, plus the parts of snake_case names so `clkdiv` finds `I2C_CLKDIV`."""
    out = []
    for t in TOKEN.findall(text.lower()):
        out.append(t)
        if "_" in t:
            out += [x for x in t.split("_") if x]
    return out


def body_of(text):
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4:].lstrip("\n")
    return text


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("dir")
    ap.add_argument("query")
    ap.add_argument("-k", type=int, default=5)
    ap.add_argument("--doc", help="only chunks whose document name or slug contains this")
    a = ap.parse_args()

    root = Path(a.dir)
    f = root / "chunks.jsonl"
    if not f.is_file():
        print(f"No chunks.jsonl in {root}. Convert a PDF with pdf_to_md.py first.")
        return 2
    records = [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines() if x.strip()]
    if a.doc:
        records = [r for r in records if a.doc.lower() in r["doc"].lower() or a.doc.lower() in r["path"].lower()]

    docs = []
    for r in records:
        p = root / r["path"]
        if not p.is_file():
            continue
        body = body_of(p.read_text(encoding="utf-8"))
        tf = collections.Counter(tokenize(body))
        for t in tokenize(r["section"]) + tokenize(" ".join(r.get("headings", []))):
            tf[t] += 3
        for t in tokenize(r["chapter"]):
            tf[t] += 2
        docs.append((r, body, tf, sum(tf.values())))
    if not docs:
        print("No chunks to search.")
        return 1

    q = list(dict.fromkeys(tokenize(a.query)))
    n = len(docs)
    avg = sum(d[3] for d in docs) / n or 1
    df = {t: sum(1 for d in docs if t in d[2]) for t in q}
    scored = []
    for r, body, tf, dl in docs:
        s = 0.0
        for t in q:
            if tf[t]:
                idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
                s += idf * tf[t] * (K1 + 1) / (tf[t] + K1 * (1 - B + B * dl / avg))
        if s > 0:
            scored.append((s, r, body))
    scored.sort(key=lambda x: -x[0])
    if not scored:
        print("No match.")
        return 1

    for rank, (s, r, body) in enumerate(scored[:a.k], 1):
        lines = [ln.strip() for ln in body.split("\n")
                 if ln.strip() and not ln.lstrip().startswith(("#", "<", "```", "|---"))]
        best = max(lines, key=lambda ln: len(set(tokenize(ln)) & set(q)), default="")
        print(f"{rank}. {r['section']}  [{r['doc']} p{r['pages']}]  score {s:.2f}")
        print(f"   {root / r['path']}")
        if best:
            print(f"   {best[:160]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
