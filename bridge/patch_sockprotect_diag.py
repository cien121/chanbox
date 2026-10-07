#!/usr/bin/env python3
"""Socket-protect diagnostic logging (diag branch only).

Problem being diagnosed: when VPN is connected, batch latency tests spawn
per-node temporary sing-box test instances whose outbound sockets may not be
protected from the TUN, so test traffic gets sucked into the main tunnel
("testing all nodes through the current node" -> double hop -> 5s timeout).

This patch adds LOGGING ONLY, zero behavior change:
  Go libcore/box.go:
    - NewSingBoxInstance entry: isBgProcess value
    - SetAsMain entry: protect server (re)start marker
    - goServeProtect: start/stop marker
    - ServeProtect callback: fd received via protect_path unix socket
    - UrlTest entry: whether test instance or main instance is used
  Go libcore/platform_box.go:
    - boxPlatformInterfaceWrapper.AutoDetectInterfaceControl: fd + branch taken
      (protect_path unix socket vs direct intfBox call) + sendFdToProtect error
      (previously silently ignored with `_ =`)
  Kotlin NativeInterface.kt:
    - autoDetectInterfaceControl: fd + vpnService null or not + protect() result
  Kotlin ConfigurationFragment.kt:
    - urlTestInternal entry: batch test START marker with vpnState

All log lines carry the prefix "SockProtectDiag" for easy logcat filtering:
    adb logcat | grep SockProtectDiag

Idempotent via marker sockProtectDiag (per file).
"""

import sys

# NOTE: marker is the capital-S log prefix, which is injected into every
# patched file (Go log lines + Kotlin log lines), so per-file idempotency works.
MARKER = "SockProtectDiag"

# ---------------------------------------------------------------- Go: box.go
BOX_GO = "libcore/box.go"

BOX_GO_PATCHES = [
    # 1. NewSingBoxInstance entry
    (
        "func NewSingBoxInstance(config string, localTransport LocalDNSTransport) (b *BoxInstance, err error) {\n",
        "func NewSingBoxInstance(config string, localTransport LocalDNSTransport) (b *BoxInstance, err error) {\n"
        '\tlog.Println("SockProtectDiag NewSingBoxInstance enter isBgProcess=", isBgProcess)\n',
    ),
    # 2. SetAsMain entry
    (
        "func (b *BoxInstance) SetAsMain() {\n\tmainInstance = b\n",
        "func (b *BoxInstance) SetAsMain() {\n"
        '\tlog.Println("SockProtectDiag SetAsMain enter: marking main instance, (re)starting protect server")\n'
        "\tmainInstance = b\n",
    ),
    # 3. goServeProtect start/stop
    (
        "func goServeProtect(start bool) {\n",
        "func goServeProtect(start bool) {\n"
        '\tlog.Println("SockProtectDiag goServeProtect start=", start)\n',
    ),
    # 4. ServeProtect callback: fd received via unix socket
    (
        '\t\tprotectCloser = protect_server.ServeProtect("protect_path", false, 0, func(fd int) {\n'
        "\t\t\tintfBox.AutoDetectInterfaceControl(int32(fd))\n"
        "\t\t})\n",
        '\t\tprotectCloser = protect_server.ServeProtect("protect_path", false, 0, func(fd int) {\n'
        '\t\t\tlog.Println("SockProtectDiag protectServer: fd received via protect_path, forwarding to Java fd=", fd)\n'
        "\t\t\tintfBox.AutoDetectInterfaceControl(int32(fd))\n"
        "\t\t})\n",
    ),
    # 5. UrlTest entry
    (
        "func UrlTest(i *BoxInstance, link string, timeout int32) (latency int32, err error) {\n",
        "func UrlTest(i *BoxInstance, link string, timeout int32) (latency int32, err error) {\n"
        '\tlog.Println("SockProtectDiag UrlTest enter useTestInstance=", i != nil, " mainInstanceNil=", mainInstance == nil)\n',
    ),
]

# ------------------------------------------------------- Go: platform_box.go
PLATFORM_BOX_GO = "libcore/platform_box.go"

PLATFORM_BOX_OLD = """func (w *boxPlatformInterfaceWrapper) AutoDetectInterfaceControl(fd int) error {
	// call protect_path
	if !isBgProcess {
		_ = sendFdToProtect(fd, "protect_path")
		return nil
	}
	// bg process call VPNService
	return intfBox.AutoDetectInterfaceControl(int32(fd))
}"""

