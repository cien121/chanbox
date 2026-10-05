#!/usr/bin/env python3
"""Hide the sing-box version row in NekoBox About page.

The About page (AboutFragment.kt) shows a "sing-box" version item via
Libcore.versionBox(). User wants this row hidden entirely - only the
App version (a1) should remain.

We remove the .addItem(...) block that displays version_x "sing-box".
Build tags in the Go build (with_xhttp etc.) are untouched.

Idempotent. Takes optional path arg (default AboutFragment.kt).
"""
import sys

TARGET = "app/src/main/java/io/nekohasekai/sagernet/ui/AboutFragment.kt"
MARKER = "singboxVersionRowHidden"

# The exact block to remove (24-space indent for .addItem)
BLOCK = """                        .addItem(
                            MaterialAboutActionItem.Builder()
                                .icon(R.drawable.ic_baseline_layers_24)
                                .text(getString(R.string.version_x, "sing-box"))
                                .subText(Libcore.versionBox())
                                .setOnClickAction { }
                                .build())
"""

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else TARGET
    # Backward compat: old integrate.sh passed "libcore/build.sh"; ignore it
    if path.endswith("build.sh"):
        path = TARGET
    with open(path) as f:
        src = f.read()
    if MARKER in src:
        print("AboutFragment.kt sing-box version row already hidden, skip")
        return
    if "version_x, \"sing-box\"" not in src:
        # Already removed by other means; mark and exit
        print("sing-box version block not found, assuming already hidden")
        return

    assert src.count(BLOCK) == 1, f"sing-box version block not found exactly once (found {src.count(BLOCK)})"
    src = src.replace(BLOCK, f"                        // {MARKER}: sing-box version row hidden per user request\n")

    with open(path, "w") as f:
        f.write(src)
    print("AboutFragment.kt sing-box version row hidden OK")

if __name__ == "__main__":
    main()
