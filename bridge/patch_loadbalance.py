#!/usr/bin/env python3
"""Patch NekoBox to add load balance (urltest) support.

User request: "能不能做负载均衡" (can you do load balancing).

Background:
- sing-box has a `urltest` outbound type that automatically selects the
  lowest-latency outbound from a list, re-testing periodically.
- NekoBox already has `Outbound_URLTestOptions` in SingBoxOptions.java and
  a `selector` group mode (`group.isSelector` -> selector outbound tagged
  "proxy" containing all profiles in the group).
- This patch adds a global "Load Balance" toggle. When enabled AND the
  current group is in selector mode, the generated "proxy" outbound uses
  `urltest` type instead of `selector`, so traffic automatically goes to
  the fastest node.

Files touched (all under the NekoBox checkout, run from its root):

1. app/src/main/java/io/nekohasekai/sagernet/Constants.kt
   - Add `const val LOAD_BALANCE = "loadBalance"` after GROUP_IS_SELECTOR.

2. app/src/main/java/io/nekohasekai/sagernet/database/DataStore.kt
   - Add `var loadBalance by configurationStore.boolean(Key.LOAD_BALANCE)`.

3. app/src/main/res/xml/group_preferences.xml
   - Add SwitchPreference `loadBalance` after the `groupIsSelector` item,
     with `app:dependency="groupIsSelector"` so it is only enabled when
     selector mode is on.

4. app/src/main/res/values/strings.xml
   - Add `load_balance` / `load_balance_summary` (English).

5. app/src/main/res/values-zh-rCN/strings.xml
   - Add `load_balance` / `load_balance_summary` (Chinese).

6. app/src/main/java/io/nekohasekai/sagernet/fmt/ConfigBuilder.kt
   - In the `if (buildSelector)` block: when `DataStore.loadBalance` is
     true, emit `Outbound_URLTestOptions` (type=urltest, url=
     https://www.gstatic.com/generate_204, tolerance=50, interval=5m via
     _hack_config_map) instead of `Outbound_SelectorOptions`.

Idempotent: re-running is a no-op (marker checks in each file).
"""
import sys

MARKER = "loadBalancePatch"

CONSTANTS_TARGET = "app/src/main/java/io/nekohasekai/sagernet/Constants.kt"
DATASTORE_TARGET = "app/src/main/java/io/nekohasekai/sagernet/database/DataStore.kt"
GROUP_PREFS_TARGET = "app/src/main/res/xml/group_preferences.xml"
STRINGS_EN_TARGET = "app/src/main/res/values/strings.xml"
STRINGS_ZH_TARGET = "app/src/main/res/values-zh-rCN/strings.xml"
CONFIG_BUILDER_TARGET = "app/src/main/java/io/nekohasekai/sagernet/fmt/ConfigBuilder.kt"


