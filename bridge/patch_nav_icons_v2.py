#!/usr/bin/env python3
"""Bottom nav icons: second enlargement (2026-10-06).

User request: "还是小" - after #113 enlarged bottom nav icons (config/route/
group/settings) from 20dp to 28dp, user says still too small. Enlarge again.

Changes (layout_main.xml, bottom_bar):
   - nav icon ImageView: 28dp -> 36dp
   - nav pill FrameLayout: 56x36dp -> 64x44dp (room for the bigger icon)
   - nav label TextView: 10sp -> 11sp, marginTop 3dp -> 4dp

Idempotent via marker. Requires patch_compact.py applied first (#113 state).
"""

import re

MARKER = "chanboxCompact"
V2_MARKER = MARKER + ":navicons-v2"
BAR_MARKER = "chanboxStartButtonBottom: bottom bar"

LAYOUT_MAIN = "app/src/main/res/layout/layout_main.xml"

NAV_IDS = ["config", "route", "group", "settings"]


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _write(path, src):
    with open(path, "w", encoding="utf-8") as f:
        f.write(src)


def patch_nav_icons_v2(root):
    """Enlarge the 4 bottom nav icons again (28dp -> 36dp)."""
    path = root + "/" + LAYOUT_MAIN
    src = _read(path)
    if V2_MARKER in src:
        print("nav icons v2 already enlarged, skip")
        return src
    assert MARKER + ":navicons" in src, \
        "patch_compact.py must run first (#113 navicons state)"
    for item in NAV_IDS:
        # --- pill FrameLayout 56x36dp -> 64x44dp (opening tag only) ---
        pill_id = 'android:id="@+id/bottom_nav_%s_pill"' % item
        pid = src.index(pill_id)
        fstart = src.rindex("<FrameLayout", 0, pid)
        fend = src.index(">", pid)
        ftag = src[fstart : fend + 1]
        assert ftag.count('"56dp"') == 1 and ftag.count('"36dp"') == 1, \
            "pill size changed for " + item + " (not #113 state?)"
        src = (
            src[:fstart]
            + ftag.replace('"56dp"', '"64dp"').replace('"36dp"', '"44dp"')
            + src[fend + 1 :]
        )
        # --- icon ImageView 28dp -> 36dp (block anchored by unique id) ---
        icon_id = 'android:id="@+id/bottom_nav_%s_icon"' % item
        m = re.search(re.escape(icon_id) + r'.*?\n(.*?)/>', src, re.S)
        assert m, "icon block not found for " + item
        block = m.group(0)
        assert block.count('"28dp"') == 2, \
            "icon 28dp count changed for " + item + " (not #113 state?)"
        new_block = block.replace('"28dp"', '"36dp"')
        src = src.replace(block, new_block, 1)
        # --- label TextView 10sp -> 11sp, marginTop 3dp -> 4dp ---
        label_id = 'android:id="@+id/bottom_nav_%s_label"' % item
        m = re.search(re.escape(label_id) + r'.*?\n(.*?)/>', src, re.S)
        assert m, "label block not found for " + item
        block = m.group(0)
        assert block.count('"10sp"') == 1 and block.count('"3dp"') == 1, \
            "label size changed for " + item + " (not #113 state?)"
        new_block = block.replace('"10sp"', '"11sp"').replace('"3dp"', '"4dp"')
        src = src.replace(block, new_block, 1)
        print("  nav %s: icon 36dp, pill 64x44dp, label 11sp" % item)
    # marker comment after the v1 navicons marker
    idx = src.index(MARKER + ":navicons")
    cend = src.index("-->", idx) + len("-->")
    src = (
        src[:cend]
        + "\n        <!-- " + V2_MARKER + " bottom nav icons enlarged again -->"
        + src[cend:]
    )
    _write(path, src)
    return src


def main():
    root = "."
    patch_nav_icons_v2(root)
    print("ALL NAV ICONS V2 PATCHES OK")


if __name__ == "__main__":
    main()
