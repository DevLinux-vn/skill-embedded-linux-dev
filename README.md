# embedded-linux-dev

A Claude Code plugin that helps write, build and verify embedded Linux code:
kernel-space drivers and userspace programs for I2C, SPI and UART, together with
the subsystems they depend on (device tree, pinctrl, interrupts, GPIO).

Target boards: Raspberry Pi, BeagleBone Black, Lichee Pi Nano (Allwinner F1C100s).
Target build systems: Yocto, Buildroot.

## Design principles

- **Progressive disclosure**: skill metadata is always loaded, `SKILL.md` stays
  short, detailed knowledge lives in `references/` and is read only when needed.
  Deterministic work lives in `scripts/` and is executed, not read.
- **Focused answers**: ask the minimum needed to identify board, build system,
  kernel version and subsystem; state assumptions instead of rambling.
- **Verifiable**: generated build/test scripts and a log analyser decide whether
  the result actually works.
- **Mainline first**: knowledge is curated from mainline kernel documentation
  and dt-bindings, not from vendor forks.

## Layout (planned)

```
.claude-plugin/plugin.json
skills/
  eldev-router/          intake and routing
  eldev-board-profiles/  per-board facts (SoC, pinout, quirks)
  eldev-buildsys/        Yocto / Buildroot detection and integration
  eldev-kernel-driver/   I2C/SPI/UART drivers, DT, pinctrl, IRQ, GPIO
  eldev-userspace/       userspace programs and service generation
  eldev-log-diagnose/    dmesg / journal / serial log analysis
scripts/                 shared helpers
evals/                   test prompts and assertions
```

Language: skill content is English; replies follow the user's language.

## Status

Work in progress. See `CONTRIBUTING.md` for the commit workflow.
