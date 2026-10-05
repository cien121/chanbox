#!/usr/bin/env python3
"""Patch NekoBox main screen menu to match v2rayNG.

User request: the three-dot menu on the main screen should have the same
items, names and order as v2rayNG:

v2rayNG order:
  1. 服务重启 (restart service)
  2. 删除配置 (delete all configs)
  3. 删除重复配置 (delete duplicate configs)
  4. 删除无效配置 (delete invalid/unavailable configs)
  5. 将配置导出至剪贴板 (export all configs to clipboard)
  6. 定位所选配置 (scroll to selected config)
  7. 按测试结果排序 (sort by test results)
  8. 测试 TCP 延迟（TCPing) (TCP ping test)
  9. 测试真连接延迟 (real connection latency / URL test)
  10. 更新订阅 (update subscription)

Four files are touched (under the NekoBox checkout, run from its root):

1. app/src/main/res/menu/add_profile_menu.xml
   Rewrite the action_misc submenu: reorder to v2rayNG order, drop
   action_clear_traffic_statistics and action_connection_test_clear_results
   (not in v2rayNG), add action_restart_service / action_delete_all /
   action_export_all_clipboard / action_locate_selected.

2. app/src/main/res/values-zh-rCN/strings.xml
   Rename: 删除重复的服务器->删除重复配置, 清理不可用配置->删除无效配置,
   排序->按测试结果排序, 更新当前组订阅->更新订阅.
   Add: restart_service=服务重启, delete_all_configs=删除配置,
   export_all_clipboard=将配置导出至剪贴板, locate_selected=定位所选配置.

3. app/src/main/res/values/strings.xml (English)
   Rename TCPing->Test TCP latency (TCPing), URL Test->Test real connection
   latency, plus matching renames and new strings.

4. app/src/main/java/io/nekohasekai/sagernet/ui/ConfigurationFragment.kt
   - Remove when branches for action_clear_traffic_statistics and
     action_connection_test_clear_results (menu items removed).
   - Add when branches for the four new menu items. All used APIs
     (SagerNet.reloadService/startService, GroupManager.clearGroup,
     SagerNet.trySetPrimaryClip, getCurrentGroupFragment().scrollTo)
     already exist in this file's scope/imports.

Idempotent: re-running is a no-op (marker comment left in each file).
"""
import sys

MARKER = "mainMenuV2rayNG"

XML_TARGET = "app/src/main/res/menu/add_profile_menu.xml"
STR_ZH = "app/src/main/res/values-zh-rCN/strings.xml"
STR_EN = "app/src/main/res/values/strings.xml"
KT_TARGET = "app/src/main/java/io/nekohasekai/sagernet/ui/ConfigurationFragment.kt"


def patch_xml(path):
    with open(path, encoding="utf-8") as f:
        src = f.read()
    if MARKER in src:
        print("add_profile_menu.xml already patched, skip")
        return

    # The whole action_misc item block (from `<item android:id="@+id/action_misc"`
    # to its closing `</item>` right before `</menu>`).
    start_tag = '        android:id="@+id/action_misc"'
    start = src.find(start_tag)
    assert start != -1, "action_misc not found"
    # find the start of the <item line
    item_start = src.rfind("<item", 0, start)
    assert item_start != -1
    # The action_misc item is the last one; its closing </item> is followed by
    # "\n\n</menu>". Find that to get the true end of the block.
    end_marker = "</item>\n\n</menu>"
    end_pos = src.find(end_marker, start)
    assert end_pos != -1, "action_misc end not found"
    item_end = end_pos + len("</item>")

    new_block = '''<item
        android:id="@+id/action_misc"
        android:icon="@drawable/ic_baseline_more_vert_24"
        android:title=""
        app:showAsAction="always">
        <menu>
            <!-- %s: reordered/renamed to match v2rayNG -->
            <item
                android:id="@+id/action_restart_service"
                android:title="@string/restart_service" />
            <item
                android:id="@+id/action_delete_all"
                android:title="@string/delete_all_configs" />
            <item
                android:id="@+id/action_remove_duplicate"
                android:title="@string/remove_duplicate" />
            <item
                android:id="@+id/action_connection_test_delete_unavailable"
                android:title="@string/connection_test_delete_unavailable" />
            <item
                android:id="@+id/action_export_all_clipboard"
                android:title="@string/export_all_clipboard" />
            <item
                android:id="@+id/action_locate_selected"
                android:title="@string/locate_selected" />
            <item
                android:id="@+id/action_order"
                android:title="@string/group_order">
                <menu>
                    <group android:checkableBehavior="single">
                        <item
                            android:id="@+id/action_order_origin"
                            android:title="@string/group_order_origin" />
                        <item
                            android:id="@+id/action_order_by_name"
                            android:title="@string/group_order_by_name" />
                        <item
                            android:id="@+id/action_order_by_delay"
                            android:title="@string/group_order_by_delay" />
                    </group>
                </menu>
            </item>
            <item
                android:id="@+id/action_connection_tcp_ping"
                android:title="@string/connection_test_tcp_ping" />
            <item
                android:id="@+id/action_connection_url_test"
                android:title="@string/connection_test_url_test" />
            <item
                android:id="@+id/action_update_subscription"
                android:title="@string/update_current_subscription" />
        </menu>
    </item>''' % MARKER

    src = src[:item_start] + new_block + src[item_end:]

    with open(path, "w", encoding="utf-8") as f:
        f.write(src)
    print("add_profile_menu.xml patched OK")


