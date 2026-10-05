#!/usr/bin/env python3
"""Patch NekoBox libcore/build.sh: stamp sing-box version via ldflags.

Without this, Libcore.versionBox() shows "sing-box: unknown" because
constant.Version defaults to "unknown" in the lx tree.

We append:
    -X github.com/sagernet/sing-box/constant.Version=v1.14.2-lx.11
to the existing -ldflags='-s -w', so it becomes:
    -ldflags='-s -w -X github.com/sagernet/sing-box/constant.Version=v1.14.2-lx.11'

Idempotent. Takes optional path arg (default libcore/build.sh).
"""
import sys

TARGET = "libcore/build.sh"
MARKER = "singboxVersionStamped"
VERSION = "v1.14.2-lx.11"
XFLAG = f"-X github.com/sagernet/sing-box/constant.Version={VERSION}"

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else TARGET
    with open(path) as f:
        src = f.read()
    if MARKER in src or XFLAG in src:
        print("libcore/build.sh sing-box version already stamped, skip")
        return

    old = "-ldflags='-s -w'"
    assert src.count(old) == 1, f"ldflags pattern not found exactly once (found {src.count(old)})"
    new = f"-ldflags='-s -w {XFLAG}' # {MARKER}"
    src = src.replace(old, new)

    with open(path, "w") as f:
        f.write(src)
    print("libcore/build.sh sing-box version stamped OK")

if __name__ == "__main__":
    main()
