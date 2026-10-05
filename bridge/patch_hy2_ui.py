#!/usr/bin/env python3
"""Patch NekoBox protocol edit UIs to match v2rayNG style.

User request: Hysteria2 node edit UI (and other protocols: VLESS/VMess/
Trojan/Shadowsocks) should match v2rayNG's field order, labels and hints.

v2rayNG Hysteria2 field order (from user screenshot):
  1. 别名 (remarks)
  2. 地址 (address)
  3. 端口 (port)
  4. 密码
  5. 混淆密码
  6. 跳跃端口 (会覆盖服务器端口)   <- NekoBox merges into serverPorts (supports ranges)
  7. 端口跳跃间隔 (秒)
  8. 带宽下行 (支持的单位 k/m/g/t)
  9. 带宽上行 (支持的单位 k/m/g/t)
  10. 跳过证书验证 (allowInsecure)
  11. SNI
  12. echConfigList            <- NOT supported by sing-box Hysteria2, skipped
  13. 证书指纹 (SHA-256)        <- NOT supported by sing-box Hysteria2, skipped
  14. FinalMask                <- NOT supported by sing-box Hysteria2, skipped

Changes (run from NekoBox checkout root):

1. app/src/main/res/xml/hysteria_preferences.xml
   Reorder PreferenceCategory children to v2rayNG order:
   serverAddress, serverPorts, serverPassword, serverObfs, hopInterval,
   serverDownloadSpeed, serverUploadSpeed, serverAllowInsecure, serverSNI,
   serverCertificates, then Hy1-only fields (serverAuthType, serverProtocol,
   serverALPN, windows, mtu discovery) at the end.
   (profileName + protocolVersion stay at top; visibility logic in
   HysteriaSettingsActivity.kt is key-based, unaffected by order.)

2. app/src/main/res/values-zh-rCN/strings.xml  (shared across protocols)
   profile_name:      配置名称 -> 别名 (remarks)
   server_address:    服务器 -> 地址 (address)
   server_port:       服务器端口 -> 端口 (port)
   sni:               服务器名称指示 -> SNI
   allow_insecure:    允许不安全的连接 -> 跳过证书验证 (allowInsecure)
   hop_interval:      端口跳跃间隔(秒) -> 端口跳跃间隔 (秒)
   hysteria_upload_mbps:   最大上行 (Mbps) -> 带宽上行 (支持的单位 k/m/g/t)
   hysteria_download_mbps: 最大下行 (Mbps) -> 带宽下行 (支持的单位 k/m/g/t)

3. app/src/main/res/values/strings.xml (English, shared across protocols)
   profile_name:      Profile Name -> Remarks
   server_address:    Server -> Address
   server_port:       Remote Port -> Port
   sni:               Server Name Indication -> SNI
   allow_insecure:    Allow Insecure -> Skip certificate verification (allowInsecure)
   hop_interval:      Port Hopping Interval(second) -> Port Hopping Interval (seconds)
   hysteria_upload_mbps:   Max Upload Speed (in Mbps) -> Upload bandwidth (units k/m/g/t)
   hysteria_download_mbps: Max Download Speed (in Mbps) -> Download bandwidth (units k/m/g/t)

Idempotent: re-running is a no-op (marker comment left in each file).
"""

import re
import sys

MARKER = "hy2UiV2rayNG"

XML_TARGET = "app/src/main/res/xml/hysteria_preferences.xml"
STR_ZH = "app/src/main/res/values-zh-rCN/strings.xml"
STR_EN = "app/src/main/res/values/strings.xml"

# v2rayNG order for the proxy category (Hy2-visible fields first,
# Hy1-only fields last). Keys as in hysteria_preferences.xml.
V2RAYNG_ORDER = [
    "serverAddress",          # 地址 (address)
    "serverPorts",            # 端口 (port) - also covers port hopping ranges
    "serverPassword",         # 密码
    "serverObfs",             # 混淆密码
    "hopInterval",            # 端口跳跃间隔 (秒)
    "serverDownloadSpeed",    # 带宽下行
    "serverUploadSpeed",      # 带宽上行
    "serverAllowInsecure",    # 跳过证书验证 (allowInsecure)
    "serverSNI",              # SNI
    "serverCertificates",     # 证书 (链) - kept, not in v2rayNG UI
    # Hy1-only fields below (hidden when protocolVersion=2)
    "serverAuthType",
    "serverProtocol",
    "serverALPN",
    "serverStreamReceiveWindow",
    "serverConnectionReceiveWindow",
    "serverDisableMtuDiscovery",
]

ZH_RENAMES = {
    "profile_name": "别名 (remarks)",
    "server_address": "地址 (address)",
    "server_port": "端口 (port)",
    "sni": "SNI",
    "allow_insecure": "跳过证书验证 (allowInsecure)",
    "hop_interval": "端口跳跃间隔 (秒)",
    "hysteria_upload_mbps": "带宽上行 (支持的单位 k/m/g/t)",
    "hysteria_download_mbps": "带宽下行 (支持的单位 k/m/g/t)",
}

