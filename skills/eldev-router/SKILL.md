---
name: eldev-router
description: Entry point for embedded Linux development work. Use this skill first whenever the user wants to write, port, build, debug or integrate a Linux kernel driver or a userspace program for an embedded board (Raspberry Pi, BeagleBone Black, Lichee Pi Nano / Allwinner, or any SoC), including I2C, SPI, UART, GPIO, interrupts, pinctrl, device tree, Yocto, Buildroot, systemd services, or reading dmesg/serial logs to check whether something works. It identifies board, build system, kernel version and subsystem with the fewest possible questions, then hands off to the right specialised skill. Trigger even when the user only describes a device ("I have a sensor on SPI") without saying "driver".
---

# eldev-router

Identify what the user is building and where it will run, then route. Do not write driver or app code in this skill; the specialised skills do that with the right context loaded.

## Why this skill exists

Every later decision depends on four facts: the **board/SoC**, the **build system**, the **kernel version**, and the **target** (which subsystem, kernel or userspace). Getting one wrong produces code that compiles but does not fit (wrong DT compatible, wrong recipe layer, API removed in that kernel). Collect them cheaply, once.

## Step 1: Infer before asking

Look at what is already available (repo, user message, pasted logs) and fill the table below. Only ask for what stays unknown.

| Fact | Where to look |
|---|---|
| Build system | `conf/local.conf` + `conf/bblayers.conf` or `meta-*` dirs: Yocto. Top-level `Config.in` + `package/` + `board/`, or `BR2_` in `.config`/`defconfig`: Buildroot. Kernel tree (`Kbuild`, `arch/`, `Documentation/`): bare kernel. None: native/cross build |
| Board / SoC | user message; `MACHINE =` in Yocto; `BR2_*` defconfig name; `compatible` in DT; `/proc/device-tree/model` in a log |
| Kernel version | `uname -r` in a log; `PREFERRED_VERSION_linux-*` or `LINUX_VERSION` / `BR2_LINUX_KERNEL_*`; top of kernel `Makefile` |
| Target | kernel driver, userspace app, DT only, build integration, or log diagnosis |
| Device | part number and bus (I2C address, SPI mode and speed, UART baud and framing) |

## Step 2: Ask at most three questions

Ask only what blocks progress, in one message, with a suggested default for each so the user can reply "ok". If something is missing but not blocking, assume a default, say so in one line, and continue.

When the kernel version is unknown, assume the version shipped by the board's profile and state it. A wrong assumption here is the most common source of API mismatches, so always state it.

## Step 3: Route

| Request | Go to |
|---|---|
| Kernel driver, device tree node, pinctrl, IRQ, GPIO consumer | `eldev-kernel-driver` |
| Userspace app (libgpiod, i2c-dev, spidev, termios), systemd/init service | `eldev-userspace` |
| Add to Yocto or Buildroot, kernel config, overlays, recipes | `eldev-buildsys` |
| Board pinout, SoC quirks, which kernel the board uses | `eldev-board-profiles` |
| Log or dmesg says it works or not | `eldev-log-diagnose` |

A request often needs several (a driver plus its Yocto recipe plus a log check). Hand off in the order the work happens, loading each only when reached.

If a listed skill is not installed yet, say which one is missing and continue with general knowledge, flagging lower confidence.

## Step 4: Answer shape

Keep it on target. Lead with the answer or the artifact, then the minimum explanation. Use this order:

1. One line stating the assumptions (board, build system, kernel version, target).
2. The deliverable (code, config, commands).
3. How to verify it, naming the exact log line or command output that means success.

Skip background lectures the user did not ask for. If the user's request is ambiguous between two reasonable readings, pick the likelier one, state it, and offer the other in one line.

## Userspace vs kernel

If the device can be handled from userspace (`/dev/i2c-*`, `spidev`, `/dev/tty*`, libgpiod) and the user has no need for in-kernel integration (iio, input, hwmon, ...), say so once and recommend userspace, since it is faster to iterate and safer. Recommend a kernel driver when the device belongs in an existing subsystem or needs interrupts with tight latency.
