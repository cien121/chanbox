#!/usr/bin/env python3
"""Add ECH (Encrypted Client Hello) support to Hysteria2.

Background:
- Hysteria v2.12.3 added `hysteria ech` subcommand to generate ECH keys
  and client configuration.
- sing-box-lx v1.14.2-lx.11 supports ECH on Hysteria2 outbound via
  `tls.ech` (OutboundECHOptions): enabled + config (PEM "ECH CONFIGS").
  Chain verified: Hysteria2OutboundOptions -> OutboundTLSOptionsContainer
  -> OutboundTLSOptions.ech -> tls.NewClient -> parseECHClientConfig.
- NekoBox's HysteriaBean has no echConfigList field; this patch adds it,
  adds UI input, and wires it into the sing-box outbound config.

ECH config format: sing-box expects PEM ("-----BEGIN ECH CONFIGS-----").
v2rayNG shows raw base64; the patch wraps raw base64 in PEM automatically,
so users can paste from v2rayNG directly.

Changes (run from NekoBox checkout root):

1. HysteriaBean.java
   - Add `public String echConfigList;` field (HY1 & 2 section)
   - initializeDefaultValues: default ""
   - serialize version 7 -> 8, write echConfigList
   - deserialize: version >= 8 reads it, older defaults ""

2. Constants.kt (Key object)
   - Add `const val SERVER_ECH_CONFIG_LIST = "serverECHConfigList"`

3. DataStore.kt
   - Add `var serverECHConfigList by profileCacheStore.string(Key.SERVER_ECH_CONFIG_LIST)`

4. hysteria_preferences.xml
   - Add EditTextPreference (key serverECHConfigList) after serverSNI

5. HysteriaSettingsActivity.kt
   - init(): DataStore.serverECHConfigList = echConfigList
   - serialize(): echConfigList = DataStore.serverECHConfigList

6. HysteriaFmt.kt (buildSingBoxOutboundHysteriaBean, Hy2 branch)
   - In TLS options: if echConfigList not blank, set
     ech = OutboundECHOptions(enabled=true, config=[pemWrapped])

7. values-zh-rCN/strings.xml + values/strings.xml
   - Add `ech_config_list` string ("echConfigList")

Idempotent: re-running is a no-op (marker comment in each file).
"""

import re
import sys

MARKER = "hy2EchSupport"

BEAN = "app/src/main/java/io/nekohasekai/sagernet/fmt/hysteria/HysteriaBean.java"
CONSTANTS = "app/src/main/java/io/nekohasekai/sagernet/Constants.kt"
DATASTORE = "app/src/main/java/io/nekohasekai/sagernet/database/DataStore.kt"
PREF_XML = "app/src/main/res/xml/hysteria_preferences.xml"
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
    # 1. Add field declaration (in HY1 & 2 section, after allowInsecure)
    old = "    public Boolean allowInsecure;\n"
    new = "    public Boolean allowInsecure;\n    public String echConfigList; // hy2EchSupport\n"
    assert old in c, "bean field anchor not found"
    c = c.replace(old, new, 1)
    # 2. Default value
    old = '        if (allowInsecure == null) allowInsecure = false;\n'
    new = ('        if (allowInsecure == null) allowInsecure = false;\n'
           '        if (echConfigList == null) echConfigList = ""; // hy2EchSupport\n')
    assert old in c, "bean default anchor not found"
    c = c.replace(old, new, 1)
    # 3. Serialize: bump version 7 -> 8
    old = "        output.writeInt(7);\n"
    new = "        output.writeInt(8); // hy2EchSupport\n"
    assert old in c, "bean serialize version anchor not found"
    c = c.replace(old, new, 1)
    # 4. Serialize: write field (after serverPorts)
    old = "        output.writeString(serverPorts);\n    }\n"
    new = ("        output.writeString(serverPorts);\n"
           "        output.writeString(echConfigList); // hy2EchSupport\n    }\n")
    assert old in c, "bean serialize field anchor not found"
    c = c.replace(old, new, 1)
    # 5. Deserialize: read field for version >= 8
    old = """        if (version >= 6) {
            serverPorts = input.readString();
        } else {"""
    new = """        if (version >= 6) {
            serverPorts = input.readString();
        } else {"""
    assert old in c, "bean deserialize anchor not found"
    # Insert version>=8 read right after the version>=6 block closes.
    # Find the closing of the else block for version>=6.
    old2 = """            } else {
                serverPorts = serverPort.toString();
            }
        }
    }"""
    # Simpler: add after deserialize's serverPorts handling, before displayAddress.
    # Use a unique anchor: the end of deserialize method.
    anchor = """                serverPorts = serverPort.toString();
            }
        }
    }

    @Override
    public String displayAddress() {"""
    replacement = """                serverPorts = serverPort.toString();
            }
        }
        if (version >= 8) { // hy2EchSupport
            echConfigList = input.readString();
        } else {
            echConfigList = "";
        }
    }

    @Override
    public String displayAddress() {"""
    assert anchor in c, "bean deserialize end anchor not found"
    c = c.replace(anchor, replacement, 1)
    write(BEAN, c)
    print("  [ok] HysteriaBean.java: echConfigList field added (v8)")


