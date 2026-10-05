#!/usr/bin/env python3
"""Patch NekoBox: add XHTTP quick-add entry + xhttp transport option.

User request: the "add node" protocol list has no XHTTP entry, and the
VLESS transport dropdown has no xhttp option either.

XHTTP is already supported as a VLESS transport (type=xhttp) by the
Kotlin xhttp wiring (V2RayFmt.kt / StandardV2RayBean.xhttpMode). This
patch only touches the UI so users can actually select it:

1. app/src/main/res/menu/add_profile_menu.xml
   Add "XHTTP" item right after the VLESS item in the manual-add submenu.

2. app/src/main/java/io/nekohasekai/sagernet/ui/ConfigurationFragment.kt
   Add the R.id.action_new_xhttp handler: open VMessSettingsActivity
   with vless=true + xhttp=true extras.

3. app/src/main/java/io/nekohasekai/sagernet/ui/profile/VMessSettingsActivity.kt
   In createEntity(): when the xhttp extra is present, preset
   bean.type = "xhttp".

4. app/src/main/res/values/arrays.xml
   - Add <item>xhttp</item> to the networks_value array (transport dropdown).
   - Add xhttp_mode_value array (auto/packet-up/stream-up/stream-one).

5. app/src/main/res/xml/standard_v2ray_preferences.xml
   Add an XHTTP-mode SimpleMenuPreference (key=xhttpMode) after the
   path preference.

6. app/src/main/java/io/nekohasekai/sagernet/ui/profile/StandardV2RaySettingsActivity.kt
   - Bind the new xhttpMode preference to the bean field.
   - updateView(): add the "xhttp" branch (show host/path) and toggle
     the mode selector visibility (only for xhttp).

Idempotent: re-running is a no-op (marker comment left in each file).
"""
import sys

MARKER = "xhttpMenu"

MENU_XML = "app/src/main/res/menu/add_profile_menu.xml"
FRAGMENT_KT = "app/src/main/java/io/nekohasekai/sagernet/ui/ConfigurationFragment.kt"
VMESS_ACTIVITY = "app/src/main/java/io/nekohasekai/sagernet/ui/profile/VMessSettingsActivity.kt"
ARRAYS_XML = "app/src/main/res/values/arrays.xml"
PREFS_XML = "app/src/main/res/xml/standard_v2ray_preferences.xml"
STD_ACTIVITY = "app/src/main/java/io/nekohasekai/sagernet/ui/profile/StandardV2RaySettingsActivity.kt"


def patch_menu_xml(path):
    with open(path, encoding="utf-8") as f:
        src = f.read()
    if MARKER in src:
        print("add_profile_menu.xml already patched, skip")
        return
    old = (
        '                        android:id="@+id/action_new_vless"\n'
        '                        android:title="VLESS" />\n'
        '                    <item\n'
        '                        android:id="@+id/action_new_trojan"'
    )
    assert src.count(old) == 1, "VLESS menu item anchor not found exactly once"
    new = (
        '                        android:id="@+id/action_new_vless"\n'
        '                        android:title="VLESS" />\n'
        f'                    <!-- {MARKER}: XHTTP quick-add entry -->\n'
        '                    <item\n'
        '                        android:id="@+id/action_new_xhttp"\n'
        '                        android:title="XHTTP" />\n'
        '                    <item\n'
        '                        android:id="@+id/action_new_trojan"'
    )
    src = src.replace(old, new)
    with open(path, "w", encoding="utf-8") as f:
        f.write(src)
    print("add_profile_menu.xml patched OK")


