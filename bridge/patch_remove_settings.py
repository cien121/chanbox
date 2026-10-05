#!/usr/bin/env python3
"""从设置页面移除"启用 Clash API"和"像 SagerNet 一样显示底栏"两项。

用户要求删除设置页面的这两项（2026-10-05）：
  1. 启用 Clash API（在 127.0.0.1:9090 提供 clash api 和 yacd 仪表板）
  2. 像 SagerNet 一样显示底栏

改动（在 NekoBox checkout 根目录运行，幂等）：
  1. app/src/main/res/xml/global_preferences.xml：
     删除 key="enableClashAPI" 和 key="showBottomBar" 的 <SwitchPreference> 块。
     底层 DataStore/Constants 的 key 定义保留，只移除 UI 显示。
  2. app/src/main/java/io/nekohasekai/sagernet/ui/SettingsPreferenceFragment.kt：
     删除 findPreference<SwitchPreference>(Key.ENABLE_CLASH_API)!! 块
     （XML 项删除后 findPreference 返回 null，!! 会导致 NPE，必须同步删除）。

注意：MainActivity.refreshNavMenu(DataStore.enableClashAPI) 的调用保留，
它用的是 DataStore 存储值（默认 false），且内部用 ?. 安全调用，
不会因 UI 项删除而出问题。
"""
import re
import sys
from pathlib import Path

MARKER = "<!-- rmSettingsPatched -->"

XML_PATH = Path("app/src/main/res/xml/global_preferences.xml")
KT_PATH = Path("app/src/main/java/io/nekohasekai/sagernet/ui/SettingsPreferenceFragment.kt")

# 要删除的 XML 块（精确匹配 NekoBox pin 5768494 的内容）
CLASH_API_BLOCK = '''        <SwitchPreference
            app:icon="@drawable/baseline_construction_24"
            app:key="enableClashAPI"
            app:summary="@string/enable_clash_api_summary"
            app:title="@string/enable_clash_api" />
'''

BOTTOM_BAR_BLOCK = '''        <SwitchPreference
            app:key="showBottomBar"
            app:title="@string/show_bottom_bar" />
'''

# 要删除的 Kotlin 块（精确匹配 NekoBox pin 5768494 的内容）
KT_BLOCK = '''        val enableClashAPI = findPreference<SwitchPreference>(Key.ENABLE_CLASH_API)!!
        enableClashAPI.setOnPreferenceChangeListener { _, newValue ->
            (activity as MainActivity?)?.refreshNavMenu(newValue as Boolean)
            needReload()
            true
        }
'''


def patch_xml() -> bool:
    """删除 XML 中的两项，返回是否发生改动。"""
    if not XML_PATH.is_file():
        print(f"ERROR: {XML_PATH} 不存在", file=sys.stderr)
        return False
    text = XML_PATH.read_text(encoding="utf-8")
    if MARKER in text:
        print("XML 已打过补丁，跳过")
        return False

    changed = False
    for name, block in (("enableClashAPI", CLASH_API_BLOCK),
                        ("showBottomBar", BOTTOM_BAR_BLOCK)):
        if block in text:
            text = text.replace(block, "", 1)
            changed = True
            print(f"XML: 已删除 {name} 项")
        else:
            # 兜底：用正则按 key 匹配删除（容忍属性顺序/空白差异）
            pattern = re.compile(
                r'<SwitchPreference\b[^>]*\bapp:key="%s"[^>]*/>\s*' % re.escape(name)
            )
            new_text, n = pattern.subn("", text, count=1)
            if n:
                text = new_text
                changed = True
                print(f"XML: 已删除 {name} 项（正则兜底）")
            else:
                print(f"XML: 未找到 {name} 项（可能已被删除）")

    if changed:
        # 在 </PreferenceScreen> 前插入 marker，保证幂等
        text = text.replace("</PreferenceScreen>", MARKER + "\n</PreferenceScreen>", 1)
        XML_PATH.write_text(text, encoding="utf-8")
        # 简单校验 XML 合法性
        import xml.dom.minidom
        xml.dom.minidom.parseString(text)
        print("XML 合法性校验通过")
    return changed


def patch_kotlin() -> bool:
    """删除 Kotlin 中的 findPreference 块，返回是否发生改动。"""
    if not KT_PATH.is_file():
        print(f"ERROR: {KT_PATH} 不存在", file=sys.stderr)
        return False
    text = KT_PATH.read_text(encoding="utf-8")
    marker = "// rmSettingsPatched"
    if marker in text:
        print("Kotlin 已打过补丁，跳过")
        return False

    changed = False
    if KT_BLOCK in text:
        text = text.replace(KT_BLOCK, "", 1)
        changed = True
        print("Kotlin: 已删除 enableClashAPI findPreference 块")
    else:
        # 兜底：正则删除 findPreference(ENABLE_CLASH_API)!! 开头的块
        pattern = re.compile(
            r'^[ \t]*val enableClashAPI = findPreference<SwitchPreference>\(Key\.ENABLE_CLASH_API\)!!\n'
            r'(?:[ \t]*.*\n)*?'
            r'^[ \t]*\}\n',
            re.MULTILINE,
        )
        new_text, n = pattern.subn("", text, count=1)
        if n:
            text = new_text
            changed = True
            print("Kotlin: 已删除 enableClashAPI findPreference 块（正则兜底）")
        else:
            print("Kotlin: 未找到 enableClashAPI findPreference 块（可能已被删除）")

    if changed:
        # 在文件末尾追加 marker，保证幂等
        if not text.endswith("\n"):
            text += "\n"
        text += marker + "\n"
        KT_PATH.write_text(text, encoding="utf-8")
    return changed


def main() -> int:
    xml_changed = patch_xml()
    kt_changed = patch_kotlin()
    if xml_changed or kt_changed:
        print("patch_remove_settings.py: 改动已应用")
    else:
        print("patch_remove_settings.py: 无需改动（已是最新）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
