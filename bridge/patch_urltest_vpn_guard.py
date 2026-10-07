#!/usr/bin/env python3
"""VPN guard for batch latency test (ConfigurationFragment.urlTest).

Problem: when VPN is connected, tapping "URL test" on the node list spawns
per-node temporary sing-box test instances whose sockets may not be protected
from the TUN, so test traffic gets sucked into the main tunnel ("testing all
nodes through the current node" -> double hop -> 5s timeout on every node,
a misleading "all timeout" report).

Fix (productized workaround, scheme 1): guard the batch-test entry. If VPN
is running, show a dialog:

    title:   "VPN 正在运行"
    message: "VPN 正在运行，延迟测试可能不准确（测试流量会经过当前隧道）。"
    [断开并测试] -> stop VPN, wait for Stopped (10s max), then run the test
    [仍要测试]   -> run the test anyway
    [取消]       -> dismiss

Implementation: rename original fun urlTest() to private fun urlTestInternal(),
insert a new public fun urlTest() wrapper with the guard in front.

Idempotent via marker chanboxVpnGuard.
"""

import sys

MARKER = "chanboxVpnGuard"
FRAGMENT_KT = ("app/src/main/java/io/nekohasekai/sagernet/ui/"
               "ConfigurationFragment.kt")

ANCHOR = "    @OptIn(DelicateCoroutinesApi::class)\n    fun urlTest() {"

GUARD = '''    @OptIn(DelicateCoroutinesApi::class)
    fun urlTest() {
        // chanboxVpnGuard: VPN 运行时批量延迟测试的测试流量可能被主隧道吸走，
        // 导致全部节点显示"超时"误报。先提示用户，由用户决定。
        val vpnState = DataStore.serviceState
        if (vpnState == BaseService.State.Connected ||
            vpnState == BaseService.State.Connecting) {
            MaterialAlertDialogBuilder(requireContext())
                .setTitle("VPN 正在运行")
                .setMessage("VPN 正在运行，延迟测试可能不准确（测试流量会经过当前隧道）。")
                .setPositiveButton("断开并测试") { _, _ ->
                    SagerNet.stopService()
                    runOnDefaultDispatcher {
                        var tries = 0
                        while (DataStore.serviceState != BaseService.State.Stopped && tries < 100) {
                            Thread.sleep(100)
                            tries++
                        }
                        onMainDispatcher {
                            urlTestInternal()
                        }
                    }
                }
                .setNeutralButton("仍要测试") { _, _ ->
                    urlTestInternal()
                }
                .setNegativeButton("取消", null)
                .show()
            return
        }
        urlTestInternal()
    }

    @OptIn(DelicateCoroutinesApi::class)
    private fun urlTestInternal() {'''


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _write(path, src):
    with open(path, "w", encoding="utf-8") as f:
        f.write(src)


def patch_fragment(root):
    path = root + "/" + FRAGMENT_KT
    src = _read(path)
    if MARKER in src:
        print("ConfigurationFragment.kt VPN guard already applied, skip")
        return
    count = src.count(ANCHOR)
    assert count == 1, "expected exactly 1 urlTest() anchor, found %d" % count
    assert "fun urlTestInternal()" not in src, "urlTestInternal already exists"

    src = src.replace(ANCHOR, GUARD, 1)
    _write(path, src)
    print("ConfigurationFragment.kt VPN guard applied OK")


def main():
    patch_fragment(".")
    print("ALL VPN-GUARD PATCHES OK")


if __name__ == "__main__":
    main()