def patch_constants():
    c = read(CONSTANTS)
    if patched(c):
        print("  [skip] Constants.kt already patched")
        return
    old = '    const val SERVER_SNI = "serverSNI"\n'
    new = ('    const val SERVER_SNI = "serverSNI"\n'
           '    const val SERVER_ECH_CONFIG_LIST = "serverECHConfigList" // hy2EchSupport\n')
    assert old in c, "constants anchor not found"
    c = c.replace(old, new, 1)
    write(CONSTANTS, c)
    print("  [ok] Constants.kt: SERVER_ECH_CONFIG_LIST key added")


def patch_datastore():
    c = read(DATASTORE)
    if patched(c):
        print("  [skip] DataStore.kt already patched")
        return
    old = "    var serverSNI by profileCacheStore.string(Key.SERVER_SNI)\n"
    new = ("    var serverSNI by profileCacheStore.string(Key.SERVER_SNI)\n"
           "    var serverECHConfigList by profileCacheStore.string(Key.SERVER_ECH_CONFIG_LIST) // hy2EchSupport\n")
    assert old in c, "datastore anchor not found"
    c = c.replace(old, new, 1)
    write(DATASTORE, c)
    print("  [ok] DataStore.kt: serverECHConfigList field added")


def patch_pref_xml():
    c = read(PREF_XML)
    if patched(c):
        print("  [skip] hysteria_preferences.xml already patched")
        return
    # Insert after serverSNI preference (which may have been reordered by hy2ui patch,
    # so search for the serverSNI block generically).
    pattern = re.compile(
        r'(<EditTextPreference\b[^>]*app:key="serverSNI"[^>]*/>)', re.DOTALL)
    m = pattern.search(c)
    assert m, "pref xml serverSNI anchor not found"
    addition = (m.group(1) +
                '\n        <!-- hy2EchSupport -->\n'
                '        <EditTextPreference\n'
                '            app:icon="@drawable/ic_notification_enhanced_encryption"\n'
                '            app:key="serverECHConfigList"\n'
                '            app:title="@string/ech_config_list"\n'
                '            app:useSimpleSummaryProvider="true" />')
    c = c[:m.start(1)] + addition + c[m.end(1):]
    write(PREF_XML, c)
    print("  [ok] hysteria_preferences.xml: echConfigList preference added")


def patch_settings_kt():
    c = read(SETTINGS_KT)
    if patched(c):
        print("  [skip] HysteriaSettingsActivity.kt already patched")
        return
    old = "        DataStore.serverSNI = sni\n"
    new = ("        DataStore.serverSNI = sni\n"
           "        DataStore.serverECHConfigList = echConfigList // hy2EchSupport\n")
    assert old in c, "settings init anchor not found"
    c = c.replace(old, new, 1)
    old = "        sni = DataStore.serverSNI\n"
    new = ("        sni = DataStore.serverSNI\n"
           "        echConfigList = DataStore.serverECHConfigList // hy2EchSupport\n")
    assert old in c, "settings serialize anchor not found"
    c = c.replace(old, new, 1)
    write(SETTINGS_KT, c)
    print("  [ok] HysteriaSettingsActivity.kt: binding added")


