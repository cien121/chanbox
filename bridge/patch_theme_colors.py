#!/usr/bin/env python3
"""Patch NekoBox theme: keep only black/blue/purple; black skin is pure black.

User requests:
1. Theme color picker (ColorPickerPreference) shows only black, blue, purple.
2. The black theme ("skin") must be pure black (#000000), not dark gray.

Background:
- app/src/main/res/values/colors.xml defines integer-array "material_colors"
  (21 entries). ColorPickerPreference.kt builds the picker grid from this
  array and persists the 1-based index as the theme id (see "Theme.kt" comment
  in that file).
- colors.xml already defines <color name="black">#FF000000</color> (pure
  black), so the picker references @color/black directly; no new color needed.
- app/src/main/res/values/themes.xml defines Theme.SagerNet.Black and
  Theme.SagerNet.Dialog.Black on top of color_ng_black_primary (#2B2B2B, dark
  gray). Pure-black skin: point their primaries/backgrounds at @color/black.
  color_ng_black_primary is used ONLY inside these two Black styles.
- app/src/main/java/io/nekohasekai/sagernet/utils/Theme.kt maps the theme id
  (constants RED=1 ... BLACK=21) to R.style themes, with default PINK_SSR.

Changes (all under the NekoBox checkout, run from its root):

1. app/src/main/res/values/colors.xml
   - material_colors integer-array trimmed to 3 entries, in user-listed order:
     black (@color/black, pure black #000000),
     blue (@color/material_blue_500), purple (@color/material_purple_500).
   - NOTE: .github/workflows/build.yml runs pink->blue hex seds on this file
     BEFORE integrate.sh, but those only touch pink hex values (#E91E63 etc.),
     not the @color references used here, so no conflict.

2. app/src/main/res/values/themes.xml
   - In Theme.SagerNet.Black and Theme.SagerNet.Dialog.Black:
     replace @color/color_ng_black_primary with @color/black, and add
     android:windowBackground + colorSurface = @color/black.
   - Accent stays color_ng_black_accent (gray) so FAB/selection stay visible.

3. app/src/main/java/io/nekohasekai/sagernet/utils/Theme.kt
   - constants remapped to the new 1-based array indices:
     BLACK=1, BLUE=2, PURPLE=3
   - defaultTheme() changed PINK_SSR -> BLUE (blue is the app's theme color)
   - getTheme()/getDialogTheme() when-branches trimmed to the three colors;
     any stale stored value (e.g. old ids 1..21) falls into `else` and lands
     on the blue default. Unset preference (0) also lands on blue.
   - Theme constants are only referenced inside Theme.kt itself
     (SettingsPreferenceFragment/ThemedActivity only call Theme.getTheme(int)
     / Theme.apply()), so the rewrite is safe.

Idempotent: re-running is a no-op (marker comments left in each file).
"""

import re
import sys

COLORS_XML = "app/src/main/res/values/colors.xml"
THEMES_XML = "app/src/main/res/values/themes.xml"
THEME_KT = "app/src/main/java/io/nekohasekai/sagernet/utils/Theme.kt"
MARKER = "themeColorsBlackBluePurple"
PURE_BLACK_MARKER = "themePureBlackSkin"

NEW_ARRAY = """    <integer-array name="material_colors">
        <!-- themeColorsBlackBluePurple: picker keeps only black/blue/purple -->
        <item>@color/black</item>
        <item>@color/material_blue_500</item>
        <item>@color/material_purple_500</item>
    </integer-array>"""

NEW_CONSTANTS = """    // themeColorsBlackBluePurple: picker keeps only black/blue/purple
    const val BLACK = 1
    const val BLUE = 2
    const val PURPLE = 3
"""

OLD_CONSTANTS_RE = re.compile(
    r"    const val RED = 1\n"
    r"(?:    const val \w+ = \d+\n)+"
    r"    const val BLACK = 21\n"
)

NEW_GET_THEME = """    fun getTheme(theme: Int): Int {
        return when (theme) {
            BLACK -> R.style.Theme_SagerNet_Black
            BLUE -> R.style.Theme_SagerNet_Blue
            PURPLE -> R.style.Theme_SagerNet_Purple
            else -> getTheme(defaultTheme())
        }
    }"""

