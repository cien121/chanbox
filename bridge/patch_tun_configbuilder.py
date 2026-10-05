#!/usr/bin/env python3
"""Patch NekoBox ConfigBuilder.kt: migrate legacy tun address fields to sing-box 1.10+ format.

sing-box 1.10 merged inet4_address/inet6_address into `address`
(also inet4/6_route_address -> route_address, inet4/6_route_exclude_address ->
route_exclude_address). The legacy fields were removed in 1.12, and setting them
now fails at startup:
  "create service: initialize inbound[0] tun[tun-in]: legacy tun address fields
   are deprecated in sing-box 1.10.0 and removed in sing-box 1.12.0"

NekoBox 5768494 sets inet4_address/inet6_address on the tun-in inbound based on
ipv6Mode. We replace them with the merged `address` field.

Migration ref: https://sing-box.sagernet.org/migration/ ("TUN address fields are merged")

Run from nekobox/ dir (CI). Idempotent: skips if already patched.
"""
import sys

TARGET = "app/src/main/java/io/nekohasekai/sagernet/fmt/ConfigBuilder.kt"
MARKER = "tun address fields merged into address (sing-box 1.10+)"

def patch(src, old, new, count=1):
    n = src.count(old)
    assert n == count, f"pattern found {n} times (expected {count}): {old[:80]!r}"
    return src.replace(old, new)

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else TARGET
    with open(path) as f:
        src = f.read()
    if MARKER in src:
        print("ConfigBuilder.kt tun 1.10 patch already applied, skip")
        return

    # tun-in: replace inet4_address/inet6_address with merged `address` field.
    # Matches the when (ipv6Mode) block inside Inbound_TunOptions().apply { ... }.
    # (The inbound 1.13 patch already removed sniff/domain_strategy lines above this
    # block, so we anchor only on the when-block which it did not touch.)
    src = patch(src,
        """                when (ipv6Mode) {
                    IPv6Mode.DISABLE -> {
                        inet4_address = listOf(VpnService.PRIVATE_VLAN4_CLIENT + "/28")
                    }

                    IPv6Mode.ONLY -> {
                        inet6_address = listOf(VpnService.PRIVATE_VLAN6_CLIENT + "/126")
                    }

                    else -> {
                        inet4_address = listOf(VpnService.PRIVATE_VLAN4_CLIENT + "/28")
                        inet6_address = listOf(VpnService.PRIVATE_VLAN6_CLIENT + "/126")
                    }
                }""",
        """                // """ + MARKER + """
                // (inet4_address/inet6_address removed in sing-box 1.12)
                when (ipv6Mode) {
                    IPv6Mode.DISABLE -> {
                        address = listOf(VpnService.PRIVATE_VLAN4_CLIENT + "/28")
                    }

                    IPv6Mode.ONLY -> {
                        address = listOf(VpnService.PRIVATE_VLAN6_CLIENT + "/126")
                    }

                    else -> {
                        address = listOf(
                            VpnService.PRIVATE_VLAN4_CLIENT + "/28",
                            VpnService.PRIVATE_VLAN6_CLIENT + "/126"
                        )
                    }
                }""")

    with open(path, "w") as f:
        f.write(src)
    print("ConfigBuilder.kt tun 1.10 patch applied OK")

if __name__ == "__main__":
    main()
