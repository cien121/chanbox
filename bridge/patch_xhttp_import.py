#!/usr/bin/env python3
"""Add missing v2rayxhttp import to sing-box-lx transport/v2ray package.

sing-box-lx v1.14.2-lx.11 ships transport/v2rayxhttp/register.go with
`//go:build with_xhttp` and an init() that calls v2ray.RegisterClient(),
but NOTHING imports the v2rayxhttp package, so the init() never runs.
The libcore build uses -tags with_xhttp, so at runtime:
  create client transport: xhttp: unknown transport type: xhttp

Compare with the working pattern: transport/v2ray/grpc.go has
`//go:build with_grpc` and imports v2raygrpc / v2raygrpclite.

This script creates transport/v2ray/xhttp.go in the sing-box-lx clone:
  //go:build with_xhttp

  package v2ray

  import _ "github.com/sagernet/sing-box/transport/v2rayxhttp"

Run from nekobox/ dir (CI); SING_BOX_DIR defaults to ../sing-box.
Idempotent: skips when the file already has the expected content.
"""
import os
import sys

SING_BOX_DIR = sys.argv[1] if len(sys.argv) > 1 else "../sing-box"

EXPECTED = """//go:build with_xhttp

package v2ray

import _ "github.com/sagernet/sing-box/transport/v2rayxhttp"
"""


def main():
    target = os.path.join(SING_BOX_DIR, "transport", "v2ray", "xhttp.go")
    if not os.path.isdir(os.path.join(SING_BOX_DIR, "transport", "v2rayxhttp")):
        print(f"ERROR: {SING_BOX_DIR}/transport/v2rayxhttp not found, "
              "is sing-box-lx cloned?", file=sys.stderr)
        sys.exit(1)
    if os.path.isfile(target):
        with open(target) as f:
            if f.read() == EXPECTED:
                print("transport/v2ray/xhttp.go already correct, skip")
                return
        print(f"WARNING: {target} exists with unexpected content, overwriting")
    with open(target, "w") as f:
        f.write(EXPECTED)
    print(f"created {target}")


if __name__ == "__main__":
    main()
