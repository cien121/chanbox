#!/usr/bin/env python3
"""Align NekoBox settings defaults with v2rayNG.

User request: ChanBox settings page should match v2rayNG's settings.
v2rayNG reference screenshot: workspace/user/files/1000039280_6_scbp.jpg

Changes to app/src/main/res/xml/global_preferences.xml (default values only):

1. mtu: "9000" -> "1600"
   v2rayNG uses MTU 1600. NekoBox default was 9000.

2. remoteDns: "https://dns.google/dns-query" -> "1.1.1.1"
   v2rayNG uses plain IP 1.1.1.1 for remote DNS.

3. directDns: "https://223.5.5.5/dns-query" -> "223.5.5.5"
   v2rayNG uses plain IP 223.5.5.5 for direct DNS.

4. ipv6Mode: "0" (disable) -> "2" (prefer)
   v2rayNG has "IPv6" ON and "IPv6 priority" ON.
   NekoBox ipv6_mode values: 0=disable, 1=enable, 2=prefer, 3=only.

5. logLevel: "0" (none) -> "1" (warn)
   v2rayNG uses log level "warning".
   NekoBox log_level values: 0=none, 1=warn, 2=info, 3=debug, 4=trace.

NOT changed (v2rayNG-specific or not applicable):
- Mux, Fragment: Xray-specific, not applicable to sing-box core.
- Hev TUN settings: NekoBox uses gVisor/System/Mixed TUN implementations.
- VPN DNS: NekoBox has no separate VPN DNS setting.
- UI preferences (ad blocking, dual-column, etc.): v2rayNG-specific UI.
- Settings page structure/grouping: kept as NekoBox's (functional,
  user is already familiar with it). Only defaults are aligned.

Idempotent: re-running is a no-op (marker comment).
"""
import re

XML_TARGET = "app/src/main/res/xml/global_preferences.xml"
MARKER = "settingsAlignedWithV2rayNG"

# (key, old_default, new_default, description)
# In the XML, app:defaultValue comes before app:key, on separate lines.
CHANGES = [
    ("mtu", "9000", "1600",
     "MTU default 9000 -> 1600 (v2rayNG)"),
    ("remoteDns", "https://dns.google/dns-query", "1.1.1.1",
     "Remote DNS default -> 1.1.1.1 (v2rayNG)"),
    ("directDns", "https://223.5.5.5/dns-query", "223.5.5.5",
     "Direct DNS default -> 223.5.5.5 (v2rayNG)"),
    ("ipv6Mode", "0", "2",
     "IPv6 mode default disable(0) -> prefer(2) (v2rayNG: IPv6 ON + priority ON)"),
    ("logLevel", "0", "1",
     "Log level default none(0) -> warn(1) (v2rayNG: warning)"),
]


def patch_xml(path):
    with open(path, encoding="utf-8") as f:
        src = f.read()
    if MARKER in src:
        print("global_preferences.xml already patched, skip")
        return

    for key, old_default, new_default, desc in CHANGES:
        # Pattern: app:defaultValue="<old>" ... app:key="<key>"
        # Attributes are on separate lines, defaultValue comes before key.
        # Use [^<]*? to stay within a single XML element (no nested tags
        # between attributes of the same preference).
        old_escaped = re.escape(old_default)
        pattern = (
            rf'app:defaultValue="{old_escaped}"'
            rf'([^<]*?)'
            rf'app:key="{key}"'
        )
        replacement = (
            rf'app:defaultValue="{new_default}"'
            rf'\g<1>'
            rf'app:key="{key}"'
        )
        new_src, n = re.subn(pattern, replacement, src, count=1)
        if n != 1:
            print(f"WARNING: key={key} pattern not found exactly once (found {n}), skipping")
            continue
        src = new_src
        print(f"  {desc}")

    # Add marker comment before closing </PreferenceScreen>
    marker_comment = f"\n<!-- {MARKER}: defaults aligned with v2rayNG per user request -->\n"
    src = src.rstrip()
    if src.endswith("</PreferenceScreen>"):
        src = src[:-len("</PreferenceScreen>")].rstrip() + marker_comment + "</PreferenceScreen>\n"

    with open(path, "w", encoding="utf-8") as f:
        f.write(src)
    print("global_preferences.xml patched OK")


if __name__ == "__main__":
    patch_xml(XML_TARGET)