def patch_strings_zh(path):
    with open(path, encoding="utf-8") as f:
        src = f.read()
    if MARKER in src:
        print("strings.xml (zh-rCN) already patched, skip")
        return

    renames = [
        ('<string name="remove_duplicate">删除重复的服务器</string>',
         '<string name="remove_duplicate">删除重复配置</string>'),
        ('<string name="connection_test_delete_unavailable">清理不可用配置</string>',
         '<string name="connection_test_delete_unavailable">删除无效配置</string>'),
        ('<string name="group_order">排序</string>',
         '<string name="group_order">按测试结果排序</string>'),
        ('<string name="update_current_subscription">更新当前组订阅</string>',
         '<string name="update_current_subscription">更新订阅</string>'),
    ]
    for old, new in renames:
        assert src.count(old) == 1, "zh string not found exactly once: %s" % old[:50]
        src = src.replace(old, new)

    # Add new strings right after update_current_subscription.
    anchor = '    <string name="update_current_subscription">更新订阅</string>\n'
    assert src.count(anchor) == 1, "zh anchor not found"
    addition = (
        anchor +
        '    <!-- %s: v2rayNG menu items -->\n' % MARKER +
        '    <string name="restart_service">服务重启</string>\n' +
        '    <string name="delete_all_configs">删除配置</string>\n' +
        '    <string name="export_all_clipboard">将配置导出至剪贴板</string>\n' +
        '    <string name="locate_selected">定位所选配置</string>\n'
    )
    src = src.replace(anchor, addition)

    with open(path, "w", encoding="utf-8") as f:
        f.write(src)
    print("strings.xml (zh-rCN) patched OK")


def patch_strings_en(path):
    with open(path, encoding="utf-8") as f:
        src = f.read()
    if MARKER in src:
        print("strings.xml (en) already patched, skip")
        return

    renames = [
        ('<string name="connection_test_tcp_ping" translatable="false">TCPing</string>',
         '<string name="connection_test_tcp_ping" translatable="false">Test TCP latency (TCPing)</string>'),
        ('<string name="connection_test_url_test" translatable="false">URL Test</string>',
         '<string name="connection_test_url_test" translatable="false">Test real connection latency</string>'),
        ('<string name="remove_duplicate">Remove duplicate servers</string>',
         '<string name="remove_duplicate">Remove duplicate configs</string>'),
        ('<string name="connection_test_delete_unavailable">Clear unavailable</string>',
         '<string name="connection_test_delete_unavailable">Delete invalid configs</string>'),
        ('<string name="group_order">Order</string>',
         '<string name="group_order">Order by test results</string>'),
        ("<string name=\"update_current_subscription\">Update current Group\\'s subscription</string>",
         '<string name="update_current_subscription">Update subscription</string>'),
    ]
    for old, new in renames:
        assert src.count(old) == 1, "en string not found exactly once: %s" % old[:60]
        src = src.replace(old, new)

    anchor = '    <string name="update_current_subscription">Update subscription</string>\n'
    assert src.count(anchor) == 1, "en anchor not found"
    addition = (
        anchor +
        '    <!-- %s: v2rayNG menu items -->\n' % MARKER +
        '    <string name="restart_service">Restart service</string>\n' +
        '    <string name="delete_all_configs">Delete configs</string>\n' +
        '    <string name="export_all_clipboard">Export configs to clipboard</string>\n' +
        '    <string name="locate_selected">Locate selected config</string>\n'
    )
    src = src.replace(anchor, addition)

    with open(path, "w", encoding="utf-8") as f:
        f.write(src)
    print("strings.xml (en) patched OK")


