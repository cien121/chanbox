#!/usr/bin/env python3
"""Patch NekoBox Constants.kt: change default connection test URL.

v1: http://cp.cloudflare.com/ -> https://www.gstatic.com/generate_204
    (cp.cloudflare.com returns EOF when fetched via Cloudflare Worker)

v2: https://www.gstatic.com/generate_204 -> https://www.baidu.com
    (gstatic times out on China Unicom; Baidu is the most reliable
    endpoint inside China with global CDN, reachable through any proxy)
"""
import sys

TARGET = "app/src/main/java/io/nekohasekai/sagernet/Constants.kt"
MARKER_V1 = "testUrlPatchedForCFWorker"
MARKER_V2 = "testUrlPatchedForChina"
NEW_URL = "https://www.baidu.com"

OLD_ORIG = 'const val CONNECTION_TEST_URL = "http://cp.cloudflare.com/"'
OLD_GSTATIC = 'const val CONNECTION_TEST_URL = "https://www.gstatic.com/generate_204"'

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else TARGET
    with open(path) as f:
        src = f.read()
    if MARKER_V2 in src:
        print("Constants.kt test URL already patched for China, skip")
        return

    new_line = (f'const val CONNECTION_TEST_URL = "{NEW_URL}"\n'
                f'// {MARKER_V2}: gstatic times out on China Unicom, Baidu is most reliable in China')

    if src.count(OLD_GSTATIC) == 1:
        # v1 already applied: upgrade gstatic -> baidu
        src = src.replace(OLD_GSTATIC, new_line)
        print("Constants.kt test URL upgraded gstatic -> baidu OK")
    elif src.count(OLD_ORIG) == 1:
        # fresh checkout: original -> baidu directly
        src = src.replace(
            OLD_ORIG,
            new_line + f'\n// {MARKER_V1}: cp.cloudflare.com returns EOF when fetched via Cloudflare Worker')
        print("Constants.kt test URL patched cp.cloudflare.com -> baidu OK")
    elif NEW_URL in src and "CONNECTION_TEST_URL" in src:
        print("Constants.kt test URL already set to baidu (marker missing), skip")
        return
    else:
        raise AssertionError("CONNECTION_TEST_URL not found in expected forms")

    with open(path, "w") as f:
        f.write(src)

if __name__ == "__main__":
    main()