PLATFORM_BOX_NEW = """func (w *boxPlatformInterfaceWrapper) AutoDetectInterfaceControl(fd int) error {
	// sockProtectDiag: diagnostic logging only, zero behavior change
	log.Println("SockProtectDiag AutoDetectInterfaceControl enter fd=", fd, " isBgProcess=", isBgProcess)
	// call protect_path
	if !isBgProcess {
		err := sendFdToProtect(fd, "protect_path")
		log.Println("SockProtectDiag sendFdToProtect fd=", fd, " err=", err)
		return nil
	}
	// bg process call VPNService
	err := intfBox.AutoDetectInterfaceControl(int32(fd))
	log.Println("SockProtectDiag intfBox.AutoDetectInterfaceControl fd=", fd, " err=", err)
	return err
}"""

# ------------------------------------------------- Kotlin: NativeInterface.kt
NATIVE_IFACE_KT = "app/src/main/java/moe/matsuri/nb4a/NativeInterface.kt"

NATIVE_IFACE_OLD = """    override fun autoDetectInterfaceControl(fd: Int) {
        DataStore.vpnService?.protect(fd)
    }"""

NATIVE_IFACE_NEW = """    override fun autoDetectInterfaceControl(fd: Int) {
        // sockProtectDiag: diagnostic logging only, zero behavior change
        // (protect() is still called exactly when vpnService != null, as before)
        val svc = DataStore.vpnService
        val ok = svc?.protect(fd) ?: false
        android.util.Log.i("SockProtectDiag", "java autoDetectInterfaceControl fd=" + fd + " vpnServiceNull=" + (svc == null) + " protectResult=" + ok)
    }"""

# --------------------------------------- Kotlin: ConfigurationFragment.kt
FRAGMENT_KT = "app/src/main/java/io/nekohasekai/sagernet/ui/ConfigurationFragment.kt"

# Post-guard anchor (guard patch runs before this one in integrate.sh)
FRAGMENT_ANCHOR_GUARD = (
    "    private fun urlTestInternal() {\n"
    "        if (DataStore.runningTest) return else DataStore.runningTest = true\n"
)
# Pre-guard fallback anchor (upstream text, if guard patch were absent)
FRAGMENT_ANCHOR_UPSTREAM = (
    "    fun urlTest() {\n"
    "        if (DataStore.runningTest) return else DataStore.runningTest = true\n"
)
FRAGMENT_LOG_LINE = (
    '        android.util.Log.i("SockProtectDiag", "batch urlTest START vpnState=" + DataStore.serviceState)\n'
)


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _write(path, src):
    with open(path, "w", encoding="utf-8") as f:
        f.write(src)


def _apply(path, replacements):
    """replacements: list of (old, new). Each old must occur exactly once."""
    src = _read(path)
    if MARKER in src:
        print(f"{path}: {MARKER} already applied, skip")
        return
    for old, new in replacements:
        count = src.count(old)
        assert count == 1, f"{path}: expected exactly 1 anchor, found {count} for: {old[:80]!r}"
        src = src.replace(old, new, 1)
    _write(path, src)
    print(f"{path}: {MARKER} applied OK ({len(replacements)} hunks)")


def patch_box_go(root):
    _apply(root + "/" + BOX_GO, BOX_GO_PATCHES)


def patch_platform_box_go(root):
    _apply(root + "/" + PLATFORM_BOX_GO, [(PLATFORM_BOX_OLD, PLATFORM_BOX_NEW)])


def patch_native_iface(root):
    _apply(root + "/" + NATIVE_IFACE_KT, [(NATIVE_IFACE_OLD, NATIVE_IFACE_NEW)])


def patch_fragment(root):
    path = root + "/" + FRAGMENT_KT
    src = _read(path)
    if MARKER in src:
        print(f"{path}: {MARKER} already applied, skip")
        return
    if src.count(FRAGMENT_ANCHOR_GUARD) == 1:
        anchor = FRAGMENT_ANCHOR_GUARD
        print(f"{path}: using post-guard anchor (urlTestInternal)")
    elif src.count(FRAGMENT_ANCHOR_UPSTREAM) == 1:
        anchor = FRAGMENT_ANCHOR_UPSTREAM
        print(f"{path}: using upstream anchor (urlTest)")
    else:
        raise AssertionError(f"{path}: no urlTest anchor found")
    src = src.replace(anchor, anchor + FRAGMENT_LOG_LINE, 1)
    _write(path, src)
    print(f"{path}: {MARKER} applied OK (1 hunk)")


def main():
    patch_box_go(".")
    patch_platform_box_go(".")
    patch_native_iface(".")
    patch_fragment(".")
    print("ALL SOCKPROTECT-DIAG PATCHES OK")


if __name__ == "__main__":
    main()
