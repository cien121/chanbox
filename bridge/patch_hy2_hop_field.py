#!/usr/bin/env python3
"""Hysteria2: independent hop-ports field + protocol version display tweak.

User requests (2026-10-06):
1. "一个独立端口，一个跳跃端口" / "增加不好吗"
   - The Hy2 edit page currently has a single "端口" (serverPorts) field where
     a range means hopping. The user wants TWO separate inputs:
       - "端口" (serverPorts): fixed / independent port
       - "跳跃端口" (hopPorts): hopping range like 20000-21000, empty = no hop
2. '"协议版本：2"这行改成显示"协议：hysteria2"' (correction, not deletion)
   - Title "协议版本" -> "协议", entries "1"/"2" -> "hysteria1"/"hysteria2".

Changes (run from NekoBox checkout root, AFTER patch_hy2_ech.py):

1. HysteriaBean.java
   - Add `public String hopPorts;` field (after serverPorts)
   - initializeDefaultValues: default ""
   - serialize version 8 -> 9, write hopPorts (after echConfigList)
   - deserialize: version >= 9 reads it, older defaults ""

2. Constants.kt (Key object)
   - Add `const val SERVER_HOP_PORTS = "serverHopPorts"`

3. DataStore.kt
   - Add `var serverHopPorts by profileCacheStore.string(Key.SERVER_HOP_PORTS)`

4. hysteria_preferences.xml
   - Add EditTextPreference (key serverHopPorts) right after serverPorts
   - protocolVersion preference: entries -> @array/hysteria_version_entries
     (entryValues stay @array/hysteria_version so stored values remain "1"/"2")

5. arrays.xml
   - Add `hysteria_version_entries` array: hysteria1, hysteria2

6. HysteriaSettingsActivity.kt
   - init(): DataStore.serverHopPorts = hopPorts
   - serialize(): hopPorts = DataStore.serverHopPorts

7. HysteriaFmt.kt (buildSingBoxOutboundHysteriaBean, Hy1 & Hy2 branches)
   - If hopPorts not blank: server_port = fixed port, server_ports = parsed hops
   - Else: legacy behavior (serverPorts single -> server_port, range -> server_ports)
   - parseHysteria1/parseHysteria2: mport query param -> hopPorts (was serverPorts)
   - toUri(): mport param from hopPorts (fallback serverPorts)

8. values-zh-rCN/strings.xml + values/strings.xml
   - Add `hop_ports` string ("跳跃端口" / "Hop Ports")
   - Change `protocol_version`: "协议版本" -> "协议" / "Protocol Version" -> "Protocol"

Idempotent: re-running is a no-op (marker comment in each file).
"""

import re

MARKER = "hy2HopField"

BEAN = "app/src/main/java/io/nekohasekai/sagernet/fmt/hysteria/HysteriaBean.java"
CONSTANTS = "app/src/main/java/io/nekohasekai/sagernet/Constants.kt"
DATASTORE = "app/src/main/java/io/nekohasekai/sagernet/database/DataStore.kt"
PREF_XML = "app/src/main/res/xml/hysteria_preferences.xml"
ARRAYS_XML = "app/src/main/res/values/arrays.xml"
SETTINGS_KT = "app/src/main/java/io/nekohasekai/sagernet/ui/profile/HysteriaSettingsActivity.kt"
FMT_KT = "app/src/main/java/io/nekohasekai/sagernet/fmt/hysteria/HysteriaFmt.kt"
STR_ZH = "app/src/main/res/values-zh-rCN/strings.xml"
STR_EN = "app/src/main/res/values/strings.xml"


def read(p):
    with open(p, "r", encoding="utf-8") as f:
        return f.read()


def write(p, c):
    with open(p, "w", encoding="utf-8") as f:
        f.write(c)


def patched(content):
    return MARKER in content


