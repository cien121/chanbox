#!/usr/bin/env python3
"""Harden #117 hop-ports outbound logic (follow-up to #119).

Why #119 still times out (analysis 2026-10-07):
- Verified: #119 APK contains the null-safety fix; libgojni.so is
  byte-identical to #116; per-profile URL tests are isolated
  (ConfigurationFragment.urlTest catches per-profile exceptions), so the
  old "NPE kills the whole batch" theory is wrong.
- Verified against sing-box-lx source: when server_ports is set,
  server_port is ignored for dialing (NewHopConn picks a random hop port),
  so the forced server_port alone does not break hopping.
- Real bugs left in the #117 logic:
  1. `server_port = bean.serverPorts.toIntOrNull() ?: 443` fabricates port
     443 when the "port" field is not a plain number.
  2. No whitespace trimming anywhere. sing-box's ParsePorts does
     `strconv.ParseUint` WITHOUT trimming, so a user-typed
     "20000 - 21000" (spaces, very natural on a phone keyboard) passes the
     Kotlin filter as "20000 : 21000" and then makes NewClient fail ->
     outbound creation error -> timeout.
  3. If hopPorts is non-blank but unparseable (garbage), server_ports is
     left unset while server_port was already forced -> dials wrong port.

Fix (idempotent, marker hy2HopFieldHarden), HysteriaFmt.kt only:
1. Hy1/Hy2 branches: trim hopPorts/serverPorts; drop the `?: 443`
   fabrication (only set server_port when the port field is a valid single
   port); if hopPorts parses to empty, fall back to the legacy serverPorts
   logic instead of leaving a half-configured outbound.
2. hopPortsToSingboxList: trim each comma-separated segment so
   "20000-21000, 30000-31000" works.
"""

MARKER = "hy2HopFieldHarden"

FMT_KT = "app/src/main/java/io/nekohasekai/sagernet/fmt/hysteria/HysteriaFmt.kt"


def read(p):
    with open(p, "r", encoding="utf-8") as f:
        return f.read()


def write(p, c):
    with open(p, "w", encoding="utf-8") as f:
        f.write(c)


def patch_fmt():
    c = read(FMT_KT)
    if MARKER in c:
        print("  [skip] HysteriaFmt.kt already hardened")
        return

    # 1+2. Hy1/Hy2 branches: identical text (post-#119), replace both.
    old = """            // hy2HopField: independent hop-ports field; legacy serverPorts range still honored
            // hy2HopFieldFix: null-safe (hopPorts is Java platform type)
            val hopPortsSafe = bean.hopPorts ?: ""
            if (hopPortsSafe.isNotBlank()) {
                server_port = bean.serverPorts.toIntOrNull() ?: 443
                val hops = hopPortsToSingboxList(hopPortsSafe)
                if (hops.isNotEmpty()) server_ports = hops
            } else {
                val port = bean.serverPorts.toIntOrNull()
                if (port != null) {
                    server_port = port
                } else {
                    server_ports = hopPortsToSingboxList(bean.serverPorts)
                }
            }"""
    new = """            // hy2HopField: independent hop-ports field; legacy serverPorts range still honored
            // hy2HopFieldFix: null-safe (hopPorts is Java platform type)
            // hy2HopFieldHarden: trim whitespace; never fabricate server_port;
            // unparseable hopPorts falls back to legacy serverPorts logic
            val hopPortsSafe = (bean.hopPorts ?: "").trim()
            val serverPortsSafe = (bean.serverPorts ?: "").trim()
            val hops = if (hopPortsSafe.isNotBlank()) hopPortsToSingboxList(hopPortsSafe) else emptyList()
            if (hops.isNotEmpty()) {
                serverPortsSafe.toIntOrNull()?.let { server_port = it }
                server_ports = hops
            } else {
                val port = serverPortsSafe.toIntOrNull()
                if (port != null) {
                    server_port = port
                } else {
                    server_ports = hopPortsToSingboxList(serverPortsSafe)
                }
            }"""
    count = c.count(old)
    assert count == 2, f"Hy1/Hy2 harden anchor: expected 2, found {count}"
    c = c.replace(old, new)

    # 3. hopPortsToSingboxList: trim each segment.
    old = """fun hopPortsToSingboxList(s: String): List<String> {
    return s.split(",").mapNotNull {
        val pRange = it.replace("-", ":")
        if (pRange.split(":").size == 2) {
            pRange
        } else {
            null
        }
    }
}"""
    new = """fun hopPortsToSingboxList(s: String): List<String> {
    return s.split(",").mapNotNull {
        // hy2HopFieldHarden: trim each segment ("20000 - 21000" must work;
        // sing-box ParsePorts does not trim and would fail the outbound)
        val pRange = it.trim().replace("-", ":")
        if (pRange.split(":").size == 2) {
            pRange
        } else {
            null
        }
    }
}"""
    assert c.count(old) == 1, "hopPortsToSingboxList anchor not found/ambiguous"
    c = c.replace(old, new, 1)

    assert MARKER in c, "marker not found after patch"
    write(FMT_KT, c)
    print("  [ok] HysteriaFmt.kt: hop-ports logic hardened")


def main():
    print(">>> patch_hy2_hopfield_harden: trim + no fabricated server_port + garbage fallback")
    patch_fmt()
    print(">>> done")


if __name__ == "__main__":
    main()
