# embedded-linux-dev

A Claude Code plugin for embedded Linux development: kernel drivers (external
devices and SoC peripherals), userspace programs, and getting them built, flashed
and verified on a real board. It is meant to grow module by module and board by
board; I2C, SPI and UART come first, together with the subsystems they depend on
(device tree, pinctrl, interrupts, GPIO, and media/V4L2 for camera sensors).

## How it works

1. **Context once.** Board facts (SoC, kernel version, toolchain, build system and
   commands, flash and debug access, voltage) and the one module being worked on
   are written to `board.yaml` and `target.yaml` in your project. A short pointer
   in your project's `CLAUDE.md` names the active board and target. Later steps
   read these files instead of re-reading the source tree.
2. **One module at a time.** Only the module you name is in scope. The reference
   manual, converted to markdown, is read through an index, one chapter at a time.
3. **Loop until it works.** Write, integrate into your tree, build with your
   commands, flash, capture logs, decide pass or fail, fix, repeat.

You provide the source tree, build guide, device tree, pinout and manual. The
plugin never guesses pins, voltages, addresses or build commands.

## Skills

| Skill | Purpose | Status |
|---|---|---|
| `eldev-router` | Reads the context, classifies the request, hands off | done |
| `eldev-intake` | Creates and maintains board and target context | done |
| `eldev-driver-external` | Driver for a device wired to the board | planned |
| `eldev-driver-platform` | Driver for a SoC peripheral | planned |
| `eldev-userspace` | Userspace programs and service generation | planned |
| `eldev-integrate` | Put code into your tree and build with your commands | planned |
| `eldev-debug` | Choose debug tools, capture data | planned |
| `eldev-log-diagnose` | Read dmesg, journal or serial logs, decide pass or fail | planned |

A worked example (Raspberry Pi 4B + IMX219 camera on Yocto) is in
`skills/eldev-intake/assets/example/`.

## Usage

### 1. Install

Load the plugin from a local clone:

```
git clone https://github.com/DevLinux-vn/skill-embedded-linux-dev
claude --plugin-dir ./skill-embedded-linux-dev
```

The PDF converter needs one package: `pip install pymupdf4llm`. The other script uses only the Python standard library.

### 2. Set up your project

Skills read these files from your project root. You supply them; the plugin never fills in pins, voltages, addresses or build commands for you.

```
<project>/
├── CLAUDE.md                      pointer to the active board and target
├── boards/<board>/
│   ├── board.yaml                 SoC, kernel, toolchain, build system and commands, flash, debug
│   ├── pinout.md                  pins, functions, voltage
│   ├── build-guide.md             your build instructions
│   ├── dt/                        device tree, defconfig
│   └── manual/                    reference manual, split into markdown chunks
└── targets/<target>/
    ├── target.yaml                the one module being worked on
    └── docs/                      its datasheets, same chunk format
```

Add the pointer to `CLAUDE.md` so every session knows what is active:

```
## Embedded context
Board: rpi4b (boards/rpi4b/board.yaml, manual in boards/rpi4b/manual/)
Target: imx219 (targets/imx219/target.yaml)
```

A complete example project for Raspberry Pi 4B + IMX219 is in `skills/eldev-intake/assets/example/`, laid out like your project root: copy and edit it.

### 3. Use the skills

Skills trigger from what you ask; you do not have to name them.

| You say | What happens |
|---|---|
| "Write a driver for the IMX219 on my Pi 4B" | `eldev-router` reads the context, classifies the request and hands off. If anything needed is missing, `eldev-intake` runs the readiness check and stops with a list of what to add |
| "Set up context for this board" / "I changed the kernel to 6.12" | `eldev-intake` creates or updates `board.yaml` and `target.yaml`; your values always win and guesses are marked `# assumed` |
| "Here is the BCM2711 manual PDF" | `eldev-intake` converts it with `pdf_to_md.py` into searchable chunks |
| "What does the manual say about I2C clock stretching?" | the skill runs `search_docs.py` and opens only the best chunks, not the whole manual |

Only the router and intake skills exist so far; the driver, integrate, debug and log skills are planned (see the table above).

### 4. Scripts

Run them from your project root. `<plugin>` is the directory you cloned.

**Readiness check** (read-only, no changes):

```
python3 <plugin>/scripts/check_context.py [--board NAME] [--target NAME] [--need i2c,gpio]
```

Board and target come from `Board:` and `Target:` in `CLAUDE.md` unless given. It reports each item as `OK`, `EMPTY`, `MISSING` or `ASSUMED`, checks that the manual chapters the module needs exist (derived from the bus in `target.yaml`, or `--need`), and ends with `READY` (exit 0) or `NOT READY` (exit 1). Exit 2 means no board or target was found.

**PDF to markdown chunks:**

```
python3 <plugin>/scripts/pdf_to_md.py manual.pdf --out boards/<board>/manual
python3 <plugin>/scripts/pdf_to_md.py datasheet.pdf --out targets/<target>/docs
```

| Option | Meaning |
|---|---|
| `--split chapters\|none` | One chapter per PDF bookmark (default), or the whole document as one chapter. No bookmarks also gives one chapter |
| `--level N` | Deepest bookmark level that starts a chapter (default 1) |
| `--max-words N` | Target chunk size in words (default 500) |
| `--min-words N` | Smaller sections are merged into a neighbour (default 80) |
| `--dpi N` | Resolution of extracted figures (default 200) |
| `--min-coverage X` | Warn and exit 1 if a chapter's text coverage is below X (default 0.97) |

Output in `--out`:

```
<doc>/<NN-chapter>/<NNN-section>.md   one chunk: front matter (id, document, chapter, section path, pages) + original text
chunks.jsonl                          one metadata line per chunk
INDEX.md                              chapters, chunk counts, pages, text coverage
images/                               figures, and figures.todo.md
```

Chunks follow the headings, keep a table or figure whole, and carry their section path so a search hit explains itself. Several PDFs can share one `--out`; re-running a PDF replaces only its own chunks. Nothing is summarised, and text found inside a figure is kept beside it. Coverage counts words, not order, so check any table whose values you will rely on against the PDF.

To add an ASCII redraw of a block diagram, write it to `images/<same name as the png>.md` and run the command again; it is embedded next to the image, which stays authoritative.

**Search the chunks:**

```
python3 <plugin>/scripts/search_docs.py boards/<board>/manual "i2c clock stretching" [-k 5] [--doc NAME]
```

Ranks chunks with BM25 (standard library only; register names such as `I2C_CLKDIV` also match `clkdiv`) and prints the best matches with section path, pages, file path and a snippet. Open only those chunk files.

## Design principles

- **Progressive disclosure**: skill metadata is always loaded, `SKILL.md` stays
  short, detail lives in `references/` and is read only when needed. Deterministic
  work lives in `scripts/` and is executed, not read.
- **Focused answers**: lead with the answer, state assumptions, skip background.
- **Honest about certainty**: every stored value is either given by you,
  verified against a primary source, or marked as an assumption.
- **Mainline first**: knowledge is curated from mainline kernel documentation and
  dt-bindings, not from vendor forks.

## Layout

```
.claude-plugin/plugin.json
skills/
  eldev-router/
  eldev-intake/
scripts/
  check_context.py       readiness check for board/target context
  pdf_to_md.py           PDF manual -> searchable markdown chunks and figures
  search_docs.py         find the right chunk (BM25)
```

More skills and `evals/` are added with their own commits.

Language: skill content is English; replies follow the user's language.

## Contributing

Work in progress. See `CONTRIBUTING.md` for the commit workflow.
