#!/usr/bin/env python3
"""Patch NekoBox: quick Load Balance toggle on the main screen.

User feedback: "在分组用的不方便" (the group-settings entry is inconvenient).

This adds a checkable "负载均衡" item to the main screen's overflow (⋮)
menu (the action_misc submenu of add_profile_menu.xml, already reordered by
patch_main_menu.py). Tapping it toggles the SAME DataStore.loadBalance key
that the group-settings switch uses, so both entries stay in sync and the
group-settings switch keeps working (backward compatible).

When turning ON from the main screen, the current group's selector mode is
auto-enabled (ProxyGroup.isSelector = true via GroupManager.updateGroup),
so the user no longer has to open group settings first. When turning OFF,
selector mode is left untouched.

A config rebuild (service restart) is needed for the change to take
effect; a snackbar tells the user.

Files touched (all under the NekoBox checkout, run from its root):

1. app/src/main/res/menu/add_profile_menu.xml
   - Add checkable item `action_load_balance` at the end of the
     action_misc submenu (after action_update_subscription).

2. app/src/main/java/io/nekohasekai/sagernet/ui/ConfigurationFragment.kt
   - onMenuItemClick: handle R.id.action_load_balance (toggle
     DataStore.loadBalance, auto-enable selector on the current group,
     refresh the check mark, show snackbar).
   - onViewCreated: set the initial checked state after inflateMenu.
   - onResume (new override): re-sync the checked state in case it was
     changed via group settings.

3. app/src/main/res/values/strings.xml
   - Add `load_balance_enabled` / `load_balance_disabled` (English).

4. app/src/main/res/values-zh-rCN/strings.xml
   - Add `load_balance_enabled` / `load_balance_disabled` (Chinese).

Requires patch_loadbalance.py to have run first (DataStore.loadBalance and
R.string.load_balance must exist); fails fast otherwise.

Idempotent: re-running is a no-op (marker checks in each file).
"""
import sys

MARKER = "loadBalanceQuickToggle"

MENU_TARGET = "app/src/main/res/menu/add_profile_menu.xml"
KT_TARGET = "app/src/main/java/io/nekohasekai/sagernet/ui/ConfigurationFragment.kt"
STRINGS_EN_TARGET = "app/src/main/res/values/strings.xml"
STRINGS_ZH_TARGET = "app/src/main/res/values-zh-rCN/strings.xml"


def patch_menu(path):
    with open(path, encoding="utf-8") as f:
        src = f.read()
    if MARKER in src:
        print("add_profile_menu.xml already patched, skip")
        return
    old = """            <item
                android:id="@+id/action_update_subscription"
                android:title="@string/update_current_subscription" />
"""
    assert src.count(old) == 1, "action_update_subscription item not found exactly once"
    new = old + """            <!-- %s: quick load balance toggle on main screen -->
            <item
                android:id="@+id/action_load_balance"
                android:title="@string/load_balance"
                android:checkable="true" />
""" % MARKER
    src = src.replace(old, new)
    with open(path, "w", encoding="utf-8") as f:
        f.write(src)
    print("add_profile_menu.xml patched OK")


