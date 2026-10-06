---
name: eldev-intake
description: Record and reuse the board and target-module facts that every other embedded Linux skill needs, so source code is not re-read each time. Use at the start of any driver or userspace task on a board, when board facts are missing or incomplete, when the user gives or changes SoC, kernel version, toolchain, build system and commands, device tree, pinout, voltage, flash method, debug access or reference manual, or switches to another board or module.
---

# eldev-intake

Write board and target facts down once, in files in the user's project, so later steps read a few dozen lines instead of the source tree.

## Files

- `<board>/board.yaml`: SoC, kernel, toolchain, build system and commands, flash, debug, voltage.
- `<board>/manual/`: reference manual already converted to markdown, with an `INDEX.md`.
- `<target>/target.yaml`: the one module being worked on.

Put them where the user already keeps board documents; if there is no such place, ask once. A one-line pointer in the project's `CLAUDE.md` says which board and target are active, so a new session finds them without searching (see `assets/example/CLAUDE.md.snippet`). Switching work means editing that pointer.

A filled example (Raspberry Pi 4B + IMX219, Yocto) is in `assets/example/`. Copy it and replace the values; its field names are the schema.

## Workflow

1. Read the pointer in `CLAUDE.md`, then the board and target files it names. Stop if they answer the question.
2. If missing, copy the example and fill it from what the user said, files they point to, then the source tree. Ask once for what is still empty and blocks the task. One module is in scope; ignore the rest.
3. Mark each value with a trailing comment: none means the user gave it, `# verified: <source>` means checked against a primary source, `# assumed` means a guess to confirm before touching hardware. Leave unknown fields empty. User values win and are not silently changed.
4. Do not invent pins, voltages, addresses or build commands. Build and flash commands come from the user's build guide.

## Reference manual

Read `manual/INDEX.md` (chapter, file, one-line summary), then open only the chapters for the module in hand plus directly related ones (I2C work: I2C, GPIO and pinmux, clocks). Never load the whole manual.