def patch_fragment_kt(path):
    with open(path, encoding="utf-8") as f:
        src = f.read()
    if MARKER in src:
        print("ConfigurationFragment.kt already patched, skip")
        return
    old = (
        '            R.id.action_new_vless -> {\n'
        '                startActivity(Intent(requireActivity(), VMessSettingsActivity::class.java).apply {\n'
        '                    putExtra("vless", true)\n'
        '                })\n'
        '            }\n'
    )
    assert src.count(old) == 1, "action_new_vless handler not found exactly once"
    new = old + (
        '\n'
        f'            // {MARKER}: quick-add VLESS node with xhttp transport preselected\n'
        '            R.id.action_new_xhttp -> {\n'
        '                startActivity(Intent(requireActivity(), VMessSettingsActivity::class.java).apply {\n'
        '                    putExtra("vless", true)\n'
        '                    putExtra("xhttp", true)\n'
        '                })\n'
        '            }\n'
    )
    src = src.replace(old, new)
    with open(path, "w", encoding="utf-8") as f:
        f.write(src)
    print("ConfigurationFragment.kt patched OK")


def patch_vmess_activity(path):
    with open(path, encoding="utf-8") as f:
        src = f.read()
    if MARKER in src:
        print("VMessSettingsActivity.kt already patched, skip")
        return
    old = (
        '    override fun createEntity() = VMessBean().apply {\n'
        '        if (intent?.getBooleanExtra("vless", false) == true) {\n'
        '            alterId = -1\n'
        '        }\n'
        '    }\n'
    )
    assert src.count(old) == 1, "createEntity not found exactly once"
    new = (
        '    override fun createEntity() = VMessBean().apply {\n'
        '        if (intent?.getBooleanExtra("vless", false) == true) {\n'
        '            alterId = -1\n'
        '        }\n'
        f'        // {MARKER}: preselect xhttp transport for the XHTTP quick-add entry\n'
        '        if (intent?.getBooleanExtra("xhttp", false) == true) {\n'
        '            type = "xhttp"\n'
        '        }\n'
        '    }\n'
    )
    src = src.replace(old, new)
    with open(path, "w", encoding="utf-8") as f:
        f.write(src)
    print("VMessSettingsActivity.kt patched OK")


def patch_arrays_xml(path):
    with open(path, encoding="utf-8") as f:
        src = f.read()
    if MARKER in src:
        print("arrays.xml already patched, skip")
        return
    old = (
        '    <string-array name="networks_value">\n'
        '        <item>tcp</item>\n'
        '        <item>ws</item>\n'
        '        <item>http</item>\n'
        '        <item>quic</item>\n'
        '        <item>grpc</item>\n'
        '        <item>httpupgrade</item>\n'
        '    </string-array>\n'
    )
    assert src.count(old) == 1, "networks_value array not found exactly once"
    new = (
        '    <string-array name="networks_value">\n'
        '        <item>tcp</item>\n'
        '        <item>ws</item>\n'
        '        <item>http</item>\n'
        '        <item>quic</item>\n'
        '        <item>grpc</item>\n'
        '        <item>httpupgrade</item>\n'
        '        <item>xhttp</item>\n'
        '    </string-array>\n'
        f'    <!-- {MARKER}: XHTTP transport mode options -->\n'
        '    <string-array name="xhttp_mode_value">\n'
        '        <item>auto</item>\n'
        '        <item>packet-up</item>\n'
        '        <item>stream-up</item>\n'
        '        <item>stream-one</item>\n'
        '    </string-array>\n'
    )
    src = src.replace(old, new)
    with open(path, "w", encoding="utf-8") as f:
        f.write(src)
    print("arrays.xml patched OK")


