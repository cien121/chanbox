#!/usr/bin/env python3
"""Patch NekoBox ConfigBuilder.kt: migrate legacy inbound fields to route rule actions.

sing-box 1.13 removed legacy inbound fields:
  - sniff, sniff_override_destination, sniff_timeout, domain_strategy, udp_disable_domain_unmapping
  ("legacy inbound fields are deprecated in sing-box 1.11.0 and removed in sing-box 1.13.0")

Migration (https://sing-box.sagernet.org/migration/#migrate-legacy-inbound-fields-to-rule-actions):
  - sniff -> route rule {"action": "sniff"}
  - domain_strategy -> route rule {"action": "resolve", "strategy": "..."}
  - sniff_override_destination has no equivalent in 1.13+ (removed upstream); dropped.
    (FakeIP, which NekoBox uses, covers the domain-routing use case.)

NekoBox 5768494 sets these on tun-in and mixed-in inbounds. We remove the fields
and add equivalent route rules (non-final actions, apply to all inbound traffic,
which is exactly what the old per-inbound fields did).

Run from nekobox/ dir (CI). Idempotent: skips if already patched.
"""
import sys

TARGET = "app/src/main/java/io/nekohasekai/sagernet/fmt/ConfigBuilder.kt"

def patch(src, old, new, count=1):
    n = src.count(old)
    assert n == count, f"pattern found {n} times (expected {count}): {old[:80]!r}"
    return src.replace(old, new)

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else TARGET
    with open(path) as f:
        src = f.read()
    if "legacy inbound fields migrated to route rule actions" in src:
        print("ConfigBuilder.kt inbound 1.13 patch already applied, skip")
        return

    # 1. tun-in: remove legacy fields
    src = patch(src,
        """                endpoint_independent_nat = true
                mtu = DataStore.mtu
                domain_strategy = genDomainStrategy(DataStore.resolveDestination)
                sniff = needSniff
                sniff_override_destination = needSniffOverride
                when (ipv6Mode) {""",
        """                endpoint_independent_nat = true
                mtu = DataStore.mtu
                when (ipv6Mode) {""")

    # 2. mixed-in: remove legacy fields
    src = patch(src,
        """                listen = bind
                listen_port = DataStore.mixedPort
                domain_strategy = genDomainStrategy(DataStore.resolveDestination)
                sniff = needSniff
                sniff_override_destination = needSniffOverride
            })""",
        """                listen = bind
                listen_port = DataStore.mixedPort
            })""")

    # 3. Add sniff/resolve route rules (replacing the removed inbound fields).
    #    Placed right after route init, before built-in rules (hijack-dns etc.).
    #    Non-final actions: they don't stop rule evaluation.
    src = patch(src,
        """        // init routing object
        route = RouteOptions().apply {
            auto_detect_interface = true
            rules = mutableListOf()
            rule_set = mutableListOf()
        }
""",
        """        // init routing object
        route = RouteOptions().apply {
            auto_detect_interface = true
            rules = mutableListOf()
            rule_set = mutableListOf()
        }

        // sing-box 1.13+: legacy inbound fields migrated to route rule actions
        // (sniff/sniff_override_destination/domain_strategy removed from inbounds;
        //  sniff_override_destination has no 1.13+ equivalent and is dropped)
        if (!forTest) {
            if (needSniff) {
                route.rules.add(Rule_DefaultOptions().apply {
                    action = "sniff"
                })
            }
            genDomainStrategy(DataStore.resolveDestination).takeIf { it.isNotEmpty() }?.let { resolveStrategy ->
                route.rules.add(Rule_DefaultOptions().apply {
                    action = "resolve"
                    strategy = resolveStrategy
                })
            }
        }
""")

    with open(path, "w") as f:
        f.write(src)
    print("ConfigBuilder.kt inbound 1.13 patch applied OK")

if __name__ == "__main__":
    main()
