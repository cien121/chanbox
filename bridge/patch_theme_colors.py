#!/usr/bin/env python3
"""Patch NekoBox: black-only theme + mixed per-protocol font colors.

User requests (2026-10-06):
1. App theme keeps ONLY black (blue/purple theme options removed),
   black is pure black (#000000), and black is the default theme.
2. Font colors are "mixed": node-list protocol labels get a distinct color
   per protocol (VLESS blue, Hysteria purple, Trojan orange, ...), complementing
   the existing status colors (latency green / error red).

Background:
- app/src/main/res/values/colors.xml defines integer-array "material_colors"
  (21 entries). ColorPickerPreference.kt builds the picker grid from this
  array and persists the 1-based index as the theme id.
- colors.xml already defines <color name="black">#FF000000</color> (pure
  black), so the picker references @color/black directly.
- app/src/main/res/values/themes.xml defines Theme.SagerNet.Black and
  Theme.SagerNet.Dialog.Black on top of color_ng_black_primary (#2B2B2B).
  Pure-black skin: point their primaries/backgrounds at @color/black.
  color_ng_black_primary is used ONLY inside these two Black styles.
- app/src/main/java/io/nekohasekai/sagernet/utils/Theme.kt maps the theme id
  (constants RED=1 ... BLACK=21) to R.style themes, default PINK_SSR.
- app/src/main/java/moe/matsuri/nb4a/Protocols.kt has
  Context.getProtocolColor(type) used by ConfigurationFragment for the
  protocol label color in the node list (and a ForegroundColorSpan for the
  selected node). Stock version only distinguishes TYPE_NEKO.

Changes (all under the NekoBox checkout, run from its root):

1. app/src/main/res/values/colors.xml
   - material_colors integer-array trimmed to ONE entry: @color/black.

2. app/src/main/res/values/themes.xml
   - In Theme.SagerNet.Black and Theme.SagerNet.Dialog.Black:
     replace @color/color_ng_black_primary with @color/black, and add
     android:windowBackground + colorSurface = @color/black.
   - Accent stays color_ng_black_accent (gray) so FAB/selection stay visible.

3. app/src/main/java/io/nekohasekai/sagernet/utils/Theme.kt
   - constants: only BLACK = 1 (marker themeBlackOnly). Migration-safe:
     matches any run of "const val X = N" lines, so it works on the fresh
     NekoBox file AND on files already patched by the old black/blue/purple
     patch (stale marker comment is removed).
   - defaultTheme() changed to BLACK (regex handles PINK_SSR/BLUE/anything).
   - getTheme()/getDialogTheme() when-branches trimmed to BLACK only;
     any stale stored value (old ids 1..21, old 1..3, or unset 0) falls into
     `else` and lands on black.
   - Theme constants are only referenced inside Theme.kt itself
     (SettingsPreferenceFragment/ThemedActivity only call Theme.getTheme(int)
     / Theme.apply()), so the rewrite is safe.

4. app/src/main/java/moe/matsuri/nb4a/Protocols.kt
   - getProtocolColor(): per-protocol colors (fixed material colors, readable
     on the pure-black theme):
       VMESS/VLESS blue_500, TROJAN orange_500, TROJAN_GO deep_orange_500,
       SS cyan_500, SOCKS grey_400, HTTP teal_500, HYSTERIA purple_500,
       TUIC indigo_500, WG green_500, SSH lime_500, NAIVE yellow_500,
       MIERU pink_500, ANYTLS light_blue_500, SHADOWTLS amber_500,
       CHAIN blue_grey_400, CONFIG brown_500, NEKO textColorPrimary,
       else accentOrTextSecondary (unchanged).
   - Adds imports: ProxyEntity.Companion.* and ktx.getColour.
   - Marker: protocolMixedColors (idempotent).

5. Settings page: remove the "theme" (ColorPickerPreference) item entirely,
   since only black remains and there is nothing to pick.
   - app/src/main/res/xml/global_preferences.xml: drop the
     <moe.matsuri.nb4a.ui.ColorPickerPreference ... app:key="appTheme" />
     block.
   - app/src/main/java/io/nekohasekai/sagernet/ui/SettingsPreferenceFragment.kt:
     drop the findPreference<ColorPickerPreference>(Key.APP_THEME)!! block
     (avoids NPE after the XML removal).
   - Idempotent via target-state checks (block already gone -> skip).

Idempotent: re-running is a no-op (marker comments / target-state checks).
"""

