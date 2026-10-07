#!/usr/bin/env python3
"""One-click diagnostic log export (diag branch only).

Problem: user finds ADB authorization troublesome for grabbing logcat.
This patch adds an "Export diagnostic logs" item to the main screen's
overflow menu (ConfigurationFragment). Tapping it:

  1. Runs `logcat -d` in-process and keeps lines containing "SockProtectDiag"
     (Kotlin-side logs; an app can always read its own logs, no READ_LOGS needed).
  2. Best-effort: reads <cacheDir>/neko.log (Go-side logs) and keeps matching lines.
  3. Writes everything to <externalFilesDir>/sockprotect-log.txt.
  4. Toasts the absolute path + line counts.

Files touched (under the NekoBox checkout, run from its root):

1. app/src/main/res/menu/add_profile_menu.xml
   Append <item android:id="@+id/action_export_diag_log"> after
   action_update_subscription inside the action_misc submenu.

2. app/src/main/res/values-zh-rCN/strings.xml
   Add <string name="export_diag_log">导出诊断日志</string>.

3. app/src/main/res/values/strings.xml
   Add <string name="export_diag_log">Export diagnostic logs</string>.

4. app/src/main/java/io/nekohasekai/sagernet/ui/ConfigurationFragment.kt
   - Add `R.id.action_export_diag_log -> { exportDiagLog() }` branch
     after the action_update_subscription handler in onMenuItemClick.
   - Add `private fun exportDiagLog()` before onMenuItemClick.
     Uses only already-imported APIs (runOnDefaultDispatcher, onMainDispatcher,
     requireContext); Toast is referenced fully-qualified.

Idempotent via marker diagLogExport (per file).
"""

MARKER = "diagLogExport"

MENU_XML = "app/src/main/res/menu/add_profile_menu.xml"
STR_ZH = "app/src/main/res/values-zh-rCN/strings.xml"
STR_EN = "app/src/main/res/values/strings.xml"
FRAGMENT_KT = "app/src/main/java/io/nekohasekai/sagernet/ui/ConfigurationFragment.kt"

# --- menu XML: insert after action_update_subscription (post patch_main_menu.py) ---
MENU_ANCHOR = (
    '                android:id="@+id/action_update_subscription"\n'
    '                android:title="@string/update_current_subscription" />'
)
MENU_INSERT = (
    MENU_ANCHOR + "\n"
    '            <!-- %s: diag branch only -->\n' % MARKER +
    '            <item\n'
    '                android:id="@+id/action_export_diag_log"\n'
    '                android:title="@string/export_diag_log" />'
)

# --- strings ---
STR_ZH_ANCHOR = '    <string name="locate_selected">定位所选配置</string>'
STR_ZH_INSERT = (
    STR_ZH_ANCHOR + "\n"
    '    <!-- %s: diag branch only -->\n' % MARKER +
    '    <string name="export_diag_log">导出诊断日志</string>'
)
STR_EN_ANCHOR = '    <string name="locate_selected">Locate selected config</string>'
STR_EN_INSERT = (
    STR_EN_ANCHOR + "\n"
    '    <!-- %s: diag branch only -->\n' % MARKER +
    '    <string name="export_diag_log">Export diagnostic logs</string>'
)

# --- Kotlin: when-branch after the update_subscription handler ---
KT_BRANCH_ANCHOR = """            R.id.action_update_subscription -> {
                val group = DataStore.currentGroup()
                if (group.type != GroupType.SUBSCRIPTION) {
                    snackbar(R.string.group_not_subscription).show()
                    Logs.e("onMenuItemClick: Group(${group.displayName()}) is not subscription")
                } else {
                    runOnLifecycleDispatcher {
                        GroupUpdater.startUpdate(group, true)
                    }
                }
            }"""
KT_BRANCH_INSERT = KT_BRANCH_ANCHOR + """
            // %s: diag branch only
            R.id.action_export_diag_log -> {
                exportDiagLog()
            }""" % MARKER

