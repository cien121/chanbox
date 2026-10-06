#!/usr/bin/env python3
"""Config cards v4 polish: expanded country flags + latency quality descriptor.

On top of v3 (patch_config_cards.py). Idempotent via marker.
Requires v3 already applied (checks MARKER_V3 in StatsBar.kt).
"""

import sys

MARKER_V4 = "chanboxConfigCardsV4"
MARKER_V3 = "chanboxConfigCardsV2"
STATSBAR_KT = "app/src/main/java/io/nekohasekai/sagernet/widget/StatsBar.kt"


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _write(path, src):
    with open(path, "w", encoding="utf-8") as f:
        f.write(src)


# ---------------------------------------------------------------- country map
# ISO-ish English names from ip-api.com -> flag emoji + Chinese name.
# v3 had 14; v4 expands to 40 common VPN exit countries.
COUNTRY_WHEN = '''    // ''' + MARKER_V4 + ''': expanded to 40 countries.
    private fun countryLabel(countryEn: String, ip: String): String {
        val name = when (countryEn.lowercase()) {
            "united states" -> "\\uD83C\\uDDFA\\uD83C\\uDDF8 \\u7F8E\\u56FD"
            "japan" -> "\\uD83C\\uDDEF\\uD83C\\uDDF5 \\u65E5\\u672C"
            "singapore" -> "\\uD83C\\uDDF8\\uD83C\\uDDEC \\u65B0\\u52A0\\u5761"
            "germany" -> "\\uD83C\\uDDE9\\uD83C\\uDDEA \\u5FB7\\u56FD"
            "united kingdom" -> "\\uD83C\\uDDEC\\uD83C\\uDDE7 \\u82F1\\u56FD"
            "france" -> "\\uD83C\\uDDEB\\uD83C\\uDDF7 \\u6CD5\\u56FD"
            "netherlands" -> "\\uD83C\\uDDF3\\uD83C\\uDDF1 \\u8377\\u5170"
            "canada" -> "\\uD83C\\uDDE8\\uD83C\\uDDE6 \\u52A0\\u62FF\\u5927"
            "australia" -> "\\uD83C\\uDDE6\\uD83C\\uDDFA \\u6FB3\\u5927\\u5229\\u4E9A"
            "south korea", "korea" -> "\\uD83C\\uDDF0\\uD83C\\uDDF7 \\u97E9\\u56FD"
            "hong kong" -> "\\uD83C\\uDDED\\uD83C\\uDDF0 \\u9999\\u6E2F"
            "taiwan" -> "\\uD83C\\uDDF9\\uD83C\\uDDFC \\u53F0\\u6E7E"
            "russia" -> "\\uD83C\\uDDF7\\uD83C\\uDDFA \\u4FC4\\u7F57\\u65AF"
            "india" -> "\\uD83C\\uDDEE\\uD83C\\uDDF3 \\u5370\\u5EA6"
            "ireland" -> "\\uD83C\\uDDEE\\uD83C\\uDDEA \\u7231\\u5C14\\u5170"
            "sweden" -> "\\uD83C\\uDDF8\\uD83C\\uDDEA \\u745E\\u5178"
            "switzerland" -> "\\uD83C\\uDDE8\\uD83C\\uDDED \\u745E\\u58EB"
            "norway" -> "\\uD83C\\uDDF3\\uD83C\\uDDF4 \\u632A\\u5A01"
            "finland" -> "\\uD83C\\uDDEB\\uD83C\\uDDEE \\u82AC\\u5170"
            "denmark" -> "\\uD83C\\uDDE9\\uD83C\\uDDF0 \\u4E39\\u9EA6"
            "poland" -> "\\uD83C\\uDDF5\\uD83C\\uDDF1 \\u6CE2\\u5170"
            "spain" -> "\\uD83C\\uDDEA\\uD83C\\uDDF8 \\u897F\\u73ED\\u7259"
            "italy" -> "\\uD83C\\uDDEE\\uD83C\\uDDF9 \\u610F\\u5927\\u5229"
            "portugal" -> "\\uD83C\\uDDF5\\uD83C\\uDDF9 \\u8461\\u8404\\u7259"
            "belgium" -> "\\uD83C\\uDDE7\\uD83C\\uDDEA \\u6BD4\\u5229\\u65F6"
            "austria" -> "\\uD83C\\uDDE6\\uD83C\\uDDF9 \\u5965\\u5730\\u5229"
            "czech republic", "czechia" -> "\\uD83C\\uDDE8\\uD83C\\uDDFF \\u6377\\u514B"
            "hungary" -> "\\uD83C\\uDDED\\uD83C\\uDDFA \\u5308\\u7259\\u5229"
            "romania" -> "\\uD83C\\uDDF7\\uD83C\\uDDF4 \\u7F57\\u9A6C\\u5C3C\\u4E9A"
            "greece" -> "\\uD83C\\uDDEC\\uD83C\\uDDF7 \\u5E0C\\u814A"
            "turkey" -> "\\uD83C\\uDDF9\\uD83C\\uDDF7 \\u571F\\u8033\\u5176"
            "israel" -> "\\uD83C\\uDDEE\\uD83C\\uDDF1 \\u4EE5\\u8272\\u5217"
            "united arab emirates" -> "\\uD83C\\uDDE6\\uD83C\\uDDEA \\u963F\\u8054\\u914B"
            "saudi arabia" -> "\\uD83C\\uDDF8\\uD83C\\uDDE6 \\u6C99\\u7279"
            "thailand" -> "\\uD83C\\uDDF9\\uD83C\\uDDED \\u6CF0\\u56FD"
            "malaysia" -> "\\uD83C\\uDDF2\\uD83C\\uDDFE \\u9A6C\\u6765\\u897F\\u4E9A"
            "indonesia" -> "\\uD83C\\uDDEE\\uD83C\\uDDE9 \\u5370\\u5C3C"
            "philippines" -> "\\uD83C\\uDDF5\\uD83C\\uDDED \\u83F2\\u5F8B\\u5BBE"
            "vietnam" -> "\\uD83C\\uDDFB\\uD83C\\uDDF3 \\u8D8A\\u5357"
            "new zealand" -> "\\uD83C\\uDDF3\\uD83C\\uDDFF \\u65B0\\u897F\\u5170"
            "mexico" -> "\\uD83C\\uDDF2\\uD83C\\uDDFD \\u58A8\\u897F\\u54E5"
            "brazil" -> "\\uD83C\\uDDE7\\uD83C\\uDDF7 \\u5DF4\\u897F"
            "argentina" -> "\\uD83C\\uDDE6\\uD83C\\uDDF7 \\u963F\\u6839\\u5EF7"
            "chile" -> "\\uD83C\\uDDE8\\uD83C\\uDDF1 \\u667A\\u5229"
            "south africa" -> "\\uD83C\\uDDFF\\uD83C\\uDDE6 \\u5357\\u975E"
            "egypt" -> "\\uD83C\\uDDEA\\uD83C\\uDDEC \\u57C3\\u53CA"
            "china" -> "\\uD83C\\uDDE8\\uD83C\\uDDF3 \\u4E2D\\u56FD"
            else -> "\\uD83C\\uDF0D " + countryEn
        }
        return name + " \\u00B7 " + ip
    }'''