import re
import sys

COLORS_XML = "app/src/main/res/values/colors.xml"
THEMES_XML = "app/src/main/res/values/themes.xml"
THEME_KT = "app/src/main/java/io/nekohasekai/sagernet/utils/Theme.kt"
PROTOCOLS_KT = "app/src/main/java/moe/matsuri/nb4a/Protocols.kt"
SETTINGS_XML = "app/src/main/res/xml/global_preferences.xml"
SETTINGS_KT = "app/src/main/java/io/nekohasekai/sagernet/ui/SettingsPreferenceFragment.kt"
MARKER = "themeBlackOnly"
PURE_BLACK_MARKER = "themePureBlackSkin"
PROTO_COLOR_MARKER = "protocolMixedColors"

NEW_ARRAY = """    <integer-array name="material_colors">
        <!-- themeBlackOnly: picker keeps only black -->
        <item>@color/black</item>
    </integer-array>"""

NEW_CONSTANTS = """    // themeBlackOnly: only black theme
    const val BLACK = 1
"""

NEW_GET_THEME = """    fun getTheme(theme: Int): Int {
        return when (theme) {
            BLACK -> R.style.Theme_SagerNet_Black
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

CONSTANTS_RUN_RE = re.compile(r"(?m)(?:^    const val \w+ = \d+$\n)+")
DEFAULT_THEME_RE = re.compile(r"private fun defaultTheme\(\) = \w+")

OLD_MARKER_COMMENT = "    // themeColorsBlackBluePurple: picker keeps only black/blue/purple\n"

ARRAY_RE = re.compile(
    r'    <integer-array name="material_colors">\n(?:.*\n)*?    </integer-array>'
)

BLACK_STYLE_RE = re.compile(
    r'    <style name="Theme\.SagerNet\.(?:Dialog\.)?Black">\n'
    r"(?:.*\n)*?"
    r"    </style>"
)

PURE_BLACK_ITEMS = (
    "        <!-- %s: pure black skin -->\n"
    '        <item name="android:windowBackground">@color/black</item>\n'
    '        <item name="colorSurface">@color/black</item>\n'
) % PURE_BLACK_MARKER

# --- per-protocol font colors ---

PROTO_COLOR_BODY = """    fun Context.getProtocolColor(type: Int): Int {
        // protocolMixedColors: distinct font color per protocol
        return when (type) {
            TYPE_VMESS -> getColour(R.color.material_blue_500)
            TYPE_TROJAN -> getColour(R.color.material_orange_500)
            TYPE_TROJAN_GO -> getColour(R.color.material_deep_orange_500)
            TYPE_SS -> getColour(R.color.material_cyan_500)
            TYPE_SOCKS -> getColour(R.color.material_grey_400)
            TYPE_HTTP -> getColour(R.color.material_teal_500)
            TYPE_HYSTERIA -> getColour(R.color.material_purple_500)
            TYPE_TUIC -> getColour(R.color.material_indigo_500)
            TYPE_WG -> getColour(R.color.material_green_500)
            TYPE_SSH -> getColour(R.color.material_lime_500)
            TYPE_NAIVE -> getColour(R.color.material_yellow_500)
            TYPE_MIERU -> getColour(R.color.material_pink_500)
            TYPE_ANYTLS -> getColour(R.color.material_light_blue_500)
            TYPE_SHADOWTLS -> getColour(R.color.material_amber_500)
            TYPE_CHAIN -> getColour(R.color.material_blue_grey_400)
            TYPE_CONFIG -> getColour(R.color.material_brown_500)
            TYPE_NEKO -> getColorAttr(android.R.attr.textColorPrimary)
            else -> getColorAttr(R.attr.accentOrTextSecondary)
        }
    }"""

OLD_PROTO_COLOR_RE = re.compile(
    r"    fun Context\.getProtocolColor\(type: Int\): Int \{\n"
    r"(?:.*\n)*?"
    r"    \}\n"
)

IMPORT_WILDCARD = "import io.nekohasekai.sagernet.database.ProxyEntity.Companion.*\n"
IMPORT_GETCOLOUR = "import io.nekohasekai.sagernet.ktx.getColour\n"

# --- settings page: drop the theme picker ---

THEME_PICKER_XML_RE = re.compile(
    r'        <moe\.matsuri\.nb4a\.ui\.ColorPickerPreference\n'
    r"(?:.*\n)*?"
    r' +app:key="appTheme" />\n'
)

APP_THEME_KT_BLOCK_RE = re.compile(
    r"        val appTheme = findPreference<ColorPickerPreference>\(Key\.APP_THEME\)!!\n"
    r"        appTheme\.setOnPreferenceChangeListener \{ _, newTheme ->\n"
    r"(?:.*\n)*?"
    r"        \}\n"
)


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
    if block.count("<item>") == 1 and "@color/black</item>" in block:
        print("colors.xml already black-only, skip")
        return
    src = src[: m.start()] + NEW_ARRAY + src[m.end():]
    _write(COLORS_XML, src)
    print("colors.xml patched: material_colors -> black only")


def _pure_black_style_block(block):
    if PURE_BLACK_MARKER in block:
        return block
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
        print("Theme.kt already black-only, skip")
        return

    # drop stale marker comment left by the old black/blue/purple patch
    src = src.replace(OLD_MARKER_COMMENT, "")

    m = CONSTANTS_RUN_RE.search(src)
    assert m, "Theme.kt constants block not found"
    src = src[: m.start()] + NEW_CONSTANTS + src[m.end():]

    assert DEFAULT_THEME_RE.search(src), "defaultTheme() line not found"
    src = DEFAULT_THEME_RE.sub("private fun defaultTheme() = BLACK", src, count=1)

    m = OLD_GET_THEME_RE.search(src)
    assert m, "getTheme() when-block not found"
    src = src[: m.start()] + NEW_GET_THEME + src[m.end():]

    m = OLD_GET_DIALOG_THEME_RE.search(src)
    assert m, "getDialogTheme() when-block not found"
    src = src[: m.start()] + NEW_GET_DIALOG_THEME + src[m.end():]

    _write(THEME_KT, src)
    print("Theme.kt patched: BLACK=1 only, default BLACK")


def patch_protocols_kt():
    src = _read(PROTOCOLS_KT)
    if PROTO_COLOR_MARKER in src:
        print("Protocols.kt already has mixed protocol colors, skip")
        return

    # add imports (after the package line block, keep it simple: append to
    # the import section)
    if IMPORT_WILDCARD not in src:
        anchor = "import io.nekohasekai.sagernet.ktx.getColorAttr\n"
        assert anchor in src, "import anchor not found in Protocols.kt"
        src = src.replace(anchor, anchor + IMPORT_WILDCARD + IMPORT_GETCOLOUR, 1)

    m = OLD_PROTO_COLOR_RE.search(src)
    assert m, "getProtocolColor() body not found in Protocols.kt"
    src = src[: m.start()] + PROTO_COLOR_BODY + "\n" + src[m.end():]

    _write(PROTOCOLS_KT, src)
    print("Protocols.kt patched: per-protocol mixed font colors")


def patch_settings_remove_theme_picker():
    # 1) XML: drop the ColorPickerPreference block
    src = _read(SETTINGS_XML)
    if 'app:key="appTheme"' not in src:
        print("global_preferences.xml: theme picker already removed, skip")
    else:
        m = THEME_PICKER_XML_RE.search(src)
        assert m, "theme picker block not found in global_preferences.xml"
        src = src[: m.start()] + src[m.end():]
        _write(SETTINGS_XML, src)
        print("global_preferences.xml patched: theme picker removed")

    # 2) Kotlin: drop the findPreference<ColorPickerPreference>(Key.APP_THEME)!!
    #    block (would NPE after the XML removal)
    src = _read(SETTINGS_KT)
    if "findPreference<ColorPickerPreference>(Key.APP_THEME)" not in src:
        print("SettingsPreferenceFragment.kt: appTheme block already removed, skip")
        return
    m = APP_THEME_KT_BLOCK_RE.search(src)
    assert m, "appTheme block not found in SettingsPreferenceFragment.kt"
    src = src[: m.start()] + src[m.end():]
    _write(SETTINGS_KT, src)
    print("SettingsPreferenceFragment.kt patched: appTheme block removed")


def main():
    patch_colors_xml()
    patch_themes_xml()
    patch_theme_kt()
    patch_protocols_kt()
    patch_settings_remove_theme_picker()
    print("theme black-only + mixed font colors + no theme picker patch done")


if __name__ == "__main__":
    sys.exit(main())
