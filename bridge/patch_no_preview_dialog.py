#!/usr/bin/env python3
"""Patch NekoBox MainActivity.kt: remove the preview version dialog.

The dialog shows on every app start when BuildConfig.FLAVOR == "preview":
    pre-1.4.2-20260202-1
    本应用为预览版，可能存在诸多问题。若您不愿参与测试，请前往GitHub下载正式发布版本！

ChanBox is a personal build; the nag dialog is unwanted. We neuter the
condition instead of deleting the block, keeping the diff minimal and the
patch idempotent.
"""
import sys

TARGET = "app/src/main/java/io/nekohasekai/sagernet/ui/MainActivity.kt"
MARKER = "noPreviewDialogPatched"

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else TARGET
    with open(path) as f:
        src = f.read()
    if MARKER in src:
        print("MainActivity.kt preview dialog already patched, skip")
        return

    old = """        if (isPreview) {
            MaterialAlertDialogBuilder(this)
                .setTitle(BuildConfig.PRE_VERSION_NAME)
                .setMessage(R.string.preview_version_hint)
                .setPositiveButton(android.R.string.ok, null)
                .show()
        }"""
    assert src.count(old) == 1, f"dialog block not found exactly once (found {src.count(old)})"
    new = """        // %s: preview nag dialog disabled for ChanBox personal build
        if (false && isPreview) {
            MaterialAlertDialogBuilder(this)
                .setTitle(BuildConfig.PRE_VERSION_NAME)
                .setMessage(R.string.preview_version_hint)
                .setPositiveButton(android.R.string.ok, null)
                .show()
        }""" % MARKER
    src = src.replace(old, new)

    with open(path, "w") as f:
        f.write(src)
    print("MainActivity.kt preview dialog patched OK")

if __name__ == "__main__":
    main()
