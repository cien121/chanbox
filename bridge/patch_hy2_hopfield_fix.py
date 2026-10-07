#!/usr/bin/env python3
"""Fix #117 regression: make hopPorts null-safe.

Root cause: hopPorts is declared in HysteriaBean.java (Java String).
In Kotlin (HysteriaFmt.kt) it's a platform type String!. If hopPorts is
null at runtime (e.g., bean created without initializeDefaultValues(),
or deserialize edge case), then:
  - bean.hopPorts.isNotBlank()  -> NPE
  - hopPorts.ifBlank { ... }    -> NPE (in toUri())
The NPE in buildSingBoxOutboundHysteriaBean crashes the latency test,
and since the test iterates profiles, ALL nodes appear broken.

Fix (idempotent, marker hy2HopFieldFix):
1. HysteriaFmt.kt:
   - Replace `bean.hopPorts.isNotBlank()` with `!bean.hopPorts.isNullOrBlank()`
   - Replace `bean.hopPorts` usages with safe fallback
   - In toUri(): `val mportSrc = hopPorts.ifBlank { serverPorts }`
     -> `val mportSrc = hopPorts?.ifBlank { serverPorts } ?: serverPorts`
     Actually simpler: `(hopPorts ?: "").ifBlank { serverPorts }`
2. HysteriaBean.java:
   - In deserialize, after reading, ensure non-null:
     `if (hopPorts == null) hopPorts = "";`
   - In initializeDefaultValues, already has null check (from v1 patch).
"""

import re

MARKER = "hy2HopFieldFix"

FMT_KT = "app/src/main/java/io/nekohasekai/sagernet/fmt/hysteria/HysteriaFmt.kt"
BEAN = "app/src/main/java/io/nekohasekai/sagernet/fmt/hysteria/HysteriaBean.java"


def read(p):
    with open(p, "r", encoding="utf-8") as f:
        return f.read()


def write(p, c):
    with open(p, "w", encoding="utf-8") as f:
        f.write(c)


def patch_fmt():
    c = read(FMT_KT)
    if MARKER in c:
        print("  [skip] HysteriaFmt.kt already fixed")
        return

    # 1. Hy1 branch: null-safe hopPorts check
    old = """            // hy2HopField: independent hop-ports field; legacy serverPorts range still honored
            if (bean.hopPorts.isNotBlank()) {
                server_port = bean.serverPorts.toIntOrNull() ?: 443
                val hops = hopPortsToSingboxList(bean.hopPorts)
                if (hops.isNotEmpty()) server_ports = hops"""
    new = """            // hy2HopField: independent hop-ports field; legacy serverPorts range still honored
            // hy2HopFieldFix: null-safe (hopPorts is Java platform type)
            val hopPortsSafe = bean.hopPorts ?: ""
            if (hopPortsSafe.isNotBlank()) {
                server_port = bean.serverPorts.toIntOrNull() ?: 443
                val hops = hopPortsToSingboxList(hopPortsSafe)
                if (hops.isNotEmpty()) server_ports = hops"""
    count = c.count(old)
    assert count == 1, f"Hy1 null-safe anchor: expected 1, found {count}"
    c = c.replace(old, new, 1)

    # 2. Hy2 branch: null-safe hopPorts check
    old = """            // hy2HopField: independent hop-ports field; legacy serverPorts range still honored
            if (bean.hopPorts.isNotBlank()) {
                server_port = bean.serverPorts.toIntOrNull() ?: 443
                val hops = hopPortsToSingboxList(bean.hopPorts)
                if (hops.isNotEmpty()) server_ports = hops"""
    # After Hy1 replacement, there should be 1 remaining (Hy2)
    count = c.count(old)
    assert count == 1, f"Hy2 null-safe anchor: expected 1, found {count}"
    c = c.replace(old, new, 1)

    # 3. toUri(): null-safe mportSrc
    old = """    // hy2HopField: export hop range via mport
    val mportSrc = hopPorts.ifBlank { serverPorts }"""
    new = """    // hy2HopField: export hop range via mport
    // hy2HopFieldFix: null-safe (hopPorts is Java platform type)
    val mportSrc = (hopPorts ?: "").ifBlank { serverPorts }"""
    assert c.count(old) == 1, "toUri null-safe anchor not found"
    c = c.replace(old, new, 1)

    # Add marker comment at top of file (after package/imports, before first fun)
    # Simpler: append marker to the hy2HopFieldFix comment we already added
    # The marker is in the comments above, so check passes next time.
    # Ensure MARKER string appears: it's in "hy2HopFieldFix" comments.
    assert MARKER in c, "marker not found after patch"
    write(FMT_KT, c)
    print("  [ok] HysteriaFmt.kt: hopPorts null-safe")


def patch_bean():
    c = read(BEAN)
    if MARKER in c:
        print("  [skip] HysteriaBean.java already fixed")
        return
    # In deserialize, after the version>=9 block, add null guard.
    old = """        if (version >= 9) { // hy2HopField
            hopPorts = input.readString();
        } else {
            hopPorts = "";
        }
    }"""
    new = """        if (version >= 9) { // hy2HopField
            hopPorts = input.readString();
        } else {
            hopPorts = "";
        }
        if (hopPorts == null) hopPorts = ""; // hy2HopFieldFix: guard against null from parcel
    }"""
    assert c.count(old) == 1, "bean deserialize null-guard anchor not found"
    c = c.replace(old, new, 1)
    write(BEAN, c)
    print("  [ok] HysteriaBean.java: deserialize null guard added")


def main():
    print(">>> patch_hy2_hopfield_fix: null-safe hopPorts (#117 regression)")
    patch_fmt()
    patch_bean()
    print(">>> done")


if __name__ == "__main__":
    main()
