#!/usr/bin/env python3
"""Patch NekoBox SingBoxOptions.java: add strategy field to Rule_DefaultOptions.

Needed for the sing-box 1.13+ migration of legacy inbound domain_strategy
to route rule action: {"action": "resolve", "strategy": "..."}.

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
    if "RouteActionResolve strategy" in src:
        print("SingBoxOptions.java inbound 1.13 patch already applied, skip")
        return

    # Rule_DefaultOptions: add strategy field for {"action":"resolve","strategy":...}
    src = patch(src,
        """        public String clash_mode;

        public Boolean invert;

        public String action;

        public String outbound;

    }

    public static class DNSRule_DefaultOptions extends DNSRule {""",
        """        public String clash_mode;

        public Boolean invert;

        public String action;

        // sing-box 1.13+: resolve rule action strategy (migrated from inbound domain_strategy)
        // RouteActionResolve strategy
        public String strategy;

        public String outbound;

    }

    public static class DNSRule_DefaultOptions extends DNSRule {""")

    with open(path, "w") as f:
        f.write(src)
    print("SingBoxOptions.java inbound 1.13 patch applied OK")

if __name__ == "__main__":
    main()
