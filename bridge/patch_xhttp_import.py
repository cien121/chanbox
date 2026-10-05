#!/usr/bin/env python3
"""Add missing v2rayxhttp import for the with_xhttp build tag.

sing-box-lx v1.14.2-lx.11 ships transport/v2rayxhttp/register.go with
`//go:build with_xhttp` and an init() that calls v2ray.RegisterClient(),
but NOTHING imports the v2rayxhttp package, so the init() never runs.
At runtime:
  create client transport: xhttp: unknown transport type: xhttp

IMPORTANT (learned from build #48): the blank import must NOT live inside
package transport/v2ray (e.g. transport/v2ray/xhttp.go), because
v2rayxhttp/register.go itself imports transport/v2ray ->
  "imports github.com/sagernet/sing-box/transport/v2ray from register.go:
   import cycle not allowed"
The safe place is the top-level libcore package, which nothing inside
sing-box imports back: gobind -> libcore -> v2rayxhttp -> v2ray (no cycle).

This script creates libcore/xhttp_import.go:
  //go:build with_xhttp

  package libcore

  import _ "github.com/sagernet/sing-box/transport/v2rayxhttp"

Usage: patch_xhttp_import.py <singbox_dir> <libcore_dir>
Run from nekobox/ dir (CI): python3 patch_xhttp_import.py ../sing-box libcore
Idempotent: skips when the file already has the expected content; also
removes the stale transport/v2ray/xhttp.go left by the broken #48 attempt.
"""
import os
import sys

SING_BOX_DIR = sys.argv[1] if len(sys.argv) > 1 else "../sing-box"
LIBCORE_DIR = sys.argv[2] if len(sys.argv) > 2 else "libcore"

EXPECTED = """//go:build with_xhttp

package libcore

import _ "github.com/sagernet/sing-box/transport/v2rayxhttp"
"""


def main():
    if not os.path.isdir(os.path.join(SING_BOX_DIR, "transport", "v2rayxhttp")):
        print(f"ERROR: {SING_BOX_DIR}/transport/v2rayxhttp not found, "
              "is sing-box-lx cloned?", file=sys.stderr)
        sys.exit(1)
    if not os.path.isdir(LIBCORE_DIR):
        print(f"ERROR: {LIBCORE_DIR} not found (run from nekobox/ dir)",
              file=sys.stderr)
        sys.exit(1)
    # Clean up the broken #48 attempt: blank import inside package
    # transport/v2ray causes an import cycle (v2rayxhttp -> v2ray).
    stale = os.path.join(SING_BOX_DIR, "transport", "v2ray", "xhttp.go")
    if os.path.isfile(stale):
        os.remove(stale)
        print(f"removed stale {stale} (import-cycle file from broken #48 fix)")
    target = os.path.join(LIBCORE_DIR, "xhttp_import.go")
    if os.path.isfile(target):
        with open(target) as f:
            if f.read() == EXPECTED:
                print(f"{target} already correct, skip")
                return
        print(f"WARNING: {target} exists with unexpected content, overwriting")
    with open(target, "w") as f:
        f.write(EXPECTED)
    print(f"created {target}")


if __name__ == "__main__":
    main()