def patch_constants(path):
    with open(path, encoding="utf-8") as f:
        src = f.read()
    if MARKER in src:
        print("Constants.kt already patched, skip")
        return
    old = '    const val GROUP_IS_SELECTOR = "groupIsSelector"\n'
    assert src.count(old) == 1, "GROUP_IS_SELECTOR not found exactly once"
    new = old + '    const val LOAD_BALANCE = "loadBalance"\n'
    src = src.replace(old, new)
    # marker comment
    src = src.replace(
        '    const val LOAD_BALANCE = "loadBalance"\n',
        '    const val LOAD_BALANCE = "loadBalance" // %s\n' % MARKER,
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(src)
    print("Constants.kt patched OK")


def patch_datastore(path):
    with open(path, encoding="utf-8") as f:
        src = f.read()
    if MARKER in src:
        print("DataStore.kt already patched, skip")
        return
    old = "    var showBottomBar by configurationStore.boolean(Key.SHOW_BOTTOM_BAR)\n"
    assert src.count(old) == 1, "showBottomBar not found exactly once"
    new = old + "    var loadBalance by configurationStore.boolean(Key.LOAD_BALANCE) // %s\n" % MARKER
    src = src.replace(old, new)
    with open(path, "w", encoding="utf-8") as f:
        f.write(src)
    print("DataStore.kt patched OK")


def patch_group_prefs(path):
    with open(path, encoding="utf-8") as f:
        src = f.read()
    if MARKER in src:
        print("group_preferences.xml already patched, skip")
        return
    old = """    <SwitchPreference
        app:icon="@drawable/ic_baseline_manage_search_24"
        app:key="groupIsSelector"
        app:title="@string/use_selector" />
"""
    assert src.count(old) == 1, "groupIsSelector preference not found exactly once"
    new = old + """
    <!-- %s: load balance toggle, only enabled in selector mode -->
    <SwitchPreference
        app:key="loadBalance"
        app:title="@string/load_balance"
        app:summary="@string/load_balance_summary"
        app:dependency="groupIsSelector" />
""" % MARKER
    src = src.replace(old, new)
    with open(path, "w", encoding="utf-8") as f:
        f.write(src)
    print("group_preferences.xml patched OK")


def patch_strings_en(path):
    with open(path, encoding="utf-8") as f:
        src = f.read()
    if MARKER in src:
        print("strings.xml (en) already patched, skip")
        return
    old = '    <string name="use_selector">Use selector</string>\n'
    assert src.count(old) == 1, "use_selector string not found exactly once"
    new = old + """    <!-- %s -->
    <string name="load_balance">Load Balance</string>
    <string name="load_balance_summary">Auto select the lowest latency node (urltest)</string>
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
    old = '    <string name="use_selector">启用 selector （免重载切换节点）</string>\n'
    assert src.count(old) == 1, "use_selector string (zh) not found exactly once"
    new = old + """    <!-- %s -->
    <string name="load_balance">负载均衡</string>
    <string name="load_balance_summary">自动选择延迟最低的节点（urltest）</string>
""" % MARKER
    src = src.replace(old, new)
    with open(path, "w", encoding="utf-8") as f:
        f.write(src)
    print("strings.xml (zh) patched OK")


def patch_config_builder(path):
    with open(path, encoding="utf-8") as f:
        src = f.read()
    if MARKER in src:
        print("ConfigBuilder.kt already patched, skip")
        return
    old = """        if (buildSelector) {
            val list = group.id.let { SagerDatabase.proxyDao.getByGroup(it) }
            list.forEach {
                tagMap[it.id] = buildChain(it.id, it)
            }
            outbounds.add(0, Outbound_SelectorOptions().apply {
                type = "selector"
                tag = TAG_PROXY
                default_ = tagMap[proxy.id]
                outbounds = tagMap.values.toList()
            })
        } else {"""
    assert src.count(old) == 1, "selector outbound block not found exactly once"
    new = """        if (buildSelector) {
            val list = group.id.let { SagerDatabase.proxyDao.getByGroup(it) }
            list.forEach {
                tagMap[it.id] = buildChain(it.id, it)
            }
            // %s: load balance mode -> urltest auto-selects lowest latency node
            if (DataStore.loadBalance) {
                outbounds.add(0, Outbound_URLTestOptions().apply {
                    type = "urltest"
                    tag = TAG_PROXY
                    outbounds = tagMap.values.toList()
                    url = "https://www.gstatic.com/generate_204"
                    tolerance = 50
                    _hack_config_map["interval"] = "5m"
                })
            } else {
                outbounds.add(0, Outbound_SelectorOptions().apply {
                    type = "selector"
                    tag = TAG_PROXY
                    default_ = tagMap[proxy.id]
                    outbounds = tagMap.values.toList()
                })
            }
        } else {""" % MARKER
    src = src.replace(old, new)
    with open(path, "w", encoding="utf-8") as f:
        f.write(src)
    print("ConfigBuilder.kt patched OK")


def main():
    patch_constants(CONSTANTS_TARGET)
    patch_datastore(DATASTORE_TARGET)
    patch_group_prefs(GROUP_PREFS_TARGET)
    patch_strings_en(STRINGS_EN_TARGET)
    patch_strings_zh(STRINGS_ZH_TARGET)
    patch_config_builder(CONFIG_BUILDER_TARGET)
    print("All load balance patches applied OK")


if __name__ == "__main__":
    main()
