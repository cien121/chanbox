#!/usr/bin/env python3
"""Set installer version to clean v01 (no 1.4.2).

User request (2026-10-06): installer version -> v01, must not contain 142.
nb4a.properties VERSION_NAME feeds Gradle versionName and the APK file name
(NB4A-<versionName>-<abi>-....apk).

Idempotent via marker comment.
"""

import re

MARKER = "chanboxVersionV01"
PATH = "nb4a.properties"


def main():
    with open(PATH, encoding="utf-8") as f:
        src = f.read()
    if MARKER in src:
        print("nb4a.properties already patched, skip")
        return
    new, n = re.subn(r"^VERSION_NAME=.*$", "VERSION_NAME=v01  # " + MARKER,
                     src, flags=re.M)
    assert n == 1, "VERSION_NAME line not found exactly once"
    with open(PATH, "w", encoding="utf-8") as f:
        f.write(new)
    print("nb4a.properties VERSION_NAME=v01 OK")


if __name__ == "__main__":
    main()