def patch_bean():
    c = read(BEAN)
    if patched(c):
        print("  [skip] HysteriaBean.java already patched")
        return
    # 1. Field declaration after serverPorts
    old = "    public String serverPorts;\n"
    new = ("    public String serverPorts;\n"
           "    public String hopPorts; // hy2HopField: independent hop-ports input\n")
    assert c.count(old) == 1, "bean field anchor not found/ambiguous"
    c = c.replace(old, new, 1)
    # 2. Default value after serverPorts default
    old = '        if (serverPorts == null) serverPorts = "443";\n'
    new = ('        if (serverPorts == null) serverPorts = "443";\n'
           '        if (hopPorts == null) hopPorts = ""; // hy2HopField\n')
    assert c.count(old) == 1, "bean default anchor not found/ambiguous"
    c = c.replace(old, new, 1)
    # 3. Serialize version 8 -> 9 (ECH patch already bumped 7 -> 8)
    old = "        output.writeInt(8); // hy2EchSupport\n"
    new = "        output.writeInt(9); // hy2HopField\n"
    assert c.count(old) == 1, "bean serialize version anchor not found/ambiguous"
    c = c.replace(old, new, 1)
    # 4. Serialize: write hopPorts after echConfigList
    old = "        output.writeString(echConfigList); // hy2EchSupport\n"
    new = ("        output.writeString(echConfigList); // hy2EchSupport\n"
           "        output.writeString(hopPorts); // hy2HopField\n")
    assert c.count(old) == 1, "bean serialize field anchor not found/ambiguous"
    c = c.replace(old, new, 1)
    # 5. Deserialize: read hopPorts for version >= 9 (after ECH v8 block)
    old = """        if (version >= 8) { // hy2EchSupport
            echConfigList = input.readString();
        } else {
            echConfigList = "";
        }
    }"""
    new = """        if (version >= 8) { // hy2EchSupport
            echConfigList = input.readString();
        } else {
            echConfigList = "";
        }
        if (version >= 9) { // hy2HopField
            hopPorts = input.readString();
        } else {
            hopPorts = "";
        }
    }"""
    assert c.count(old) == 1, "bean deserialize anchor not found/ambiguous"
    c = c.replace(old, new, 1)
    write(BEAN, c)
    print("  [ok] HysteriaBean.java: hopPorts field added (v9)")


def patch_constants():
    c = read(CONSTANTS)
    if patched(c):
        print("  [skip] Constants.kt already patched")
        return
    old = '    const val SERVER_ECH_CONFIG_LIST = "serverECHConfigList" // hy2EchSupport\n'
    new = (old +
           '    const val SERVER_HOP_PORTS = "serverHopPorts" // hy2HopField\n')
    assert c.count(old) == 1, "constants anchor not found/ambiguous"
    c = c.replace(old, new, 1)
    write(CONSTANTS, c)
    print("  [ok] Constants.kt: SERVER_HOP_PORTS key added")


def patch_datastore():
    c = read(DATASTORE)
    if patched(c):
        print("  [skip] DataStore.kt already patched")
        return
    old = "    var serverECHConfigList by profileCacheStore.string(Key.SERVER_ECH_CONFIG_LIST) // hy2EchSupport\n"
    new = (old +
           "    var serverHopPorts by profileCacheStore.string(Key.SERVER_HOP_PORTS) // hy2HopField\n")
    assert c.count(old) == 1, "datastore anchor not found/ambiguous"
    c = c.replace(old, new, 1)
    write(DATASTORE, c)
    print("  [ok] DataStore.kt: serverHopPorts field added")


