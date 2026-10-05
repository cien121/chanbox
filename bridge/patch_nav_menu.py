#!/usr/bin/env python3
"""Patch NekoBox nav drawer: remove Promote/Documents/About menu items.

User request: the side navigation drawer should only keep
Configuration / Group / Route / Settings / Log / Tools.
Remove the last group (推广=nav_tuiguang, 文档=nav_faq, 关于=nav_about).

Two files are touched (both under the NekoBox checkout, run from its root):

1. app/src/main/res/menu/main_drawer_menu.xml
   Delete the whole <group android:id="@+id/about"> ... </group> block.

2. app/src/main/java/io/nekohasekai/sagernet/ui/MainActivity.kt
   - refreshNavMenu(): drop the nav_tuiguang visibility line
     (R.id.nav_tuiguang no longer exists after the XML change, so the
     reference would fail compilation).
   - displayFragmentWithId(): drop the now-dead when branches for
     nav_faq / nav_about / nav_tuiguang.
   - Drop the now-unused `import io.nekohasekai.sagernet.ktx.isPlay`.

Idempotent: re-running is a no-op (marker comment left in both files).
"""
import sys

XML_TARGET = "app/src/main/res/menu/main_drawer_menu.xml"
KT_TARGET = "app/src/main/java/io/nekohasekai/sagernet/ui/MainActivity.kt"
MARKER = "navMenuPruned"


def patch_xml(path):
    with open(path, encoding="utf-8") as f:
        src = f.read()
    if MARKER in src:
        print("main_drawer_menu.xml already patched, skip")
        return

    old = (
        '\n    <group\n'
        '        android:id="@+id/about"\n'
        '        android:checkableBehavior="single">\n'
        '        <item\n'
        '            android:id="@+id/nav_tuiguang"\n'
        '            android:icon="@drawable/ic_social_share"\n'
        '            android:title="@string/ads" />\n'
        '        <item\n'
        '            android:id="@+id/nav_faq"\n'
        '            android:icon="@drawable/ic_device_data_usage"\n'
        '            android:title="@string/document" />\n'
        '        <item\n'
        '            android:id="@+id/nav_about"\n'
        '            android:icon="@drawable/ic_baseline_info_24"\n'
        '            android:title="@string/menu_about" />\n'
        '    </group>\n'
    )
    assert src.count(old) == 1, "about group block not found exactly once"
    # Leave a single blank line between </group> and </menu>, plus marker.
    new = f"\n<!-- {MARKER}: Promote/Documents/About removed per user request -->\n"
    src = src.replace(old, new)

    with open(path, "w", encoding="utf-8") as f:
        f.write(src)
    print("main_drawer_menu.xml patched OK")


def patch_kt(path):
    with open(path, encoding="utf-8") as f:
        src = f.read()
    if MARKER in src:
        print("MainActivity.kt already patched, skip")
        return

    # 1. refreshNavMenu(): drop nav_tuiguang visibility line.
    old1 = "            navigation.menu.findItem(R.id.nav_tuiguang)?.isVisible = !isPlay\n"
    assert src.count(old1) == 1, "nav_tuiguang visibility line not found"
    src = src.replace(old1, "")

    # 2. Drop the now-unused isPlay import.
    old2 = "import io.nekohasekai.sagernet.ktx.isPlay\n"
    assert src.count(old2) == 1, "isPlay import not found"
    src = src.replace(old2, "")

    # 3. Drop the dead when branches for nav_faq / nav_about / nav_tuiguang.
    old3 = (
        "            R.id.nav_faq -> {\n"
        '                launchCustomTab("https://matsuridayo.github.io/")\n'
        "                return false\n"
        "            }\n"
        "\n"
        "            R.id.nav_about -> displayFragment(AboutFragment())\n"
        "            R.id.nav_tuiguang -> {\n"
        '                launchCustomTab("https://neko-box.pages.dev/\u55b5")\n'
        "                return false\n"
        "            }\n"
        "\n"
        "            else -> return false"
    )
    assert src.count(old3) == 1, "nav when-branches not found exactly once"
    new3 = (
        f"            // {MARKER}: nav_faq/nav_about/nav_tuiguang branches removed\n"
        "            else -> return false"
    )
    src = src.replace(old3, new3)

    with open(path, "w", encoding="utf-8") as f:
        f.write(src)
    print("MainActivity.kt patched OK")


def main():
    xml_path = sys.argv[1] if len(sys.argv) > 1 else XML_TARGET
    kt_path = sys.argv[2] if len(sys.argv) > 2 else KT_TARGET
    patch_xml(xml_path)
    patch_kt(kt_path)


if __name__ == "__main__":
    main()
