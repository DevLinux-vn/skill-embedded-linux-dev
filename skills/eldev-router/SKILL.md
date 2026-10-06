---
name: eldev-router
description: Entry point for embedded Linux development work. Use this skill first whenever the user wants to write, port, bring up, build, integrate or debug a Linux kernel driver (external device on I2C/SPI/UART, or a SoC peripheral/platform driver) or a userspace program on an embedded board, or to check dmesg/serial logs to see whether it works. It reads the stored board and target context, decides which specialised skill handles the request, and keeps the answer focused. Trigger even when the user only describes a device ("my camera does not show up", "sensor on SPI") without saying "driver".
---

# eldev-router

Decide what the request is and hand it to the right skill. Do not write driver or app code here.

## Step 1: Load context, do not re-ask

Read the board/target pointer in the project's `CLAUDE.md`, then the board and target files it names. These hold SoC, kernel version, toolchain, build system and commands, flash and debug access, voltage and the module being worked on, so the user is not asked again and the source tree is not re-read.

If the pointer or files are missing or empty where the task needs them, use `eldev-intake` to fill them, then continue. Ask only for what is still unknown and blocks the work.

## Step 2: Classify

- **Kind** comes from the target file: `external` (device wired to the board) or `platform` (peripheral inside the SoC).
- **Goal** comes from the user's prompt: write, port or modify, bring up, debug, userspace app, or integrate into the build.

Work on the one module named. Do not widen to other modules or subsystems the user did not ask about.

## Step 3: Route

| Goal | Go to |
|---|---|
| Write or modify a driver for an external device | `eldev-driver-external` |
| Write or modify a driver for a SoC peripheral | `eldev-driver-platform` |
| Userspace app (libgpiod, i2c-dev, spidev, termios, v4l2/libcamera), service | `eldev-userspace` |
| Put code into the user's tree and build with their commands | `eldev-integrate` |
| Not working, choose debug tools, capture data | `eldev-debug` |
| Log or dmesg is available, decide pass or fail | `eldev-log-diagnose` |

Most real tasks chain several: write, integrate, build, deploy, capture log, diagnose, fix. Hand off in that order, loading each skill only when reached, and loop back to the fix step if the log shows a failure.

If a listed skill is not installed yet, say which one is missing and continue with general knowledge, flagging lower confidence.

## Step 4: Answer shape

Lead with the answer or the artifact, then the minimum explanation:

1. One line of assumptions, naming anything marked `assumed` in the context that the answer depends on.
2. The deliverable (code, config, commands).
3. How to verify: the exact log line or command output that means success.

Skip background the user did not ask for. If a request has two reasonable readings, pick the likelier, say so, and offer the other in one line.

## Userspace or kernel

If the device can be driven from userspace (`/dev/i2c-*`, spidev, tty, libgpiod) and the user does not need in-kernel integration, mention it once and continue with what they asked. Do not redirect them away from the kernel driver they requested.
