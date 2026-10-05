#!/usr/bin/env python3
"""Patch NekoBox SagerNet.kt: show clean version "a1".

Original logic appends PRE_VERSION_NAME when FLAVOR == "preview":
    var n = BuildConfig.VERSION_NAME            // "1.4.2"
    if (isPreview) {
        n += " " + BuildConfig.PRE_VERSION_NAME // " pre-1.4.2-20260202-1"
    } ...

ChanBox wants just "a1" displayed. Replace the whole lambda body.
"""
import sys

TARGET = "app/src/main/java/io/nekohasekai/sagernet/SagerNet.kt"
MARKER = "versionDisplayPatchedA1"

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else TARGET
    with open(path) as f:
        src = f.read()
    if MARKER in src:
        print("SagerNet.kt version display already patched, skip")
        return

    old = """        var appVersionNameForDisplay = {
            var n = BuildConfig.VERSION_NAME
            if (isPreview) {
                n += " " + BuildConfig.PRE_VERSION_NAME
            } else if (!isOss) {
                n += " ${BuildConfig.FLAVOR}"
            }
            if (BuildConfig.DEBUG) {
                n += " DEBUG"
            }
            n
        }()"""
    assert src.count(old) == 1, f"version block not found exactly once (found {src.count(old)})"
    new = """        // %s: ChanBox shows fixed version "a1"
        var appVersionNameForDisplay = {
            "a1"
        }()""" % MARKER
    src = src.replace(old, new)

    with open(path, "w") as f:
        f.write(src)
    print("SagerNet.kt version display patched OK")

if __name__ == "__main__":
    main()