def patch_country_label(root):
    path = root + "/" + STATSBAR_KT
    src = _read(path)
    if MARKER_V4 in src:
        print("countryLabel already v4, skip")
        return
    assert MARKER_V3 in src, "v3 marker not found; apply patch_config_cards.py first"
    # find v3 countryLabel function and replace it
    start_anchor = "// " + MARKER_V3 + ": flag + Chinese country name"
    i = src.index(start_anchor)
    # find the end: the closing "    }" of the function (followed by blank line + next comment)
    # the function ends with '        return name + " \\u00B7 " + ip\n    }'
    end_anchor = '        return name + " \\u00B7 " + ip\n    }'
    j = src.index(end_anchor, i)
    j_end = j + len(end_anchor)
    src = src[:i] + COUNTRY_WHEN + src[j_end:]
    _write(path, src)
    print("countryLabel expanded to 40 countries OK")


# ---------------------------------------------------------------- latency quality
def patch_latency_quality(root):
    path = root + "/" + STATSBAR_KT
    src = _read(path)
    if MARKER_V4 + ":latencyQuality" in src:
        print("latency quality already added, skip")
        return
    # add helper function after updateLatencyPill; hook into ping text setters
    anchor = "// " + MARKER_V3 + ": latency pill color tells line quality at a glance."
    assert anchor in src, "latency pill anchor not found"
    helper = anchor + "\n" + '''    // ''' + MARKER_V4 + ''':latencyQuality Chinese quality word for the ping pill.
    private fun latencyQuality(ms: Int): String {
        if (ms < 0) return ""
        return when {
            ms < 80 -> " \\u00B7 \\u6781\\u901F"
            ms < 150 -> " \\u00B7 \\u6D41\\u7545"
            ms < 300 -> " \\u00B7 \\u4E00\\u822C"
            else -> " \\u00B7 \\u8F83\\u6162"
        }
    }
'''
    src = src.replace(anchor, helper, 1)
    # hook 1: ping text set after test ("\" + elapsed + \"ms\"")
    old1 = 'cardPingValue.text = "" + elapsed + "ms"'
    assert src.count(old1) == 1, "ping text setter anchor not found"
    src = src.replace(old1, 'cardPingValue.text = "" + elapsed + "ms" + latencyQuality(elapsed)', 1)
    _write(path, src)
    print("latency quality descriptor added OK")


def main():
    root = "."
    patch_country_label(root)
    patch_latency_quality(root)
    print("ALL CONFIG-CARDS V4 PATCHES OK")


if __name__ == "__main__":
    main()
