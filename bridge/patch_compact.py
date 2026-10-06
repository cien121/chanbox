#!/usr/bin/env python3
"""Compact dashboard cards + bigger bottom nav icons (2026-10-06).

User requests:
1. "最下面4的图标需要增大，太小了" - Bottom nav icons (config/route/group/
   settings) are too small; enlarge them.
2. "中间那几张卡片（下载/上传、自动选择、节点配置）再缩小紧凑些，纵向空间不够" -
   Make the middle dashboard cards smaller/more compact; vertical space is tight.

Changes:
A. Bottom nav (layout_main.xml, bottom_bar):
   - nav icon ImageView: 20dp -> 28dp
   - nav pill FrameLayout: 44x28dp -> 56x36dp (room for the bigger icon)
   - nav label TextView: 9sp -> 10sp, marginTop 2dp -> 3dp
B. Dashboard cards (layout_main.xml, chanboxConfigCardsV2 region):
   - card inner padding 14dp -> 10dp; panel outer padding 16dp -> 12dp
   - text sizes: 22sp->18sp (emoji icons), 20sp->17sp (speed values/arrows),
     16sp->14sp, 14sp->13sp, 13sp->12sp, 12sp->11sp, 11sp->10sp
   - vertical margins: 16dp->10dp, 12dp->8dp, 10dp->7dp, 8dp->5dp, 6dp->4dp, 2dp->1dp
   - card corner radius 18dp -> 14dp; speedtest button padding/radius shrunk

Idempotent via marker. Requires patch_ui_tweak.py applied first (bottom bar
with 4 nav items, badge on its own row).
"""

import re
import sys

MARKER = "chanboxCompact"
CARDS_MARKER = "chanboxConfigCardsV2"
BAR_MARKER = "chanboxStartButtonBottom: bottom bar"

LAYOUT_MAIN = "app/src/main/res/layout/layout_main.xml"

NAV_IDS = ["config", "route", "group", "settings"]


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _write(path, src):
    with open(path, "w", encoding="utf-8") as f:
        f.write(src)


def patch_nav_icons(root):
    """Enlarge the 4 bottom nav icons + pills + labels."""
    path = root + "/" + LAYOUT_MAIN
    src = _read(path)
    if MARKER + ":navicons" in src:
        print("nav icons already enlarged, skip")
        return src
    for item in NAV_IDS:
        # --- pill FrameLayout 44x28dp -> 56x36dp (opening tag only) ---
        pill_id = 'android:id="@+id/bottom_nav_%s_pill"' % item
        pid = src.index(pill_id)
        fstart = src.rindex("<FrameLayout", 0, pid)
        fend = src.index(">", pid)
        ftag = src[fstart : fend + 1]
        assert ftag.count('"44dp"') == 1 and ftag.count('"28dp"') == 1, \
            "pill size changed for " + item
        src = (
            src[:fstart]
            + ftag.replace('"44dp"', '"56dp"').replace('"28dp"', '"36dp"')
            + src[fend + 1 :]
        )
        # --- icon ImageView 20dp -> 28dp (block anchored by unique id) ---
        icon_id = 'android:id="@+id/bottom_nav_%s_icon"' % item
        m = re.search(re.escape(icon_id) + r'.*?\n(.*?)/>', src, re.S)
        assert m, "icon block not found for " + item
        block = m.group(0)
        assert block.count('"20dp"') == 2, "icon 20dp count changed for " + item
        new_block = block.replace('"20dp"', '"28dp"')
        src = src.replace(block, new_block, 1)
        # --- label TextView 9sp -> 10sp, marginTop 2dp -> 3dp ---
        label_id = 'android:id="@+id/bottom_nav_%s_label"' % item
        m = re.search(re.escape(label_id) + r'.*?\n(.*?)/>', src, re.S)
        assert m, "label block not found for " + item
        block = m.group(0)
        assert block.count('"9sp"') == 1 and block.count('"2dp"') == 1, \
            "label size changed for " + item
        new_block = block.replace('"9sp"', '"10sp"').replace('"2dp"', '"3dp"')
        src = src.replace(block, new_block, 1)
        print("  nav %s: icon 28dp, pill 56x36dp, label 10sp" % item)
    # marker comment after the bottom bar marker comment
    idx = src.index(BAR_MARKER)
    cend = src.index("-->", idx) + len("-->")
    src = (
        src[:cend]
        + "\n        <!-- " + MARKER + ":navicons bottom nav icons enlarged -->"
        + src[cend:]
    )
    _write(path, src)
    return src


def patch_dashboard_compact(root):
    """Shrink dashboard cards (vertical compactness)."""
    path = root + "/" + LAYOUT_MAIN
    src = _read(path)
    if MARKER + ":cards" in src:
        print("dashboard cards already compact, skip")
        return
    start = src.index("<!-- " + CARDS_MARKER)
    end = src.index("<!-- " + BAR_MARKER)
    region = src[start:end]

    # (old, new, expected_count) - applied in cascade-safe ascending order
    repls = [
        ('android:textSize="11sp"', 'android:textSize="10sp"', 4),
        ('android:textSize="12sp"', 'android:textSize="11sp"', 6),
        ('android:textSize="13sp"', 'android:textSize="12sp"', 2),
        ('android:textSize="14sp"', 'android:textSize="13sp"', 3),
        ('android:textSize="16sp"', 'android:textSize="14sp"', 2),
        ('android:textSize="20sp"', 'android:textSize="17sp"', 4),
        ('android:textSize="22sp"', 'android:textSize="18sp"', 3),
        ('android:layout_marginTop="2dp"', 'android:layout_marginTop="1dp"', 4),
        ('android:layout_marginTop="6dp"', 'android:layout_marginTop="4dp"', 2),
        ('android:layout_marginTop="8dp"', 'android:layout_marginTop="5dp"', 3),
        ('android:layout_marginTop="10dp"', 'android:layout_marginTop="7dp"', 1),
        ('android:layout_marginTop="12dp"', 'android:layout_marginTop="8dp"', 2),
        ('android:layout_marginTop="16dp"', 'android:layout_marginTop="10dp"', 1),
        ('android:padding="14dp"', 'android:padding="10dp"', 4),
        ('android:padding="16dp"', 'android:padding="12dp"', 1),
        ('app:cardCornerRadius="18dp"', 'app:cardCornerRadius="14dp"', 4),
        ('android:paddingLeft="18dp"', 'android:paddingLeft="14dp"', 1),
        ('android:paddingRight="18dp"', 'android:paddingRight="14dp"', 1),
        ('android:paddingTop="9dp"', 'android:paddingTop="7dp"', 1),
        ('android:paddingBottom="9dp"', 'android:paddingBottom="7dp"', 1),
        ('app:cornerRadius="14dp"', 'app:cornerRadius="12dp"', 1),
    ]
    for old, new, want in repls:
        got = region.count(old)
        assert got == want, "dashboard %s: found %d, want %d" % (old, got, want)
        region = region.replace(old, new)
    print("  dashboard cards compacted (%d replacements)" % len(repls))

    src = src[:start] + region + src[end:]
    cards_comment = "<!-- " + CARDS_MARKER
    assert src.count(cards_comment) == 1, "cards marker comment not found"
    src = src.replace(
        cards_comment,
        "<!-- " + MARKER + ":cards dashboard cards compact -->\n"
        + " " * 24
        + cards_comment,
        1,
    )
    _write(path, src)
    print("  dashboard cards marker added")


def main():
    root = "."
    patch_nav_icons(root)
    patch_dashboard_compact(root)
    print("ALL COMPACT PATCHES OK")


if __name__ == "__main__":
    main()
