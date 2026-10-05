#!/usr/bin/env python3
"""ChanBox: replace NekoBox default routes with v2rayNG's 7 default rules.

NekoBox creates default routes on first run in ProfileManager.getRules()
(when rules table is empty). This patch replaces that default set with
v2rayNG's defaults:

1. 屏蔽广告 [geosite:category-ads-all] -> block (-2)
2. 阻断 udp443 port 443/udp -> block (-2)
3. 代理 Google [geosite:google] -> proxy (0)
4. 绕过局域网 IP [geoip:private] -> direct (-1)
5. 绕过局域网域名 [geosite:private] -> direct (-1)
6. 绕过中国公共 DNS IP [223.5.5.5, ...] -> direct (-1)
7. 绕过中国公共 DNS 域名 [domain:alidns.com, ...] -> direct (-1)

Idempotent: checks for marker comment before patching.
"""
import re
import sys

MARKER = "// [chanbox] v2rayNG default routes"

NEW_BLOCK = """    suspend fun getRules(): List<RuleEntity> {
        var rules = SagerDatabase.rulesDao.allRules()
        if (rules.isEmpty() && !DataStore.rulesFirstCreate) {
            DataStore.rulesFirstCreate = true
            // [chanbox] v2rayNG default routes
            createRule(
                RuleEntity(
                    name = "屏蔽广告",
                    domains = "geosite:category-ads-all",
                    outbound = -2
                )
            )
            createRule(
                RuleEntity(
                    name = "阻断 udp443",
                    port = "443",
                    network = "udp",
                    outbound = -2
                )
            )
            createRule(
                RuleEntity(
                    name = "代理 Google",
                    domains = "geosite:google",
                    outbound = 0
                )
            )
            createRule(
                RuleEntity(
                    name = "绕过局域网 IP",
                    ip = "geoip:private",
                    outbound = -1
                )
            )
            createRule(
                RuleEntity(
                    name = "绕过局域网域名",
                    domains = "geosite:private",
                    outbound = -1
                )
            )
            createRule(
                RuleEntity(
                    name = "绕过中国公共 DNS IP",
                    ip = "223.5.5.5,223.6.6.6,2400:3200::1,2400:3200:baba::1",
                    outbound = -1
                )
            )
            createRule(
                RuleEntity(
                    name = "绕过中国公共 DNS 域名",
                    domains = "domain:alidns.com,domain:doh.pub,domain:dot.pub",
                    outbound = -1
                )
            )
            rules = SagerDatabase.rulesDao.allRules()
        }
        return rules
    }"""

# Regex to match the original getRules() function
OLD_PATTERN = re.compile(
    r"    suspend fun getRules\(\): List<RuleEntity> \{.*?        return rules\n    \}",
    re.DOTALL,
)


def main():
    path = "app/src/main/java/io/nekohasekai/sagernet/database/ProfileManager.kt"
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"ERROR: {path} not found (run from nekobox dir)")
        return 1

    if MARKER in content:
        print(">>> [routes] v2rayNG default routes already applied, skip")
        return 0

    new_content, n = OLD_PATTERN.subn(NEW_BLOCK, content, count=1)
    if n == 0:
        print("ERROR: getRules() pattern not found in ProfileManager.kt")
        return 1

    with open(path, "w", encoding="utf-8") as f:
        f.write(new_content)
    print(">>> [routes] default routes replaced with v2rayNG set OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
