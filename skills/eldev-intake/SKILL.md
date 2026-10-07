---
name: eldev-intake
description: Record and reuse the board and target-module facts that every other embedded Linux skill needs, so source code is not re-read each time. Use at the start of any driver or userspace task on a board, when board facts are missing or incomplete, when the user gives or changes SoC, kernel version, toolchain, build system and commands, device tree, pinout, voltage, flash method, debug access or reference manual, or switches to another board or module.
---

# eldev-intake

Write board and target facts down once, in files in the user's project, so later steps read a few dozen lines instead of the source tree.

## Files

- `boards/<board>/board.yaml`: SoC, kernel, toolchain, build system and commands, flash, debug, voltage.
- `boards/<board>/pinout.md`, `build-guide.md`, `dt/`: pinout, the user's build guide, device tree and defconfig.
- `boards/<board>/manual/`: reference manual chapters as markdown, one file per chapter.
- `targets/<target>/target.yaml` and `docs/`: the one module being worked on and its datasheets.

The user supplies all of these. Never write or summarise manual content yourself; converting a PDF mechanically (below) is the only way manual text enters the project.

These live at the project root as shown, since `check_context.py` looks there. A short pointer in the project's `CLAUDE.md` says which board and target are active, so a new session finds them without searching (see `assets/example/CLAUDE.md.snippet`). Switching work means editing that pointer.

A filled example (Raspberry Pi 4B + IMX219, Yocto) is in `assets/example/`. Copy it and replace the values; its field names are the schema.

Scripts live in `scripts/` at the plugin root, two directories up from this skill's base directory (`<plugin>` below), so other skills can share them.

## Workflow

1. Run `python3 <plugin>/scripts/check_context.py` from the project root. It is read-only and reports each item as OK, EMPTY, MISSING or ASSUMED, and whether the task is READY. Read the pointer in `CLAUDE.md`, then the board and target files it names. Stop if they answer the question.
2. If the check is not READY, stop before writing any code. List exactly what is missing and where the user should put it, then wait. Copy the example for missing yaml files and fill what the user said or pointed to. One module is in scope; ignore the rest.
3. Mark each value with a trailing comment: none means the user gave it, `# verified: <source>` means checked against a primary source, `# assumed` means a guess to confirm before touching hardware. Leave unknown fields empty. User values win and are not silently changed.
4. Do not invent pins, voltages, addresses or build commands. Build and flash commands come from the user's build guide.

## Reference manual

List the files in `manual/` and open only the chapters for the module in hand plus directly related ones (I2C work: I2C, GPIO and pinmux, clocks). The check script reports which chapters are present. Never load the whole manual.

## Converting a PDF

When the user gives a PDF manual or datasheet instead of markdown, convert it with the script. It needs `pip install pymupdf4llm`.

```
python3 <plugin>/scripts/pdf_to_md.py <file.pdf> --out boards/<board>/manual      # a module datasheet: --out targets/<target>/docs
```

It splits by the PDF bookmarks (one file per chapter, or one file if there are none), extracts each figure as a png, keeps any text found inside a figure, and writes `INDEX.md` with a text-coverage figure per chapter. Nothing is summarised. If a chapter reports LOW COVERAGE, tell the user and compare against the PDF before relying on it. Tables with no ruling lines and multi-column layouts can come out flattened, so check any table whose values you will use.

Figures listed in `figures.todo.txt` can get an ASCII redraw. Open each png, write a faithful transcription of the blocks, labels and arrows to `images/<same name>.txt`, change nothing you cannot read, and re-run the script to embed it beside the image. The image stays authoritative; say so if a label is unclear instead of guessing.