def patch_prefs_xml(path):
    with open(path, encoding="utf-8") as f:
        src = f.read()
    if MARKER in src:
        print("standard_v2ray_preferences.xml already patched, skip")
        return
    old = (
        '        <EditTextPreference\n'
        '            app:icon="@drawable/ic_baseline_format_align_left_24"\n'
        '            app:key="path"\n'
        '            app:title="@string/http_path"\n'
        '            app:useSimpleSummaryProvider="true" />\n'
    )
    assert src.count(old) == 1, "path preference anchor not found exactly once"
    new = old + (
        f'        <!-- {MARKER}: XHTTP transport mode selector -->\n'
        '        <moe.matsuri.nb4a.ui.SimpleMenuPreference\n'
        '            app:entries="@array/xhttp_mode_value"\n'
        '            app:entryValues="@array/xhttp_mode_value"\n'
        '            app:icon="@drawable/ic_baseline_compare_arrows_24"\n'
        '            app:key="xhttpMode"\n'
        '            app:title="XHTTP 模式"\n'
        '            app:useSimpleSummaryProvider="true" />\n'
    )
    src = src.replace(old, new)
    with open(path, "w", encoding="utf-8") as f:
        f.write(src)
    print("standard_v2ray_preferences.xml patched OK")


def patch_std_activity(path):
    with open(path, encoding="utf-8") as f:
        src = f.read()
    if MARKER in src:
        print("StandardV2RaySettingsActivity.kt already patched, skip")
        return

    # 1. bind the xhttpMode preference to the bean field
    old_bind = '    private val type = pbm.add(PreferenceBinding(Type.Text, "type"))\n'
    assert src.count(old_bind) == 1, "type binding not found exactly once"
    new_bind = old_bind + (
        f'    // {MARKER}: XHTTP transport mode\n'
        '    private val xhttpMode = pbm.add(PreferenceBinding(Type.Text, "xhttpMode"))\n'
    )
    src = src.replace(old_bind, new_bind)

    # 2. updateView(): toggle mode selector + add xhttp branch
    old_view_head = (
        '    private fun updateView(network: String) {\n'
        '        host.preference.isVisible = false\n'
        '        path.preference.isVisible = false\n'
        '        wsCategory.isVisible = false\n'
    )
    assert src.count(old_view_head) == 1, "updateView head not found exactly once"
    new_view_head = (
        '    private fun updateView(network: String) {\n'
        '        host.preference.isVisible = false\n'
        '        path.preference.isVisible = false\n'
        '        wsCategory.isVisible = false\n'
        f'        // {MARKER}: show XHTTP mode selector only for xhttp transport\n'
        '        xhttpMode.preference.isVisible = network == "xhttp"\n'
    )
    src = src.replace(old_view_head, new_view_head)

    old_branch = (
        '            "httpupgrade" -> {\n'
        '                host.preference.setTitle(R.string.http_upgrade_host)\n'
        '                path.preference.setTitle(R.string.http_upgrade_path)\n'
        '                host.preference.isVisible = true\n'
        '                path.preference.isVisible = true\n'
        '            }\n'
        '        }\n'
    )
    assert src.count(old_branch) == 1, "httpupgrade branch not found exactly once"
    new_branch = (
        '            "httpupgrade" -> {\n'
        '                host.preference.setTitle(R.string.http_upgrade_host)\n'
        '                path.preference.setTitle(R.string.http_upgrade_path)\n'
        '                host.preference.isVisible = true\n'
        '                path.preference.isVisible = true\n'
        '            }\n'
        '\n'
        f'            // {MARKER}\n'
        '            "xhttp" -> {\n'
        '                host.preference.setTitle(R.string.http_host)\n'
        '                path.preference.setTitle(R.string.http_path)\n'
        '                host.preference.isVisible = true\n'
        '                path.preference.isVisible = true\n'
        '            }\n'
        '        }\n'
    )
    src = src.replace(old_branch, new_branch)

    with open(path, "w", encoding="utf-8") as f:
        f.write(src)
    print("StandardV2RaySettingsActivity.kt patched OK")


def main():
    patch_menu_xml(MENU_XML)
    patch_fragment_kt(FRAGMENT_KT)
    patch_vmess_activity(VMESS_ACTIVITY)
    patch_arrays_xml(ARRAYS_XML)
    patch_prefs_xml(PREFS_XML)
    patch_std_activity(STD_ACTIVITY)
    print("patch_xhttp_menu.py: all done")


if __name__ == "__main__":
    sys.exit(main())
