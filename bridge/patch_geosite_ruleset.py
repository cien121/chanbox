#!/usr/bin/env python3
"""ChanBox: bundle geosite categories as .srs rule-sets, fix rule_set crash.

Root cause of the crash (service fails to start):
  NekoBox's SingBoxOptionsUtil.kt converts `geosite:xxx` in route rules into
  `rule_set` references, and generateRuleSet() creates RuleSet entries with
  `path = "geosite:xxx"`. sing-box 1.14 tries to open that as a local binary
  rule-set file -> "open .../geosite:category-ads-all: no such file or
  directory", and the whole service fails to initialize.

  The `geosite`/`geoip` fields on route rules are NOT a valid alternative:
  sing-box 1.14 explicitly errors with "geosite database is deprecated in
  sing-box 1.8.0 and removed in sing-box 1.12.0".

Fix:
  1. Build time (this script, runs in CI): download sing-box + geosite.db,
     export the categories used by ChanBox default routes
     (category-ads-all, google, private) via `sing-box geosite export`,
     compile to binary .srs via `sing-box rule-set compile`, and place
     them in app/src/main/assets/srs/ so they're bundled in the APK.
  2. Patch generateRuleSet() in SingBoxOptionsUtil.kt: for `geosite:<cat>`
     where we have a bundled .srs, copy it from assets to the sing-box
     working dir (no_backup/srs/) on first use and set the absolute path.
     Unknown geosite:/geoip: entries are skipped (instead of creating
     broken RuleSets that crash the service).

Idempotent: checks marker before patching.
"""
import os
import subprocess
import sys
import urllib.request

MARKER = "// [chanbox] bundled geosite srs"

CATEGORIES = ["category-ads-all", "google", "private"]

SINGBOX_VERSION = "v1.14.0"
SINGBOX_URL = (
    "https://github.com/SagerNet/sing-box/releases/download/"
    f"{SINGBOX_VERSION}/sing-box-{SINGBOX_VERSION[1:]}-linux-amd64.tar.gz"
)
GEOSITE_DB_URL = (
    "https://github.com/soffchen/sing-geosite/releases/latest/download/geosite.db"
)

WORK_DIR = "/tmp/geosite_srs"
ASSETS_DIR = "app/src/main/assets/srs"
UTIL_PATH = "app/src/main/java/moe/matsuri/nb4a/SingBoxOptionsUtil.kt"


