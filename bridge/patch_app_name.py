#!/usr/bin/env python3
"""Patch NekoBox app display name: ChanBox -> RelayBox.

User request: rename the app from ChanBox to RelayBox (display name only,
package name com.chan.box stays unchanged).

Background: .github/workflows/build.yml runs a sed that changes
<string name="app_name">NekoBox</string> to ChanBox before integrate.sh runs.
This patch runs after that, renaming ChanBox -> RelayBox. It also fixes
app_name_long which the workflow sed leaves as "NekoBox for Android".

Files touched (all under the NekoBox checkout, run from its root):

1. app/src/main/res/values/strings.xml
   - app_name: ChanBox -> RelayBox (also handles NekoBox in case the
     workflow sed ever changes)
   - app_name_long: "NekoBox for Android" -> "RelayBox for Android"
     (shown as the title on the About page via layout_about.xml)

2. app/src/main/java/io/nekohasekai/sagernet/utils/CrashHandler.kt
   - crash report header "NekoBox for Android ..." -> "RelayBox for Android ..."

3. app/src/main/java/io/nekohasekai/sagernet/ui/BackupFragment.kt
   - backup file name prefix "nekobox_backup_" -> "relaybox_backup_"

Not touched (deliberately):
- Nets.kt USER_AGENT ("NekoBox/Android/..."): server-facing identifier,
  renaming it could affect remote identification; left as is.
- AboutFragment.kt GitHub URLs: they point at the real upstream repo.
- Package name / applicationId: unchanged per user request.
- app_name is translatable="false", so values-zh-rCN needs no change.

Idempotent: re-running is a no-op (marker comment left in each file).
"""
import sys

XML_TARGET = "app/src/main/res/values/strings.xml"
CRASH_TARGET = "app/src/main/java/io/nekohasekai/sagernet/utils/CrashHandler.kt"
BACKUP_TARGET = "app/src/main/java/io/nekohasekai/sagernet/ui/BackupFragment.kt"
MARKER = "appNameRelayBox"


def patch_strings_xml(path):
    with open(path, encoding="utf-8") as f:
        src = f.read()
    if MARKER in src:
        print("strings.xml already patched, skip")
        return

    # app_name: workflow sed already turned NekoBox into ChanBox; be robust
    # to both in case the workflow ever changes.
    old_name = '<string name="app_name" translatable="false">ChanBox</string>'
    if src.count(old_name) != 1:
        old_name = '<string name="app_name" translatable="false">NekoBox</string>'
    assert src.count(old_name) == 1, "app_name string not found exactly once"
    src = src.replace(
        old_name,
        '<string name="app_name" translatable="false">RelayBox</string>',
    )

    old_long = '<string name="app_name_long" translatable="false">NekoBox for Android</string>'
    assert src.count(old_long) == 1, "app_name_long string not found exactly once"
    src = src.replace(
        old_long,
        '<string name="app_name_long" translatable="false">RelayBox for Android</string>',
    )

    # marker right after the app_name_long line
    src = src.replace(
        '<string name="app_name_long" translatable="false">RelayBox for Android</string>\n',
        '<string name="app_name_long" translatable="false">RelayBox for Android</string>\n'
        f'    <!-- {MARKER}: app display name renamed to RelayBox -->\n',
    )

    with open(path, "w", encoding="utf-8") as f:
        f.write(src)
    print("strings.xml patched OK")


def patch_crash_handler(path):
    with open(path, encoding="utf-8") as f:
        src = f.read()
    if MARKER in src:
        print("CrashHandler.kt already patched, skip")
        return

    old = '"NekoBox for Android '
    assert src.count(old) == 1, "crash report header not found exactly once"
    src = src.replace(old, '"RelayBox for Android ')
    # add marker comment above the changed line
    lines = src.split("\n")
    for i, line in enumerate(lines):
        if 'report += "RelayBox for Android ' in line:
            indent = line[: len(line) - len(line.lstrip())]
            lines.insert(i, f"{indent}// {MARKER}: renamed from NekoBox for Android")
            break
    src = "\n".join(lines)

    with open(path, "w", encoding="utf-8") as f:
        f.write(src)
    print("CrashHandler.kt patched OK")


def patch_backup_fragment(path):
    with open(path, encoding="utf-8") as f:
        src = f.read()
    if MARKER in src:
        print("BackupFragment.kt already patched, skip")
        return

    old = "nekobox_backup_"
    n = src.count(old)
    assert n >= 1, "backup file prefix not found"
    src = src.replace(old, "relaybox_backup_")

    # marker comment at end of file
    if not src.endswith("\n"):
        src += "\n"
    src += f"// {MARKER}: backup file prefix renamed to relaybox_backup_ ({n} occurrence(s))\n"

    with open(path, "w", encoding="utf-8") as f:
        f.write(src)
    print(f"BackupFragment.kt patched OK ({n} occurrence(s))")


def main():
    patch_strings_xml(XML_TARGET)
    patch_crash_handler(CRASH_TARGET)
    patch_backup_fragment(BACKUP_TARGET)
    print("patch_app_name done")


if __name__ == "__main__":
    sys.exit(main())