def patch_kt(path):
    with open(path, encoding="utf-8") as f:
        src = f.read()
    if MARKER in src:
        print("ConfigurationFragment.kt already patched, skip")
        return

    # 1. Remove the action_clear_traffic_statistics handler block.
    old_clear_traffic = '''            R.id.action_clear_traffic_statistics -> {
                runOnDefaultDispatcher {
                    val profiles = SagerDatabase.proxyDao.getByGroup(DataStore.currentGroupId())
                    val toClear = mutableListOf<ProxyEntity>()
                    if (profiles.isNotEmpty()) for (profile in profiles) {
                        if (profile.tx != 0L || profile.rx != 0L) {
                            profile.tx = 0
                            profile.rx = 0
                            toClear.add(profile)
                        }
                    }
                    if (toClear.isNotEmpty()) {
                        ProfileManager.updateProfile(toClear)
                    }
                }
            }

'''
    assert src.count(old_clear_traffic) == 1, "clear_traffic handler not found exactly once"
    src = src.replace(old_clear_traffic, "")

    # 2. Remove the action_connection_test_clear_results handler block.
    old_clear_results = '''            R.id.action_connection_test_clear_results -> {
                runOnDefaultDispatcher {
                    val profiles = SagerDatabase.proxyDao.getByGroup(DataStore.currentGroupId())
                    val toClear = mutableListOf<ProxyEntity>()
                    if (profiles.isNotEmpty()) for (profile in profiles) {
                        if (profile.status != 0) {
                            profile.status = 0
                            profile.ping = 0
                            profile.error = null
                            toClear.add(profile)
                        }
                    }
                    if (toClear.isNotEmpty()) {
                        ProfileManager.updateProfile(toClear)
                    }
                }
            }

'''
    assert src.count(old_clear_results) == 1, "clear_results handler not found exactly once"
    src = src.replace(old_clear_results, "")

    # 3. Add the four new handlers right before the tcp_ping branch.
    anchor = '''            R.id.action_connection_tcp_ping -> {
                pingTest(false)
            }
'''
    assert src.count(anchor) == 1, "tcp_ping anchor not found exactly once"
    new_handlers = '''            // %s: v2rayNG menu items
            R.id.action_restart_service -> {
                if (DataStore.serviceState.started) {
                    SagerNet.reloadService()
                } else {
                    SagerNet.startService()
                }
            }

            R.id.action_delete_all -> {
                MaterialAlertDialogBuilder(requireContext()).setTitle(R.string.confirm)
                    .setMessage(R.string.clear_profiles_message)
                    .setPositiveButton(R.string.yes) { _, _ ->
                        runOnDefaultDispatcher {
                            GroupManager.clearGroup(DataStore.currentGroupId())
                        }
                    }
                    .setNegativeButton(android.R.string.cancel, null)
                    .show()
            }

            R.id.action_export_all_clipboard -> {
                runOnDefaultDispatcher {
                    val profiles = SagerDatabase.proxyDao.getByGroup(DataStore.currentGroupId())
                    val links = profiles.mapNotNull {
                        try {
                            it.toStdLink()
                        } catch (e: Exception) {
                            Logs.w(e)
                            null
                        }
                    }.joinToString("\\n")
                    onMainDispatcher {
                        val success = SagerNet.trySetPrimaryClip(links)
                        (activity as MainActivity).snackbar(
                            if (success) R.string.action_export_msg else R.string.action_export_err
                        ).show()
                    }
                }
            }

            R.id.action_locate_selected -> {
                val fragment = getCurrentGroupFragment()
                if (fragment != null) {
                    val selectedProxy = selectedItem?.id ?: DataStore.selectedProxy
                    val selectedProfileIndex =
                        fragment.adapter!!.configurationIdList.indexOf(selectedProxy)
                    if (selectedProfileIndex != -1) {
                        fragment.configurationListView.scrollTo(selectedProfileIndex, true)
                    }
                }
            }

''' % MARKER
    src = src.replace(anchor, new_handlers + anchor)

    with open(path, "w", encoding="utf-8") as f:
        f.write(src)
    print("ConfigurationFragment.kt patched OK")


def main():
    patch_xml(XML_TARGET)
    patch_strings_zh(STR_ZH)
    patch_strings_en(STR_EN)
    patch_kt(KT_TARGET)
    print("All main-menu patches applied.")


if __name__ == "__main__":
    main()
