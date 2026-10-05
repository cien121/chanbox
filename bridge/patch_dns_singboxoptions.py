#!/usr/bin/env python3
"""Patch NekoBox SingBoxOptions.java: add sing-box 1.14 DNS server/rule fields.

Adds to DNSServerOptions: type, server, domain_resolver, inet4_range, inet6_range
Adds to DNSRule_DefaultOptions: action

Run from nekobox/ dir (CI). Idempotent: skips if already patched.
"""
import sys

TARGET = "app/src/main/java/moe/matsuri/nb4a/SingBoxOptions.java"

def patch(src, old, new, count=1):
    n = src.count(old)
    assert n == count, f"pattern found {n} times (expected {count}): {old[:80]!r}"
    return src.replace(old, new)

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else TARGET
    with open(path) as f:
        src = f.read()
    if "public String domain_resolver;" in src:
        print("SingBoxOptions.java DNS 1.14 patch already applied, skip")
        return

    # 1. DNSServerOptions: add 1.14 fields
    src = patch(src,
        """    public static class DNSServerOptions extends SingBoxOption {

        public String tag;

        public String address;""",
        """    public static class DNSServerOptions extends SingBoxOption {

        public String tag;

        // sing-box 1.14: new DNS server format (legacy address formats removed)
        public String type;

        public String server;

        public String domain_resolver;

        public String inet4_range;

        public String inet6_range;

        public String address;""")

    # 2. DNSRule_DefaultOptions: add action field
    src = patch(src,
        """        public String clash_mode;

        public Boolean invert;

        public String server;

        public Boolean disable_cache;

        public Integer rewrite_ttl;

    }

    public static class V2RayTransportOptions_HTTPOptions""",
        """        public String clash_mode;

        public Boolean invert;

        // sing-box 1.14: DNS rule action (route/reject/predefined/...)
        public String action;

        public String server;

        public Boolean disable_cache;

        public Integer rewrite_ttl;

    }

    public static class V2RayTransportOptions_HTTPOptions""")

    with open(path, "w") as f:
        f.write(src)
    print("SingBoxOptions.java DNS 1.14 patch applied OK")

if __name__ == "__main__":
    main()