def patch_pref_xml():
    c = read(PREF_XML)
    if patched(c):
        print("  [skip] hysteria_preferences.xml already patched")
        return
    # 1. Add hopPorts preference right after serverPorts (self-closing tag).
    pattern = re.compile(
        r'(<EditTextPreference\b[^>]*app:key="serverPorts"[^>]*/>)', re.DOTALL)
    m = pattern.search(c)
    assert m, "pref xml serverPorts anchor not found"
    addition = (m.group(1) +
                '\n        <!-- hy2HopField: independent hop-ports input -->\n'
                '        <EditTextPreference\n'
                '            app:icon="@drawable/ic_maps_directions_boat"\n'
                '            app:key="serverHopPorts"\n'
                '            app:title="@string/hop_ports"\n'
                '            app:useSimpleSummaryProvider="true" />')
    c = c[:m.start(1)] + addition + c[m.end(1):]
    # 2. protocolVersion: display entries as hysteria1/hysteria2 (values stay 1/2).
    # (marker comment goes on its own line before the element; XML comments
    #  cannot appear inside a tag.)
    old = '    <moe.matsuri.nb4a.ui.SimpleMenuPreference\n        app:defaultValue="2"\n        app:entries="@array/hysteria_version"'
    new = ('    <!-- hy2HopField: version entries show hysteria1/hysteria2 -->\n'
           '    <moe.matsuri.nb4a.ui.SimpleMenuPreference\n'
           '        app:defaultValue="2"\n'
           '        app:entries="@array/hysteria_version_entries"')
    assert c.count(old) == 1, "pref xml protocolVersion entries anchor not found/ambiguous"
    c = c.replace(old, new, 1)
    write(PREF_XML, c)
    print("  [ok] hysteria_preferences.xml: hopPorts preference added, version entries relabeled")


def patch_arrays_xml():
    c = read(ARRAYS_XML)
    if patched(c):
        print("  [skip] arrays.xml already patched")
        return
    old = """    <string-array name="hysteria_version">
        <item>1</item>
        <item>2</item>
    </string-array>"""
    new = (old + "\n\n"
           "    <!-- hy2HopField: display labels for protocol version -->\n"
           '    <string-array name="hysteria_version_entries">\n'
           "        <item>hysteria1</item>\n"
           "        <item>hysteria2</item>\n"
           "    </string-array>")
    assert c.count(old) == 1, "arrays.xml hysteria_version anchor not found/ambiguous"
    c = c.replace(old, new, 1)
    write(ARRAYS_XML, c)
    print("  [ok] arrays.xml: hysteria_version_entries added")


def patch_settings_kt():
    c = read(SETTINGS_KT)
    if patched(c):
        print("  [skip] HysteriaSettingsActivity.kt already patched")
        return
    old = "        DataStore.serverPorts = serverPorts\n"
    new = ("        DataStore.serverPorts = serverPorts\n"
           "        DataStore.serverHopPorts = hopPorts // hy2HopField\n")
    assert c.count(old) == 1, "settings init anchor not found/ambiguous"
    c = c.replace(old, new, 1)
    old = "        serverPorts = DataStore.serverPorts\n"
    new = ("        serverPorts = DataStore.serverPorts\n"
           "        hopPorts = DataStore.serverHopPorts // hy2HopField\n")
    assert c.count(old) == 1, "settings serialize anchor not found/ambiguous"
    c = c.replace(old, new, 1)
    write(SETTINGS_KT, c)
    print("  [ok] HysteriaSettingsActivity.kt: hopPorts binding added")