def patch_fmt_kt():
    c = read(FMT_KT)
    if patched(c):
        print("  [skip] HysteriaFmt.kt already patched")
        return
    # In Hy2 branch TLS options, add ECH after insecure line.
    # The Hy2 TLS block:
    #   tls = SingBoxOptions.OutboundTLSOptions().apply {
    #       ...
    #       insecure = bean.allowInsecure || DataStore.globalAllowInsecure
    #       enabled = true
    #   }
    # We add ECH handling before `enabled = true` in the Hy2 branch.
    # Use the Hy2-specific context: the Hy2 branch has `alpn = listOf("h3")`.
    old = """            tls = SingBoxOptions.OutboundTLSOptions().apply {
                if (bean.sni.isNotBlank()) {
                    server_name = bean.sni
                }
                alpn = listOf("h3")
                if (bean.caText.isNotBlank()) {
                    certificate = bean.caText
                }
                insecure = bean.allowInsecure || DataStore.globalAllowInsecure
                enabled = true
            }"""
    new = """            tls = SingBoxOptions.OutboundTLSOptions().apply {
                if (bean.sni.isNotBlank()) {
                    server_name = bean.sni
                }
                alpn = listOf("h3")
                if (bean.caText.isNotBlank()) {
                    certificate = bean.caText
                }
                insecure = bean.allowInsecure || DataStore.globalAllowInsecure
                enabled = true
                // hy2EchSupport: ECH (Encrypted Client Hello)
                if (bean.echConfigList.isNotBlank()) {
                    ech = SingBoxOptions.OutboundECHOptions().apply {
                        enabled = true
                        config = listOf(wrapEchConfigAsPem(bean.echConfigList))
                    }
                }
            }"""
    assert old in c, "fmt Hy2 TLS anchor not found"
    c = c.replace(old, new, 1)
    # Add helper function wrapEchConfigAsPem before buildSingBoxOutboundHysteriaBean.
    old = "fun buildSingBoxOutboundHysteriaBean(bean: HysteriaBean): SingBoxOptions.SingBoxOption {"
    new = """// hy2EchSupport: sing-box expects ECH configs as PEM ("ECH CONFIGS" block).
// v2rayNG shows raw base64; wrap it so users can paste from v2rayNG directly.
fun wrapEchConfigAsPem(raw: String): String {
    val trimmed = raw.trim()
    if (trimmed.contains("BEGIN ECH CONFIGS")) return trimmed
    return "-----BEGIN ECH CONFIGS-----\\n" + trimmed + "\\n-----END ECH CONFIGS-----"
}

fun buildSingBoxOutboundHysteriaBean(bean: HysteriaBean): SingBoxOptions.SingBoxOption {"""
    assert old in c, "fmt helper anchor not found"
    c = c.replace(old, new, 1)
    write(FMT_KT, c)
    print("  [ok] HysteriaFmt.kt: ECH wired into Hy2 TLS options")


def patch_strings(path, lang):
    c = read(path)
    if patched(c):
        print(f"  [skip] {path} already patched")
        return
    # Insert before closing </resources>
    old = "</resources>"
    new = ('    <!-- hy2EchSupport -->\n'
           '    <string name="ech_config_list">echConfigList</string>\n'
           '</resources>')
    assert old in c, f"strings anchor not found in {path}"
    c = c.replace(old, new, 1)
    write(path, c)
    print(f"  [ok] {path}: ech_config_list string added ({lang})")


def main():
    print(">>> patch_hy2_ech: Hysteria2 ECH support")
    patch_bean()
    patch_constants()
    patch_datastore()
    patch_pref_xml()
    patch_settings_kt()
    patch_fmt_kt()
    patch_strings(STR_ZH, "zh")
    patch_strings(STR_EN, "en")
    print(">>> done")


if __name__ == "__main__":
    main()