EN_RENAMES = {
    "profile_name": "Remarks",
    "server_address": "Address",
    "server_port": "Port",
    "sni": "SNI",
    "allow_insecure": "Skip certificate verification (allowInsecure)",
    "hop_interval": "Port Hopping Interval (seconds)",
    "hysteria_upload_mbps": "Upload bandwidth (units k/m/g/t)",
    "hysteria_download_mbps": "Download bandwidth (units k/m/g/t)",
}


def patch_hysteria_xml(path):
    with open(path, encoding="utf-8") as f:
        src = f.read()
    if MARKER in src:
        print("hysteria_preferences.xml already patched, skip")
        return

    # Split out each preference element by its app:key="..."
    # We only reorder inside <PreferenceCategory app:title="@string/proxy_cat">.
    cat_start = src.find('<PreferenceCategory app:title="@string/proxy_cat">')
    assert cat_start != -1, "proxy_cat not found"
    cat_end = src.find("</PreferenceCategory>", cat_start)
    assert cat_end != -1, "proxy_cat end not found"
    cat_end += len("</PreferenceCategory>")

    cat = src[cat_start:cat_end]

    # Find all top-level preference elements within the category.
    # They are <EditTextPreference ... />, <SwitchPreference ... />,
    # <moe.matsuri.nb4a.ui.SimpleMenuPreference ... /> blocks.
    elem_re = re.compile(
        r'<(?:EditTextPreference|SwitchPreference|moe\.matsuri\.nb4a\.ui\.SimpleMenuPreference)\b'
        r'.*?(?:/>|</(?:EditTextPreference|SwitchPreference|moe\.matsuri\.nb4a\.ui\.SimpleMenuPreference)>)',
        re.DOTALL,
    )
    elems = elem_re.findall(cat)
    assert elems, "no preference elements found in proxy_cat"

    by_key = {}
    for e in elems:
        m = re.search(r'app:key="([^"]+)"', e)
        assert m, f"element without key: {e[:80]}"
        by_key[m.group(1)] = e

    # Verify we know every key present
    unknown = [k for k in by_key if k not in V2RAYNG_ORDER]
    assert not unknown, f"unknown keys in proxy_cat: {unknown}"
    missing = [k for k in V2RAYNG_ORDER if k not in by_key]
    assert not missing, f"expected keys missing: {missing}"

    new_cat_inner = "\n\n".join("        " + by_key[k].strip() for k in V2RAYNG_ORDER)
    new_cat = (
        '<PreferenceCategory app:title="@string/proxy_cat">\n\n'
        + new_cat_inner
        + "\n    </PreferenceCategory>"
    )
    # Insert marker comment right after <PreferenceScreen ...> line
    new_src = src[:cat_start] + new_cat + src[cat_end:]
    screen_end = new_src.find(">")
    assert screen_end != -1
    new_src = (
        new_src[: screen_end + 1]
        + f"\n<!-- {MARKER}: fields reordered to v2rayNG order -->"
        + new_src[screen_end + 1 :]
    )

    with open(path, "w", encoding="utf-8") as f:
        f.write(new_src)
    print(f"patched {path}: reordered {len(V2RAYNG_ORDER)} fields to v2rayNG order")


def patch_strings(path, renames):
    with open(path, encoding="utf-8") as f:
        src = f.read()
    if MARKER in src:
        print(f"{path} already patched, skip")
        return

    changed = 0
    for name, new_text in renames.items():
        # Match <string name="...">...</string>, possibly multiline
        pat = re.compile(
            r'(<string name="%s">)(.*?)(</string>)' % re.escape(name),
            re.DOTALL,
        )
        m = pat.search(src)
        assert m, f'string "{name}" not found in {path}'
        old_text = m.group(2)
        if old_text.strip() == new_text:
            continue
        # Preserve any inner formatting by replacing whole content
        src = pat.sub(lambda mm: mm.group(1) + new_text + mm.group(3), src, count=1)
        changed += 1
        print(f"  {name}: {old_text.strip()[:40]} -> {new_text}")

    # Add marker comment after <?xml ...?> or at top
    marker_comment = f"<!-- {MARKER}: labels aligned to v2rayNG -->\n"
    if src.startswith("<?xml"):
        nl = src.find("\n")
        src = src[: nl + 1] + marker_comment + src[nl + 1 :]
    else:
        src = marker_comment + src

    with open(path, "w", encoding="utf-8") as f:
        f.write(src)
    print(f"patched {path}: {changed} labels renamed")


def main():
    patch_hysteria_xml(XML_TARGET)
    patch_strings(STR_ZH, ZH_RENAMES)
    patch_strings(STR_EN, EN_RENAMES)
    print("hy2 UI patch done")


if __name__ == "__main__":
    main()
