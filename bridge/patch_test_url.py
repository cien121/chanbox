#!/usr/bin/env python3
"""Patch NekoBox Constants.kt: change default connection test URL.

The default http://cp.cloudflare.com/ fails with EOF when tested through
a Cloudflare Worker (the Worker runs inside Cloudflare's network, and
cp.cloudflare.com is a Cloudflare-owned endpoint that doesn't respond
properly to in-network requests).

Change to http://www.msftconnecttest.com/connecttest.txt which returns
HTTP 200 with plain text and works through any proxy.
"""
import sys

TARGET = "app/src/main/java/io/nekohasekai/sagernet/Constants.kt"
MARKER = "testUrlPatchedForCFWorker"

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else TARGET
    with open(path) as f:
        src = f.read()
    if MARKER in src:
        print("Constants.kt test URL already patched, skip")
        return

    old = 'const val CONNECTION_TEST_URL = "http://cp.cloudflare.com/"'
    assert src.count(old) == 1, f"pattern not found: {old!r}"
    new = ('const val CONNECTION_TEST_URL = "http://www.msftconnecttest.com/connecttest.txt"\n'
           f'// {MARKER}: cp.cloudflare.com returns EOF when fetched via Cloudflare Worker')
    src = src.replace(old, new)

    with open(path, "w") as f:
        f.write(src)
    print("Constants.kt test URL patched OK")

if __name__ == "__main__":
    main()
