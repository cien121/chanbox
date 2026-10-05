#!/usr/bin/env python3
"""Patch NekoBox SingBoxOptions.java: add `address` field to Inbound_TunOptions.

sing-box 1.10 merged tun's inet4_address/inet6_address into `address`
(removed in 1.12). The Kotlin ConfigBuilder now sets `address`, so the Java
options class needs the field for JSON serialization.

Run from nekobox/ dir (CI). Idempotent: skips if already patched.
"""
import sys

TARGET = "app/src/main/java/moe/matsuri/nb4a/SingBoxOptions.java"
MARKER = "TunAddressMerged110"

def patch(src, old, new, count=1):
    n = src.count(old)
    assert n == count, f"pattern found {n} times (expected {count}): {old[:80]!r}"
    return src.replace(old, new)

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else TARGET
    with open(path) as f:
        src = f.read()
    if MARKER in src:
        print("SingBoxOptions.java tun 1.10 patch already applied, skip")
        return

    # Inbound_TunOptions: add merged `address` field (sing-box 1.10+).
    # Placed right after mtu, before the legacy inet4_address field.
    src = patch(src,
        """    public static class Inbound_TunOptions extends Inbound {

        public String interface_name;

        public Integer mtu;

        // Generate note: Listable
        public List<String> inet4_address;""",
        """    public static class Inbound_TunOptions extends Inbound {

        public String interface_name;

        public Integer mtu;

        // sing-box 1.10+: inet4_address/inet6_address merged into address
        // (legacy fields removed in 1.12). """ + MARKER + """
        // Generate note: Listable
        public List<String> address;

        // Generate note: Listable
        public List<String> inet4_address;""")

    with open(path, "w") as f:
        f.write(src)
    print("SingBoxOptions.java tun 1.10 patch applied OK")

if __name__ == "__main__":
    main()