def download(url, dest):
    print(f"  downloading {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "ChanBox-CI"})
    with urllib.request.urlopen(req, timeout=180) as r, open(dest, "wb") as f:
        while True:
            chunk = r.read(65536)
            if not chunk:
                break
            f.write(chunk)


def run(cmd, **kwargs):
    subprocess.run(cmd, check=True, **kwargs)


def main():
    with open(UTIL_PATH, "r", encoding="utf-8") as f:
        util = f.read()
    if MARKER in util:
        print(">>> [geosrs] already applied, skip")
        return 0

    os.makedirs(WORK_DIR, exist_ok=True)
    os.makedirs(ASSETS_DIR, exist_ok=True)

    # 1. sing-box binary
    singbox_bin = os.path.join(WORK_DIR, "sing-box")
    have_tools = True
    if not os.path.exists(singbox_bin):
        try:
            tgz = os.path.join(WORK_DIR, "sing-box.tgz")
            download(SINGBOX_URL, tgz)
            run(["tar", "xzf", tgz, "-C", WORK_DIR])
            for root, _, files in os.walk(WORK_DIR):
                if "sing-box" in files:
                    cand = os.path.join(root, "sing-box")
                    if cand != singbox_bin and os.path.isfile(cand):
                        # make sure it's the binary, not the tgz dir
                        try:
                            run([cand, "version"], capture_output=True)
                            os.rename(cand, singbox_bin)
                            break
                        except Exception:
                            continue
            os.chmod(singbox_bin, 0o755)
        except Exception as e:
            print(f"  WARNING: sing-box download failed: {e}")

    # 2. geosite.db
    db_path = os.path.join(WORK_DIR, "geosite.db")
    if not os.path.exists(db_path):
        try:
            download(GEOSITE_DB_URL, db_path)
        except Exception as e:
            print(f"  WARNING: geosite.db download failed: {e}")

    have_tools = os.path.exists(singbox_bin) and os.path.exists(db_path)
    if not have_tools:
        print("  WARNING: cannot generate .srs files (network issue);")
        print("  Kotlin patch will still be applied (rules degrade gracefully).")

    # 3. Export + compile each category, place .srs in assets
    for cat in CATEGORIES:
        srs_name = f"geosite-{cat}.srs"
        dest = os.path.join(ASSETS_DIR, srs_name)
        if os.path.exists(dest):
            print(f"  {srs_name} already exists, skip")
            continue
        if not have_tools:
            print(f"  SKIP {srs_name} (no tools)")
            continue
        json_path = os.path.join(WORK_DIR, f"geosite-{cat}.json")
        srs_path = os.path.join(WORK_DIR, srs_name)
        run([singbox_bin, "geosite", "-f", db_path, "export", cat,
             "-o", json_path], cwd=WORK_DIR)
        run([singbox_bin, "rule-set", "compile", json_path, "-o", srs_path],
            cwd=WORK_DIR)
        # copy to assets
        with open(srs_path, "rb") as src, open(dest, "wb") as dst:
            dst.write(src.read())
        size = os.path.getsize(dest)
        print(f">>> [geosrs] bundled {srs_name} ({size} bytes)")

    # 4. Patch generateRuleSet() in SingBoxOptionsUtil.kt
    old_block = """fun generateRuleSet(ruleSetString: List<String>, ruleSet: MutableList<RuleSet>) {
    ruleSetString.forEach {
        when {
            it.startsWith("geoip:") -> {
                ruleSet.add(RuleSet().apply {
                    type = "local"
                    tag = it
                    format = "binary"
                    path = it
                })
            }

            it.startsWith("geosite:") -> {
                ruleSet.add(RuleSet().apply {
                    type = "local"
                    tag = it
                    format = "binary"
                    path = it
                })
            }
        }
    }
}"""

    new_block = """// [chanbox] bundled geosite srs
private val bundledGeositeSrs = setOf("category-ads-all", "google", "private")

// [chanbox] bundled geosite srs
private fun ensureBundledSrs(category: String): String? {
    return try {
        val app = io.nekohasekai.sagernet.SagerNet.application
        // sing-box working dir is no_backup; use absolute path so it resolves
        val dir = java.io.File(app.noBackupFilesDir, "srs")
        if (!dir.exists()) dir.mkdirs()
        val dst = java.io.File(dir, "geosite-" + category + ".srs")
        if (!dst.exists()) {
            app.assets.open("srs/geosite-" + category + ".srs").use { inp ->
                dst.outputStream().use { out -> inp.copyTo(out) }
            }
        }
        dst.absolutePath
    } catch (e: Exception) {
        null
    }
}

fun generateRuleSet(ruleSetString: List<String>, ruleSet: MutableList<RuleSet>) {
    ruleSetString.forEach {
        when {
            it.startsWith("geoip:") -> {
                // [chanbox] bundled geosite srs: geoip: has no bundled srs;
                // skip instead of creating a broken local path that crashes
                // the service. (geoip:private is handled via ip_is_private.)
            }

            it.startsWith("geosite:") -> {
                // [chanbox] bundled geosite srs
                val category = it.removePrefix("geosite:")
                val srsPath = if (category in bundledGeositeSrs) ensureBundledSrs(category) else null
                if (srsPath != null) {
                    ruleSet.add(RuleSet().apply {
                        type = "local"
                        tag = it
                        format = "binary"
                        path = srsPath
                    })
                }
                // unknown categories are skipped: a broken path would crash
                // service init, which is worse than the rule not matching.
            }
        }
    }
}"""

    if old_block not in util:
        print("ERROR: generateRuleSet block not found in SingBoxOptionsUtil.kt")
        return 1
    util = util.replace(old_block, new_block, 1)

    with open(UTIL_PATH, "w", encoding="utf-8") as f:
        f.write(util)
    print(">>> [geosrs] SingBoxOptionsUtil.kt patched OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
