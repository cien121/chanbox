#!/usr/bin/env python3
"""Fix #109 startup crash (NB4A Crash on launch).

Root cause: patch_start_button_bottom.py changed StatsBar's dashboard bindings
from this.findViewById(...) to (context as MainActivity).findViewById(...).
But MainActivity.onCreate calls binding.stats.setOnClickListener() BEFORE
setContentView(binding.root). Activity.findViewById() searches the activity's
current content view, which does not exist yet at that point, so every lookup
returns null and assigning null to a non-null lateinit var throws an instant
NullPointerException -> app crashes on launch.

Fix: bind via rootView (the inflated binding.root tree) instead of the
Activity's content view. rootView is valid as soon as LayoutMainBinding.inflate
returns, regardless of setContentView order.

Idempotent via marker. Requires patch_start_button_bottom.py applied first.
"""

import sys

MARKER = "chanboxCrashFix"
DASHBOARD_MARKER = ("// chanboxStartButtonBottom:dashboardtop "
                    "dashboard lives in activity layout now.")
STATSBAR_KT = "app/src/main/java/io/nekohasekai/sagernet/widget/StatsBar.kt"


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _write(path, src):
    with open(path, "w", encoding="utf-8") as f:
        f.write(src)


def patch_statsbar_rootview(root):
    path = root + "/" + STATSBAR_KT
    src = _read(path)
    if MARKER in src:
        print("StatsBar.kt crash fix already applied, skip")
        return
    assert DASHBOARD_MARKER in src, "patch_start_button_bottom.py must run first"

    m_start = src.rindex(
        "    override fun setOnClickListener(l: OnClickListener?) {",
        0, src.index(DASHBOARD_MARKER))
    m_end = (src.index("        super.setOnClickListener(l)",
                       src.index(DASHBOARD_MARKER))
             + len("        super.setOnClickListener(l)"))
    block = src[m_start:m_end]
    assert "act.findViewById" in block, "expected act.findViewById bindings"

    block = block.replace("act.findViewById", "rootView.findViewById")
    block = block.replace(
        "        val act = context as MainActivity\n",
        "        // " + MARKER + ": bind via rootView (inflated binding.root tree);\n"
        "        // Activity.findViewById is unsafe here because MainActivity.onCreate\n"
        "        // calls setOnClickListener BEFORE setContentView.\n")

    src = src[:m_start] + block + src[m_end:]
    _write(path, src)
    print("StatsBar.kt crash fix applied OK")


def main():
    patch_statsbar_rootview(".")
    print("ALL CRASH-FIX PATCHES OK")


if __name__ == "__main__":
    main()
