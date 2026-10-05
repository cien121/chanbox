#!/usr/bin/env python3
"""Patch NekoBox ConfigBuilder.kt: migrate DNS config to sing-box 1.14 server format.

sing-box 1.14 removed:
  - top-level dns.fakeip ("legacy DNS fakeip options ... removed in sing-box 1.14.0")
  - typeless servers address="local"/"rcode://..."/"fakeip"/bare IP
    ("legacy DNS server formats ... removed in sing-box 1.14.0")

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
    if "parseDnsServerAddress" in src:
        print("ConfigBuilder.kt DNS 1.14 patch already applied, skip")
        return

    # 1. Helper: parse legacy DNS address into (type, server)
    src = patch(src,
        "fun buildConfig(",
        """// sing-box 1.14: parse legacy DNS address into (type, server) for new server format
private fun parseDnsServerAddress(address: String): Pair<String, String> {
    val addr = address.trim()
    return when {
        addr.startsWith("https://") -> "https" to addr.removePrefix("https://").substringBefore("/").substringBefore(":")
        addr.startsWith("tls://") -> "tls" to addr.removePrefix("tls://").substringBefore("/").substringBefore(":")
        addr.startsWith("tcp://") -> "tcp" to addr.removePrefix("tcp://").substringBefore("/").substringBefore(":")
        addr.startsWith("quic://") -> "quic" to addr.removePrefix("quic://").substringBefore("/").substringBefore(":")
        addr.startsWith("h3://") -> "h3" to addr.removePrefix("h3://").substringBefore("/").substringBefore(":")
        else -> "udp" to addr.substringBefore(":").substringBefore("/")
    }
}

fun buildConfig(""")

    # 2. Remove independent_cache (deprecated in 1.14)
    src = patch(src,
        """        dns = DNSOptions().apply {
            servers = mutableListOf()
            rules = mutableListOf()
            independent_cache = true
        }""",
        """        dns = DNSOptions().apply {
            servers = mutableListOf()
            rules = mutableListOf()
        }""")

    # 3. Remove dns-block server (no rcode server type in 1.14; -2L rules use action=reject)
    src = patch(src,
        """        dns.servers.add(DNSServerOptions().apply {
            address = "rcode://success"
            tag = "dns-block"
        })

""",
        "")

    # 4. dns-local: address="local" -> type="local"
    src = patch(src,
        """        dns.servers.add(DNSServerOptions().apply {
            address = "local"
            tag = "dns-local"
            detour = TAG_DIRECT
        })""",
        """        dns.servers.add(DNSServerOptions().apply {
            type = "local"
            tag = "dns-local"
            detour = TAG_DIRECT
        })""")

    # 5. dns-direct: new format (type/server/domain_resolver; strategy removed in 1.14)
    src = patch(src,
        """        directDNS.firstOrNull().let {
            dns.servers.add(DNSServerOptions().apply {
                address = it ?: throw Exception("No direct DNS, check your settings!")
                tag = "dns-direct"
                detour = TAG_DIRECT
                address_resolver = "dns-local"
                strategy = autoDnsDomainStrategy(SingBoxOptionsUtil.domainStrategy(tag))
            })
        }""",
        """        directDNS.firstOrNull().let {
            val (dnsType, dnsServer) = parseDnsServerAddress(
                it ?: throw Exception("No direct DNS, check your settings!")
            )
            dns.servers.add(DNSServerOptions().apply {
                type = dnsType
                server = dnsServer
                tag = "dns-direct"
                detour = TAG_DIRECT
                domain_resolver = "dns-local"
            })
        }""")

    # 6. dns-remote: new format
    src = patch(src,
        """        remoteDns.firstOrNull().let {
            // Always use direct DNS for urlTest
            if (!forTest) dns.servers.add(DNSServerOptions().apply {
                address = it ?: throw Exception("No remote DNS, check your settings!")
                tag = "dns-remote"
                address_resolver = "dns-direct"
                strategy = autoDnsDomainStrategy(SingBoxOptionsUtil.domainStrategy(tag))
            })
        }""",
        """        remoteDns.firstOrNull().let {
            // Always use direct DNS for urlTest
            if (!forTest) {
                val (dnsType, dnsServer) = parseDnsServerAddress(
                    it ?: throw Exception("No remote DNS, check your settings!")
                )
                dns.servers.add(DNSServerOptions().apply {
                    type = dnsType
                    server = dnsServer
                    tag = "dns-remote"
                    domain_resolver = "dns-direct"
                })
            }
        }""")

    # 7. FakeDNS: drop top-level dns.fakeip, use type=fakeip server
    src = patch(src,
        """            // FakeDNS obj
            if (useFakeDns) {
                dns.fakeip = DNSFakeIPOptions().apply {
                    enabled = true
                    inet4_range = "198.18.0.0/15"
                    inet6_range = "fc00::/18"
                }
                dns.servers.add(DNSServerOptions().apply {
                    address = "fakeip"
                    tag = "dns-fake"
                    strategy = "ipv4_only"
                })""",
        """            // FakeDNS obj
            if (useFakeDns) {
                dns.servers.add(DNSServerOptions().apply {
                    type = "fakeip"
                    tag = "dns-fake"
                    inet4_range = "198.18.0.0/15"
                    inet6_range = "fc00::/18"
                })""")

    # 8. Remove avoid-loopback rule (outbound matcher removed in 1.14;
    #    as a match-all it would shadow user rules and fakeip)
    src = patch(src,
        """            // avoid loopback
            dns.rules.add(0, DNSRule_DefaultOptions().apply {
                outbound = mutableListOf("any")
                server = "dns-direct"
            })
""",
        "")

    # 9. -2L user block rule: server="dns-block" -> action="reject"
    src = patch(src,
        """                    -2L -> {
                        userDNSRuleList += makeDnsRuleObj().apply {
                            server = "dns-block"
                            disable_cache = true
                        }
                    }""",
        """                    -2L -> {
                        userDNSRuleList += makeDnsRuleObj().apply {
                            action = "reject"
                        }
                    }""")

    with open(path, "w") as f:
        f.write(src)
    print("ConfigBuilder.kt DNS 1.14 patch applied OK")

if __name__ == "__main__":
    main()
