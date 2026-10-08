#!/usr/bin/env python3
"""Check that the board/target context a driver task needs is present.

Read-only. Prints one line per item (OK, EMPTY, MISSING, ASSUMED) and a verdict.
Exit status: 0 ready, 1 not ready, 2 usage error. Uses only the standard library.

    check_context.py [--root DIR] [--board NAME] [--target NAME] [--need i2c,gpio]

Board and target come from the pointer in CLAUDE.md ("Board: <name>",
"Target: <name>") unless given on the command line.
"""
import argparse
import re
import sys
from pathlib import Path

BOARD_REQUIRED = [
    "soc", "arch", "kernel.version", "kernel.source_path", "kernel.dts",
    "toolchain.triple", "buildsys.type", "commands.image", "commands.deploy",
    "flash", "console",
]
TARGET_REQUIRED = ["kind", "subsystem", "control", "dt"]
BUSES = ("i2c", "spi", "uart", "csi")


def parse_yaml(path):
    """Minimal reader for the nested `key: value` files used here.

    Returns {dotted.path: (value, comment)}. Handles two-space nesting and
    trailing comments; lists and flow syntax are not needed and are skipped.
    """
    out, stack = {}, []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        m = re.match(r"^(\s*)([A-Za-z0-9_.-]+):\s*(.*)$", raw)
        if not m:
            continue
        indent, key, rest = len(m.group(1)), m.group(2), m.group(3)
        while stack and stack[-1][0] >= indent:
            stack.pop()
        value, comment = rest, ""
        if " #" in rest or rest.startswith("#"):
            value, _, comment = rest.partition("#")
        value = value.strip().strip('"').strip("'")
        stack.append((indent, key))
        out[".".join(k for _, k in stack)] = (value, comment.strip())
    return out


def read_pointer(root, name):
    p = root / "CLAUDE.md"
    if not p.is_file():
        return None
    m = re.search(rf"^{name}:\s*([A-Za-z0-9_.-]+)", p.read_text(encoding="utf-8"),
                  re.MULTILINE | re.IGNORECASE)
    return m.group(1) if m else None


def derive_needed(target):
    text = " ".join(target.get(k, ("", ""))[0] for k in ("control", "data")).lower()
    need = [b for b in BUSES if b in text]
    return need + (["gpio"] if need else [])


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=".")
    ap.add_argument("--board")
    ap.add_argument("--target")
    ap.add_argument("--need", help="comma list of manual chapters, default derived from target")
    a = ap.parse_args()

    root = Path(a.root).resolve()
    board = a.board or read_pointer(root, "Board")
    target = a.target or read_pointer(root, "Target")
    if not board or not target:
        print("No board/target given and no 'Board:'/'Target:' pointer in CLAUDE.md.")
        print("Add the pointer or pass --board and --target.")
        return 2

    rows = []  # (status, item, note)

    def add(status, item, note=""):
        rows.append((status, item, note))

    def check_fields(label, data, required):
        for key in required:
            val, comment = data.get(key, ("", ""))
            if not val:
                add("EMPTY", f"{label} {key}", "fill in")
            elif "assumed" in comment.lower():
                add("ASSUMED", f"{label} {key}", f"{val}  (confirm)")
            else:
                add("OK", f"{label} {key}")

    bdir, tdir = root / "boards" / board, root / "targets" / target

    add("OK" if (root / "CLAUDE.md").is_file() else "MISSING", "CLAUDE.md pointer")

    # board.yaml
    byaml = bdir / "board.yaml"
    if byaml.is_file():
        check_fields("board.yaml", parse_yaml(byaml), BOARD_REQUIRED)
    else:
        add("MISSING", f"boards/{board}/board.yaml")

    # board files and folders
    for name in ("pinout.md", "build-guide.md"):
        f = bdir / name
        add("OK" if f.is_file() and f.stat().st_size else
            ("EMPTY" if f.is_file() else "MISSING"), f"boards/{board}/{name}")
    dt = bdir / "dt"
    add("OK" if dt.is_dir() and any(dt.iterdir()) else
        ("EMPTY" if dt.is_dir() else "MISSING"), f"boards/{board}/dt/")

    # target.yaml
    tyaml = tdir / "target.yaml"
    tdata = {}
    if tyaml.is_file():
        tdata = parse_yaml(tyaml)
        check_fields("target.yaml", tdata, TARGET_REQUIRED)
    else:
        add("MISSING", f"targets/{target}/target.yaml")
    docs = tdir / "docs"
    add("OK" if docs.is_dir() and any(docs.iterdir()) else
        ("EMPTY" if docs.is_dir() else "MISSING"), f"targets/{target}/docs/")

    # manual chapters needed for this module
    manual = bdir / "manual"
    have = {str(p.relative_to(manual).with_suffix("")).lower()
            for p in manual.rglob("*.md") if p.name.lower() != "index.md"} if manual.is_dir() else set()
    need = [n.strip().lower() for n in a.need.split(",")] if a.need else derive_needed(tdata)
    if not manual.is_dir():
        add("MISSING", f"boards/{board}/manual/")
    elif not have:
        add("EMPTY", f"boards/{board}/manual/", "no chapter files")
    for n in need:
        hit = sorted(h for h in have if n in h)
        add("OK" if hit else "MISSING", f"manual chapter '{n}'",
            ", ".join(hit[:2]) + (f" (+{len(hit) - 2} more)" if len(hit) > 2 else ""))

    width = max(len(r[1]) for r in rows)
    print(f"board={board} target={target}")
    for status, item, note in rows:
        print(f"{status:8} {item:<{width}}  {note}".rstrip())
    bad = [r for r in rows if r[0] in ("MISSING", "EMPTY")]
    warn = [r for r in rows if r[0] == "ASSUMED"]
    if bad:
        print(f"\nNOT READY: {len(bad)} item(s) missing or empty, {len(warn)} assumed.")
        return 1
    print(f"\nREADY: nothing missing, {len(warn)} assumed value(s) to confirm.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