def patch_kt(path):
    with open(path, encoding="utf-8") as f:
        src = f.read()
    if MARKER in src:
        print("ConfigurationFragment.kt already patched, skip")
        return

    # 1. Menu click handler, inserted before the tcp_ping branch.
    anchor = """            R.id.action_connection_tcp_ping -> {
                pingTest(false)
            }
"""
    assert src.count(anchor) == 1, "tcp_ping handler anchor not found exactly once"
    handler = """            // %s: quick load balance toggle on main screen.
            // Same DataStore.loadBalance key as the group settings switch;
            // auto-enables selector mode on the current group when turning on.
            R.id.action_load_balance -> {
                runOnDefaultDispatcher {
                    val enable = !DataStore.loadBalance
                    DataStore.loadBalance = enable
                    if (enable) {
                        val group = DataStore.currentGroup()
                        if (!group.isSelector) {
                            group.isSelector = true
                            GroupManager.updateGroup(group)
                        }
                    }
                    onMainDispatcher {
                        toolbar.menu.findItem(R.id.action_load_balance)?.isChecked = enable
                        snackbar(
                            if (enable) R.string.load_balance_enabled
                            else R.string.load_balance_disabled
                        ).show()
                    }
                }
            }

""" % MARKER
    src = src.replace(anchor, handler + anchor)

    # 2. Initial checked state right after the menu is inflated.
    anchor2 = """            toolbar.inflateMenu(R.menu.add_profile_menu)
            toolbar.setOnMenuItemClickListener(this)
"""
    assert src.count(anchor2) == 1, "inflateMenu anchor not found exactly once"
    src = src.replace(
        anchor2,
        anchor2
        + "            toolbar.menu.findItem(R.id.action_load_balance)?.isChecked = DataStore.loadBalance // %s\n" % MARKER,
    )

    # 3. onResume: re-sync in case the switch was changed via group settings.
    anchor3 = "    override fun onPreferenceDataStoreChanged(store: PreferenceDataStore, key: String) {\n"
    assert src.count(anchor3) == 1, "onPreferenceDataStoreChanged anchor not found exactly once"
    src = src.replace(
        anchor3,
        """    // %s: keep the quick toggle in sync (e.g. changed via group settings)
    override fun onResume() {
        super.onResume()
        toolbar.menu.findItem(R.id.action_load_balance)?.isChecked = DataStore.loadBalance
    }

""" % MARKER + anchor3,
    )

    with open(path, "w", encoding="utf-8") as f:
        f.write(src)
    print("ConfigurationFragment.kt patched OK")


def patch_strings_en(path):
    with open(path, encoding="utf-8") as f:
        src = f.read()
    if MARKER in src:
        print("strings.xml (en) already patched, skip")
        return
    old = '    <string name="load_balance_summary">Auto select the lowest latency node (urltest)</string>\n'
    assert src.count(old) == 1, "load_balance_summary (en) not found exactly once"
    new = old + """    <!-- %s -->
    <string name="load_balance_enabled">Load balance enabled, restart service to take effect</string>
    <string name="load_balance_disabled">Load balance disabled, restart service to take effect</string>
""" % MARKER
    src = src.replace(old, new)
    with open(path, "w", encoding="utf-8") as f:
        f.write(src)
    print("strings.xml (en) patched OK")


def patch_strings_zh(path):
    with open(path, encoding="utf-8") as f:
        src = f.read()
    if MARKER in src:
        print("strings.xml (zh) already patched, skip")
        return
    old = '    <string name="load_balance_summary">自动选择延迟最低的节点（urltest）</string>\n'
    assert src.count(old) == 1, "load_balance_summary (zh) not found exactly once"
    new = old + """    <!-- %s -->
    <string name="load_balance_enabled">已开启负载均衡，重启服务后生效</string>
    <string name="load_balance_disabled">已关闭负载均衡，重启服务后生效</string>
""" % MARKER
    src = src.replace(old, new)
    with open(path, "w", encoding="utf-8") as f:
        f.write(src)
    print("strings.xml (zh) patched OK")


def main():
    # sanity: the base load balance patch must have run first
    with open("app/src/main/java/io/nekohasekai/sagernet/database/DataStore.kt", encoding="utf-8") as f:
        if "loadBalancePatch" not in f.read():
            sys.exit("ERROR: patch_loadbalance.py must run before patch_loadbalance_quick.py")
    patch_menu(MENU_TARGET)
    patch_kt(KT_TARGET)
    patch_strings_en(STRINGS_EN_TARGET)
    patch_strings_zh(STRINGS_ZH_TARGET)
    print("All load balance quick-toggle patches applied OK")


if __name__ == "__main__":
    main()
