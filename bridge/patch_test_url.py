#!/usr/bin/env python3
"""Patch NekoBox Constants.kt: change default connection test URL.

v1: http://cp.cloudflare.com/ -> https://www.gstatic.com/generate_204
    (cp.cloudflare.com returns EOF when fetched via Cloudflare Worker)

v2: https://www.gstatic.com/generate_204 -> https://www.baidu.com
    (gstatic times out on China Unicom; Baidu is the most reliable
    endpoint inside China with global CDN, reachable through any proxy)

v3: https://www.baidu.com -> https://www.gstatic.com/generate_204
    (user explicitly requires gstatic, no Baidu)
"""
import sys

TARGET = "app/src/main/java/io/nekohasekai/sagernet/Constants.kt"
MARKER_V1 = "testUrlPatchedForCFWorker"
MARKER_V2 = "testUrlPatchedForChina"
MARKER_V3 = "testUrlGstaticFinal"
NEW_URL = "https://www.gstatic.com/generate_204"

OLD_ORIG = 'const val CONNECTION_TEST_URL = "http://cp.cloudflare.com/"'
OLD_BAIDU = 'const val CONNECTION_TEST_URL = "https://www.baidu.com"'
OLD_GSTATIC = f'const val CONNECTION_TEST_URL = "{NEW_URL}"'

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else TARGET
    with open(path) as f:
        src = f.read()
    if MARKER_V3 in src:
        print("Constants.kt test URL already set to gstatic (v3), skip")
        return

    new_line = (f'const val CONNECTION_TEST_URL = "{NEW_URL}"\n'
                f'// {MARKER_V3}: user requires gstatic, no Baidu')

    if src.count(OLD_BAIDU) == 1:
        # v2 applied: baidu -> gstatic
        src = src.replace(OLD_BAIDU, new_line)
        print("Constants.kt test URL changed baidu -> gstatic OK")
    elif src.count(OLD_GSTATIC) == 1:
        # v1 applied or already gstatic: just tag marker
        src = src.replace(
            OLD_GSTATIC,
            new_line,
            1)
        print("Constants.kt test URL already gstatic, marker added OK")
    elif src.count(OLD_ORIG) == 1:
        # fresh checkout: original -> gstatic directly
        src = src.replace(
            OLD_ORIG,
            new_line + f'\n// {MARKER_V1}: cp.cloudflare.com returns EOF when fetched via Cloudflare Worker')
        print("Constants.kt test URL patched cp.cloudflare.com -> gstatic OK")
    elif NEW_URL in src and "CONNECTION_TEST_URL" in src:
        print("Constants.kt test URL already gstatic (marker missing), skip")
        return
    else:
        raise AssertionError("CONNECTION_TEST_URL not found in expected forms")

    with open(path, "w") as f:
        f.write(src)

if __name__ == "__main__":
    main()