OLD_GET_THEME_RE = re.compile(
    r"    fun getTheme\(theme: Int\): Int \{\n"
    r"        return when \(theme\) \{\n"
    r"(?:.*\n)*?"
    r"        \}\n"
    r"    \}",
)

NEW_GET_DIALOG_THEME = """    fun getDialogTheme(theme: Int): Int {
        return when (theme) {
            BLACK -> R.style.Theme_SagerNet_Dialog_Black
            BLUE -> R.style.Theme_SagerNet_Dialog_Blue
            PURPLE -> R.style.Theme_SagerNet_Dialog_Purple
            else -> getDialogTheme(defaultTheme())
        }
    }"""

OLD_GET_DIALOG_THEME_RE = re.compile(
    r"    fun getDialogTheme\(theme: Int\): Int \{\n"
    r"        return when \(theme\) \{\n"
    r"(?:.*\n)*?"
    r"        \}\n"
    r"    \}",
)

ARRAY_RE = re.compile(
    r"    <integer-array name=\"material_colors\">\n(?:.*\n)*?    </integer-array>"
)

BLACK_STYLE_RE = re.compile(
    r"    <style name=\"Theme\.SagerNet\.(?:Dialog\.)?Black\">\n"
    r"(?:.*\n)*?"
    r"    </style>"
)

PURE_BLACK_ITEMS = (
    "        <!-- %s: pure black skin -->\n"
    "        <item name=\"android:windowBackground\">@color/black</item>\n"
    "        <item name=\"colorSurface\">@color/black</item>\n"
) % PURE_BLACK_MARKER


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _write(path, src):
    with open(path, "w", encoding="utf-8") as f:
        f.write(src)


def patch_colors_xml():
    src = _read(COLORS_XML)
    m = ARRAY_RE.search(src)
    assert m, "material_colors integer-array not found"
    block = m.group(0)
    # already at target state? (3 items, first one pure black)
    if block.count("<item>") == 3 and "@color/black</item>" in block:
        print("colors.xml already patched (pure black), skip")
        return
    src = src[: m.start()] + NEW_ARRAY + src[m.end():]
    _write(COLORS_XML, src)
    print("colors.xml patched: material_colors -> pure black/blue/purple")


def _pure_black_style_block(block):
    if PURE_BLACK_MARKER in block:
        return block
    # primaries/backgrounds -> pure black (color_ng_black_primary is only
    # used inside these two Black styles)
    block = block.replace("@color/color_ng_black_primary", "@color/black")
    block = block.replace("    </style>", PURE_BLACK_ITEMS + "    </style>", 1)
    return block


def patch_themes_xml():
    src = _read(THEMES_XML)
    new_src, n = BLACK_STYLE_RE.subn(
        lambda m: _pure_black_style_block(m.group(0)), src
    )
    assert n == 2, "expected 2 Black style blocks, found %d" % n
    if new_src == src:
        print("themes.xml already patched (pure black skin), skip")
        return
    _write(THEMES_XML, new_src)
    print("themes.xml patched: Black styles -> pure black skin")


def patch_theme_kt():
    src = _read(THEME_KT)
    if MARKER in src:
        print("Theme.kt already patched, skip")
        return

    m = OLD_CONSTANTS_RE.search(src)
    assert m, "Theme.kt constants block not found"
    src = src[: m.start()] + NEW_CONSTANTS + src[m.end():]

    old_default = "private fun defaultTheme() = PINK_SSR"
    assert src.count(old_default) == 1, "defaultTheme() line not found exactly once"
    src = src.replace(old_default, "private fun defaultTheme() = BLUE")

    m = OLD_GET_THEME_RE.search(src)
    assert m, "getTheme() when-block not found"
    src = src[: m.start()] + NEW_GET_THEME + src[m.end():]

    m = OLD_GET_DIALOG_THEME_RE.search(src)
    assert m, "getDialogTheme() when-block not found"
    src = src[: m.start()] + NEW_GET_DIALOG_THEME + src[m.end():]

    _write(THEME_KT, src)
    print("Theme.kt patched: BLACK=1/BLUE=2/PURPLE=3, default BLUE")


def main():
    patch_colors_xml()
    patch_themes_xml()
    patch_theme_kt()
    print("theme colors patch done")


if __name__ == "__main__":
    sys.exit(main())
