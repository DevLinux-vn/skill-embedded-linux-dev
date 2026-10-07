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
  pdf_to_md.py           PDF manual -> markdown chapters and figures
```

More skills and `evals/` are added with their own commits.

Language: skill content is English; replies follow the user's language.

## Contributing

Work in progress. See `CONTRIBUTING.md` for the commit workflow.