# --- Kotlin: exportDiagLog() before onMenuItemClick ---
# Note: there are two onMenuItemClick in this file (line ~346 main one with
# 4-space indent, and an inner-class one with 12-space indent). Anchor on the
# main one by including its distinctive following lines.
KT_FUNC_ANCHOR = (
    "    override fun onMenuItemClick(item: MenuItem): Boolean {\n"
    "        when (item.itemId) {\n"
    "            R.id.action_scan_qr_code -> {"
)
KT_FUNC_INSERT = '''    // %s: diag branch only, one-click export of SockProtectDiag logs.
    // logcat: app can read its own logs without READ_LOGS. neko.log: best effort.
    private fun exportDiagLog() {
        runOnDefaultDispatcher {
            val sb = StringBuilder()
            var logcatCount = 0
            var nekoCount = 0
            try {
                sb.appendLine("=== SockProtectDiag logcat (app) ===")
                try {
                    val proc = Runtime.getRuntime().exec(arrayOf("logcat", "-d"))
                    proc.inputStream.bufferedReader().forEachLine { line ->
                        if (line.contains("SockProtectDiag")) {
                            sb.appendLine(line)
                            logcatCount++
                        }
                    }
                    proc.waitFor()
                } catch (e: Exception) {
                    sb.appendLine("logcat failed: " + e.message)
                }
                sb.appendLine("--- logcat matched: " + logcatCount + " ---")
                sb.appendLine()
                sb.appendLine("=== SockProtectDiag neko.log (go) ===")
                try {
                    val ctx = requireContext()
                    val cands = listOf(
                        java.io.File(ctx.cacheDir, "neko.log"),
                        java.io.File(ctx.filesDir, "neko.log"),
                        java.io.File(ctx.cacheDir.parent ?: "", "neko.log")
                    )
                    var found: java.io.File? = null
                    for (f in cands) {
                        try {
                            if (f.exists()) {
                                found = f
                                break
                            }
                        } catch (_: Exception) {
                        }
                    }
                    if (found != null) {
                        sb.appendLine("source: " + found.absolutePath)
                        found.bufferedReader().forEachLine { line ->
                            if (line.contains("SockProtectDiag")) {
                                sb.appendLine(line)
                                nekoCount++
                            }
                        }
                    } else {
                        sb.appendLine("neko.log not found")
                    }
                } catch (e: Exception) {
                    sb.appendLine("neko.log read failed: " + e.message)
                }
                sb.appendLine("--- neko.log matched: " + nekoCount + " ---")
                val outDir = requireContext().getExternalFilesDir(null)
                    ?: requireContext().filesDir
                val outFile = java.io.File(outDir, "sockprotect-log.txt")
                outFile.writeText(sb.toString())
                onMainDispatcher {
                    android.widget.Toast.makeText(
                        requireContext(),
                        "诊断日志已导出: " + outFile.absolutePath +
                            " (logcat " + logcatCount + "行, neko.log " + nekoCount + "行)",
                        android.widget.Toast.LENGTH_LONG
                    ).show()
                }
            } catch (e: Exception) {
                onMainDispatcher {
                    android.widget.Toast.makeText(
                        requireContext(),
                        "导出失败: " + e.message,
                        android.widget.Toast.LENGTH_LONG
                    ).show()
                }
            }
        }
    }

''' % MARKER + KT_FUNC_ANCHOR


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _write(path, src):
    with open(path, "w", encoding="utf-8") as f:
        f.write(src)


def _patch_once(path, anchor, insert, what):
    src = _read(path)
    if MARKER in src:
        print(f"{path}: {MARKER} already applied, skip")
        return
    count = src.count(anchor)
    assert count == 1, f"{path}: expected exactly 1 anchor for {what}, found {count}"
    src = src.replace(anchor, insert, 1)
    _write(path, src)
    print(f"{path}: {MARKER} applied OK ({what})")


def patch_menu_xml(root):
    _patch_once(root + "/" + MENU_XML, MENU_ANCHOR, MENU_INSERT, "menu item")


def patch_strings_zh(root):
    _patch_once(root + "/" + STR_ZH, STR_ZH_ANCHOR, STR_ZH_INSERT, "zh string")


def patch_strings_en(root):
    _patch_once(root + "/" + STR_EN, STR_EN_ANCHOR, STR_EN_INSERT, "en string")


def patch_fragment(root):
    path = root + "/" + FRAGMENT_KT
    src = _read(path)
    if MARKER in src:
        print(f"{path}: {MARKER} already applied, skip")
        return
    for anchor, insert, what in [
        (KT_BRANCH_ANCHOR, KT_BRANCH_INSERT, "when branch"),
        (KT_FUNC_ANCHOR, KT_FUNC_INSERT, "exportDiagLog()"),
    ]:
        count = src.count(anchor)
        assert count == 1, f"{path}: expected exactly 1 anchor for {what}, found {count}"
        src = src.replace(anchor, insert, 1)
        print(f"{path}: {what} anchor OK")
    _write(path, src)
    print(f"{path}: {MARKER} applied OK (2 hunks)")


def main():
    patch_menu_xml(".")
    patch_strings_zh(".")
    patch_strings_en(".")
    patch_fragment(".")
    print("ALL DIAG-LOG-EXPORT PATCHES OK")


if __name__ == "__main__":
    main()