def patch_fmt_kt():
    c = read(FMT_KT)
    if patched(c):
        print("  [skip] HysteriaFmt.kt already patched")
        return
    # 1+2. parseHysteria1 & parseHysteria2: mport -> hopPorts (was serverPorts).
    # The block text is identical in both parsers; replace both occurrences.
    old = """        link.queryParameter("mport")?.also {
            serverPorts = it
        }"""
    new_mport = """        link.queryParameter("mport")?.also {
            hopPorts = it // hy2HopField: hop range goes to the dedicated field
        }"""
    assert c.count(old) == 2, f"fmt mport anchor: expected 2 occurrences, found {c.count(old)}"
    c = c.replace(old, new_mport)
    # 3. toUri(): mport param from hopPorts (fallback serverPorts for old profiles)
    old = """    if (isMultiPort(displayAddress())) {
        builder.addQueryParameter("mport", serverPorts)
    }"""
    new = """    // hy2HopField: export hop range via mport
    val mportSrc = hopPorts.ifBlank { serverPorts }
    if (mportSrc.contains("-") || mportSrc.contains(",")) {
        builder.addQueryParameter("mport", mportSrc)
    }"""
    assert c.count(old) == 1, "fmt toUri mport anchor not found/ambiguous"
    c = c.replace(old, new, 1)
    # 4. Hy1 branch: use hopPorts when set
    old = """        1 -> SingBoxOptions.Outbound_HysteriaOptions().apply {
            type = "hysteria"
            server = bean.serverAddress
            val port = bean.serverPorts.toIntOrNull()
            if (port != null) {
                server_port = port
            } else {
                server_ports = hopPortsToSingboxList(bean.serverPorts)
            }"""
    new = """        1 -> SingBoxOptions.Outbound_HysteriaOptions().apply {
            type = "hysteria"
            server = bean.serverAddress
            // hy2HopField: independent hop-ports field; legacy serverPorts range still honored
            if (bean.hopPorts.isNotBlank()) {
                server_port = bean.serverPorts.toIntOrNull() ?: 443
                val hops = hopPortsToSingboxList(bean.hopPorts)
                if (hops.isNotEmpty()) server_ports = hops
            } else {
                val port = bean.serverPorts.toIntOrNull()
                if (port != null) {
                    server_port = port
                } else {
                    server_ports = hopPortsToSingboxList(bean.serverPorts)
                }
            }"""
    assert c.count(old) == 1, "fmt Hy1 ports anchor not found/ambiguous"
    c = c.replace(old, new, 1)
    # 5. Hy2 branch: use hopPorts when set
    old = """        2 -> SingBoxOptions.Outbound_Hysteria2Options().apply {
            type = "hysteria2"
            server = bean.serverAddress
            val port = bean.serverPorts.toIntOrNull()
            if (port != null) {
                server_port = port
            } else {
                server_ports = hopPortsToSingboxList(bean.serverPorts)
            }"""
    new = """        2 -> SingBoxOptions.Outbound_Hysteria2Options().apply {
            type = "hysteria2"
            server = bean.serverAddress
            // hy2HopField: independent hop-ports field; legacy serverPorts range still honored
            if (bean.hopPorts.isNotBlank()) {
                server_port = bean.serverPorts.toIntOrNull() ?: 443
                val hops = hopPortsToSingboxList(bean.hopPorts)
                if (hops.isNotEmpty()) server_ports = hops
            } else {
                val port = bean.serverPorts.toIntOrNull()
                if (port != null) {
                    server_port = port
                } else {
                    server_ports = hopPortsToSingboxList(bean.serverPorts)
                }
            }"""
    assert c.count(old) == 1, "fmt Hy2 ports anchor not found/ambiguous"
    c = c.replace(old, new, 1)
    write(FMT_KT, c)
    print("  [ok] HysteriaFmt.kt: hopPorts wired into Hy1/Hy2 outbounds, mport import/export")


def patch_strings(path, lang, version_label):
    c = read(path)
    if MARKER in c:
        print(f"  [skip] {path} already patched")
        return
    # 1. Add hop_ports string before </resources>
    old = "</resources>"
    new = ('    <!-- hy2HopField -->\n'
           f'    <string name="hop_ports">{"跳跃端口" if lang == "zh" else "Hop Ports"}</string>\n'
           '</resources>')
    assert c.count(old) >= 1, f"strings anchor not found in {path}"
    c = c.replace(old, new, 1)
    # 2. protocol_version label: "协议版本" -> "协议" (user: show "协议：hysteria2")
    if lang == "zh":
        old2 = '<string name="protocol_version">协议版本</string>'
        new2 = '<string name="protocol_version">协议</string> <!-- hy2HopField -->'
    else:
        old2 = '<string name="protocol_version">Protocol Version</string>'
        new2 = '<string name="protocol_version">Protocol</string> <!-- hy2HopField -->'
    assert c.count(old2) == 1, f"protocol_version anchor not found in {path}"
    c = c.replace(old2, new2, 1)
    write(path, c)
    print(f"  [ok] {path}: hop_ports added, protocol_version relabeled ({lang})")


def main():
    print(">>> patch_hy2_hop_field: independent Hy2 hop-ports field + version label")
    patch_bean()
    patch_constants()
    patch_datastore()
    patch_pref_xml()
    patch_arrays_xml()
    patch_settings_kt()
    patch_fmt_kt()
    patch_strings(STR_ZH, "zh", "协议")
    patch_strings(STR_EN, "en", "Protocol")
    print(">>> done")


if __name__ == "__main__":
    main()
