#!/usr/bin/env python3
"""Patch NekoBox ConfigBuilder.kt: drop detour=TAG_DIRECT from DNS servers.

sing-box 1.14 hard-fails at startup (common/dialer/detour.go) when a DNS
server explicitly detours to a "direct" outbound whose DialerOptions are all
defaults ("empty"):
  start dns/https[dns-direct]: detour to an empty direct outbound makes no sense

NekoBox always generates an empty direct outbound (tag+type only, see the
`for (freedom in arrayOf(TAG_DIRECT, TAG_BYPASS))` block) while dns-local and
dns-direct set detour=TAG_DIRECT. The detour is pointless anyway: without it
the DNS server uses a plain direct dialer, functionally identical to detouring
through an empty direct outbound (which is exactly why sing-box rejects it).

This is NOT caused by the earlier DNS 1.14 format patch: the original NekoBox
code already had detour=TAG_DIRECT; the failure was just masked before by the
decode-stage errors (#39/#42/#45 fixed those, exposing this start-stage check).

Run from nekobox/ dir (CI), AFTER patch_dns_configbuilder.py. Idempotent.
"""
import sys

TARGET = "app/src/main/java/io/nekohasekai/sagernet/fmt/ConfigBuilder.kt"
MARKER = "dnsDetour114Removed"

def patch(src, old, new, count=1):
    n = src.count(old)
    assert n == count, f"pattern found {n} times (expected {count}): {old[:80]!r}"
    return src.replace(old, new)

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else TARGET
    with open(path) as f:
        src = f.read()
    if MARKER in src:
        print("ConfigBuilder.kt DNS detour patch already applied, skip")
        return

    # dns-local: drop detour (local transport resolves via system, never
    # initializes the detour dialer; keeping it is harmless but pointless,
    # and dropping it keeps both servers consistent)
    src = patch(src,
        """        dns.servers.add(DNSServerOptions().apply {
            type = "local"
            tag = "dns-local"
            detour = TAG_DIRECT
        })""",
        """        dns.servers.add(DNSServerOptions().apply {
            type = "local"
            tag = "dns-local"
            // """ + MARKER + """: sing-box 1.14 rejects detour to an empty
            // direct outbound ("detour to an empty direct outbound makes no
            // sense"); without detour the server dials direct anyway.
        })""")

    # dns-direct: drop detour (plain direct dialer is equivalent to detouring
    # through NekoBox's empty direct outbound)
    src = patch(src,
        """            dns.servers.add(DNSServerOptions().apply {
                type = dnsType
                server = dnsServer
                tag = "dns-direct"
                detour = TAG_DIRECT
                domain_resolver = "dns-local"
            })""",
        """            dns.servers.add(DNSServerOptions().apply {
                type = dnsType
                server = dnsServer
                tag = "dns-direct"
                // """ + MARKER + """: sing-box 1.14 rejects detour to an empty
                // direct outbound ("detour to an empty direct outbound makes no
                // sense"); without detour the server dials direct anyway.
                domain_resolver = "dns-local"
            })""")

    with open(path, "w") as f:
        f.write(src)
    print("ConfigBuilder.kt DNS detour patch applied OK")

if __name__ == "__main__":
    main()
