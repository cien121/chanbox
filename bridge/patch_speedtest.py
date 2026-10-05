#!/usr/bin/env python3
"""Add speed test feature to ChanBox (RelayBox).

Adds download/upload speed testing through the selected proxy node:
1. Go side (libcore):
   - New file libcore/speedtest.go: download/upload speed measurement logic
   - box.go: add exported SpeedTestDownload/SpeedTestUpload functions
     (following the existing UrlTest pattern with boxapi.CreateProxyHttpClient)
2. Kotlin side:
   - New SpeedTestFragment.kt: UI tab in Tools section
   - New layout_speedtest.xml: start button, progress, results display
   - ToolsFragment.kt: add SpeedTest tab
   - strings.xml (en + zh-rCN): new string resources

Test servers (Ookla Speedtest.net):
- Server list: https://www.speedtest.net/api/js/servers (queried through the proxy,
  so servers near the node's exit are picked)
- Download: {server}/download?size=25000000 (25MB)
- Upload: {server}/upload.php (POST)

Idempotent: checks MARKER before applying.
"""
import os
import sys

MARKER = "chanboxSpeedTest"

# ---------------------------------------------------------------- Go: libcore/speedtest.go
SPEEDTEST_GO = '''package libcore

import (
\t"bytes"
\t"context"
\t"encoding/json"
\t"fmt"
\t"io"
\t"net/http"
\t"strings"
\t"time"
)

// downloadSpeed measures download throughput through client in Mbps.
func downloadSpeed(client *http.Client, link string, timeout int32) (float64, error) {
\tif client == nil {
\t\treturn 0, fmt.Errorf("no client")
\t}
\tdefer client.CloseIdleConnections()

\tctx, cancel := context.WithTimeout(context.Background(), time.Duration(timeout)*time.Millisecond)
\tdefer cancel()

\treq, err := http.NewRequestWithContext(ctx, "GET", link, nil)
\tif err != nil {
\t\treturn 0, err
\t}
\treq.Header.Set("User-Agent", ooklaUserAgent)

\tstart := time.Now()
\tresp, err := client.Do(req)
\tif err != nil {
\t\treturn 0, err
\t}
\tdefer resp.Body.Close()

\tn, err := io.Copy(io.Discard, resp.Body)
\tif err != nil {
\t\treturn 0, err
\t}

\telapsed := time.Since(start).Seconds()
\tif elapsed <= 0 {
\t\treturn 0, fmt.Errorf("invalid elapsed time")
\t}

\t// Mbps = (bytes * 8) / (seconds * 1e6)
\treturn float64(n*8) / (elapsed * 1e6), nil
}

// uploadSpeed measures upload throughput through client in Mbps.
func uploadSpeed(client *http.Client, link string, sizeBytes int64, timeout int32) (float64, error) {
\tif client == nil {
\t\treturn 0, fmt.Errorf("no client")
\t}
\tdefer client.CloseIdleConnections()

\t// deterministic pseudo-random payload (avoid compression skew)
\tdata := make([]byte, sizeBytes)
\tfor i := range data {
\t\tdata[i] = byte((i * 31) & 0xff)
\t}

\tctx, cancel := context.WithTimeout(context.Background(), time.Duration(timeout)*time.Millisecond)
\tdefer cancel()

\treq, err := http.NewRequestWithContext(ctx, "POST", link, bytes.NewReader(data))
\tif err != nil {
\t\treturn 0, err
\t}
\treq.ContentLength = sizeBytes
\treq.Header.Set("Content-Type", "application/octet-stream")
\treq.Header.Set("User-Agent", ooklaUserAgent)

\tstart := time.Now()
\tresp, err := client.Do(req)
\tif err != nil {
\t\treturn 0, err
\t}
\tdefer resp.Body.Close()
\tio.Copy(io.Discard, resp.Body)

\telapsed := time.Since(start).Seconds()
\tif elapsed <= 0 {
\t\treturn 0, fmt.Errorf("invalid elapsed time")
\t}

\treturn float64(sizeBytes*8) / (elapsed * 1e6), nil
}

// ---------------------------------------------------------------- Ookla Speedtest.net

const ooklaUserAgent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
const ooklaServerAPI = "https://www.speedtest.net/api/js/servers?engine=js&https_functional=true&limit=10"

// ooklaServer is one entry from the speedtest.net server list API.
type ooklaServer struct {
\tURL     string `json:"url"`
\tName    string `json:"name"`
\tCountry string `json:"country"`
\tSponsor string `json:"sponsor"`
\tHost    string `json:"host"`
}

// selectOoklaServer queries the speedtest.net server list through client
// (so servers near the proxy exit are returned), picks the first server,
// and returns "downloadURL\\nuploadURL\\nserverName".
func selectOoklaServer(client *http.Client, timeout int32) (string, error) {
\tif client == nil {
\t\treturn "", fmt.Errorf("no client")
\t}
\tdefer client.CloseIdleConnections()

\tctx, cancel := context.WithTimeout(context.Background(), time.Duration(timeout)*time.Millisecond)
\tdefer cancel()

\treq, err := http.NewRequestWithContext(ctx, "GET", ooklaServerAPI, nil)
\tif err != nil {
\t\treturn "", err
\t}
\treq.Header.Set("User-Agent", ooklaUserAgent)
\treq.Header.Set("Accept", "application/json")
\treq.Header.Set("Referer", "https://www.speedtest.net/")

\tresp, err := client.Do(req)
\tif err != nil {
\t\treturn "", err
\t}
\tdefer resp.Body.Close()

\tif resp.StatusCode != 200 {
\t\treturn "", fmt.Errorf("server list HTTP %d", resp.StatusCode)
\t}

\tvar servers []ooklaServer
\tif err := json.NewDecoder(resp.Body).Decode(&servers); err != nil {
\t\treturn "", err
\t}
\tif len(servers) == 0 {
\t\treturn "", fmt.Errorf("no speedtest servers found")
\t}

\tsrv := servers[0]
\tif srv.URL == "" {
\t\treturn "", fmt.Errorf("server has no URL")
\t}
\tuploadURL := srv.URL
\tdownloadURL := strings.Replace(srv.URL, "upload.php", "download?size=25000000", 1)
\tname := srv.Sponsor
\tif srv.Name != "" {
\t\tname = srv.Name + " (" + srv.Sponsor + ")"
\t}
\treturn downloadURL + "\\n" + uploadURL + "\\n" + name, nil
}
'''

# ---------------------------------------------------------------- Go: box.go additions
BOX_GO_IMPORTS_OLD = '''import (
\t"context"
\t"errors"
\t"fmt"
\t"io"
\t"libcore/device"
\t"log"
\t"runtime"
\t"runtime/debug"
\t"strings"
\t"sync"
'''
BOX_GO_IMPORTS_NEW = '''import (
\t"context"
\t"errors"
\t"fmt"
\t"io"
\t"libcore/device"
\t"log"
\t"net/http"
\t"runtime"
\t"runtime/debug"
\t"strings"
\t"sync"
'''

BOX_GO_FUNCS = '''
// SpeedTestDownload measures download speed in Mbps through the given box instance.
// If i is nil, tests through mainInstance (or direct if no service running).
func SpeedTestDownload(i *BoxInstance, link string, timeout int32) (mbps float64, err error) {
\tdefer device.DeferPanicToError("box.SpeedTestDownload", func(err_ error) { err = err_ })
\tvar client *http.Client
\tif i != nil {
\t\tvar connectionTracker adapter.ConnectionTracker
\t\tif i.v2api != nil {
\t\t\tconnectionTracker = i.v2api.StatsService()
\t\t}
\t\tclient = boxapi.CreateProxyHttpClient(i.Box, connectionTracker)
\t} else if mainInstance == nil {
\t\tclient = boxapi.CreateProxyHttpClient(nil, nil)
\t} else {
\t\tvar connectionTracker adapter.ConnectionTracker
\t\tif mainInstance.v2api != nil {
\t\t\tconnectionTracker = mainInstance.v2api.StatsService()
\t\t}
\t\tclient = boxapi.CreateProxyHttpClient(mainInstance.Box, connectionTracker)
\t}
\treturn downloadSpeed(client, link, timeout)
}

// SpeedTestUpload measures upload speed in Mbps through the given box instance.
// sizeMB is the payload size in megabytes.
// If i is nil, tests through mainInstance (or direct if no service running).
func SpeedTestUpload(i *BoxInstance, link string, sizeMB int32, timeout int32) (mbps float64, err error) {
\tdefer device.DeferPanicToError("box.SpeedTestUpload", func(err_ error) { err = err_ })
\tvar client *http.Client
\tif i != nil {
\t\tvar connectionTracker adapter.ConnectionTracker
\t\tif i.v2api != nil {
\t\t\tconnectionTracker = i.v2api.StatsService()
\t\t}
\t\tclient = boxapi.CreateProxyHttpClient(i.Box, connectionTracker)
\t} else if mainInstance == nil {
\t\tclient = boxapi.CreateProxyHttpClient(nil, nil)
\t} else {
\t\tvar connectionTracker adapter.ConnectionTracker
\t\tif mainInstance.v2api != nil {
\t\t\tconnectionTracker = mainInstance.v2api.StatsService()
\t\t}
\t\tclient = boxapi.CreateProxyHttpClient(mainInstance.Box, connectionTracker)
\t}
\treturn uploadSpeed(client, link, int64(sizeMB)*1024*1024, timeout)
}

// SpeedTestSelectServer picks an Ookla speedtest.net server through the given
// box instance and returns "downloadURL\\nuploadURL\\nserverName".
// If i is nil, uses mainInstance (or direct if no service running).
func SpeedTestSelectServer(i *BoxInstance, timeout int32) (info string, err error) {
\tdefer device.DeferPanicToError("box.SpeedTestSelectServer", func(err_ error) { err = err_ })
\tvar client *http.Client
\tif i != nil {
\t\tvar connectionTracker adapter.ConnectionTracker
\t\tif i.v2api != nil {
\t\t\tconnectionTracker = i.v2api.StatsService()
\t\t}
\t\tclient = boxapi.CreateProxyHttpClient(i.Box, connectionTracker)
\t} else if mainInstance == nil {
\t\tclient = boxapi.CreateProxyHttpClient(nil, nil)
\t} else {
\t\tvar connectionTracker adapter.ConnectionTracker
\t\tif mainInstance.v2api != nil {
\t\t\tconnectionTracker = mainInstance.v2api.StatsService()
\t\t}
\t\tclient = boxapi.CreateProxyHttpClient(mainInstance.Box, connectionTracker)
\t}
\treturn selectOoklaServer(client, timeout)
}
'''

# ---------------------------------------------------------------- Kotlin: SpeedTestFragment.kt
SPEEDTEST_FRAGMENT_KT = '''package io.nekohasekai.sagernet.ui

import android.os.Bundle
import android.view.View
import io.nekohasekai.sagernet.R
import io.nekohasekai.sagernet.database.DataStore
import io.nekohasekai.sagernet.database.SagerDatabase
import io.nekohasekai.sagernet.databinding.LayoutSpeedtestBinding
import io.nekohasekai.sagernet.ktx.app
import io.nekohasekai.sagernet.ktx.onMainDispatcher
import io.nekohasekai.sagernet.ktx.runOnDefaultDispatcher
import kotlinx.coroutines.Job
import kotlinx.coroutines.cancel

// chanboxSpeedTest: bandwidth test tab in Tools (download + upload via selected node)
class SpeedTestFragment : NamedFragment(R.layout.layout_speedtest) {

    companion object {
        const val TIMEOUT_MS = 30000
        const val UPLOAD_SIZE_MB = 10
    }

    override fun name0() = app.getString(R.string.tools_speedtest)

    private var testJob: Job? = null

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        val binding = LayoutSpeedtestBinding.bind(view)

        fun setRunning(running: Boolean) {
            binding.speedtestStart.isEnabled = !running
            binding.speedtestCancel.isEnabled = running
            binding.speedtestProgress.visibility = if (running) View.VISIBLE else View.GONE
        }

        binding.speedtestCancel.setOnClickListener {
            testJob?.cancel()
            setRunning(false)
            binding.speedtestStatus.text = getString(R.string.speedtest_cancelled)
        }

        binding.speedtestStart.setOnClickListener {
            val profileId = DataStore.selectedProxy
            if (profileId == 0L) {
                binding.speedtestStatus.text = getString(R.string.speedtest_no_profile)
                return@setOnClickListener
            }
            setRunning(true)
            binding.speedtestDownload.text = getString(R.string.speedtest_testing)
            binding.speedtestUpload.text = getString(R.string.speedtest_testing)
            binding.speedtestStatus.text = getString(R.string.speedtest_running)

            testJob = runOnDefaultDispatcher {
                try {
                    val entity = SagerDatabase.proxyDao.getById(profileId) ?: run {
                        onMainDispatcher {
                            setRunning(false)
                            binding.speedtestStatus.text = getString(R.string.speedtest_no_profile)
                        }
                        return@runOnDefaultDispatcher
                    }
                    val instance = SpeedTestInstance(entity)

                    onMainDispatcher {
                        binding.speedtestStatus.text = getString(R.string.speedtest_selecting)
                    }
                    val serverParts = try {
                        instance.doSelectServer(TIMEOUT_MS).split("\n")
                    } catch (e: Exception) {
                        onMainDispatcher {
                            binding.speedtestStatus.text =
                                getString(R.string.speedtest_error, e.message ?: "")
                        }
                        throw e
                    }
                    if (serverParts.size < 3) {
                        onMainDispatcher {
                            binding.speedtestStatus.text =
                                getString(R.string.speedtest_error, "bad server info")
                        }
                        return@runOnDefaultDispatcher
                    }
                    val downloadUrl = serverParts[0]
                    val uploadUrl = serverParts[1]
                    val serverName = serverParts[2]
                    onMainDispatcher {
                        binding.speedtestStatus.text =
                            getString(R.string.speedtest_server, serverName) +
                            "\n" + getString(R.string.speedtest_downloading)
                    }
                    val downloadMbps = try {
                        instance.doDownloadTest(downloadUrl, TIMEOUT_MS)
                    } catch (e: Exception) {
                        onMainDispatcher {
                            binding.speedtestDownload.text = getString(R.string.speedtest_failed)
                        }
                        throw e
                    }
                    onMainDispatcher {
                        binding.speedtestDownload.text =
                            getString(R.string.speedtest_mbps, downloadMbps)
                        binding.speedtestStatus.text = getString(R.string.speedtest_uploading)
                    }

                    val uploadMbps = try {
                        instance.doUploadTest(uploadUrl, UPLOAD_SIZE_MB, TIMEOUT_MS)
                    } catch (e: Exception) {
                        onMainDispatcher {
                            binding.speedtestUpload.text = getString(R.string.speedtest_failed)
                        }
                        throw e
                    }
                    onMainDispatcher {
                        binding.speedtestUpload.text =
                            getString(R.string.speedtest_mbps, uploadMbps)
                        binding.speedtestStatus.text = getString(R.string.speedtest_done)
                    }
                } catch (e: Exception) {
                    if (e is kotlinx.coroutines.CancellationException) throw e
                    onMainDispatcher {
                        binding.speedtestStatus.text =
                            getString(R.string.speedtest_error, e.message ?: "")
                    }
                } finally {
                    onMainDispatcher { setRunning(false) }
                }
            }
        }
    }

    override fun onDestroyView() {
        testJob?.cancel()
        super.onDestroyView()
    }
}
'''

# ---------------------------------------------------------------- Kotlin: SpeedTestInstance (bg/proto)
SPEEDTEST_INSTANCE_KT = '''package io.nekohasekai.sagernet.bg.proto

import io.nekohasekai.sagernet.database.ProxyEntity
import io.nekohasekai.sagernet.ktx.runOnDefaultDispatcher
import io.nekohasekai.sagernet.ktx.tryResume
import io.nekohasekai.sagernet.ktx.tryResumeWithException
import kotlinx.coroutines.delay
import libcore.Libcore
import moe.matsuri.nb4a.net.LocalResolverImpl
import kotlin.coroutines.suspendCoroutine

// chanboxSpeedTest: per-profile sing-box instance for bandwidth testing.
// Mirrors TestInstance but calls the SpeedTest* libcore functions.
class SpeedTestInstance(profile: ProxyEntity) : BoxInstance(profile) {

    override fun buildConfig() {
        config = buildConfig(profile, true)
    }

    suspend fun doSelectServer(timeout: Int): String {
        return suspendCoroutine { c ->
            processes = GuardedProcessPool {
                c.tryResumeWithException(it)
            }
            runOnDefaultDispatcher {
                use {
                    try {
                        init()
                        launch()
                        if (processes.processCount > 0) {
                            delay(500)
                        }
                        c.tryResume(Libcore.speedTestSelectServer(box, timeout))
                    } catch (e: Exception) {
                        c.tryResumeWithException(e)
                    }
                }
            }
        }
    }

    suspend fun doDownloadTest(link: String, timeout: Int): Double {
        return suspendCoroutine { c ->
            processes = GuardedProcessPool {
                c.tryResumeWithException(it)
            }
            runOnDefaultDispatcher {
                use {
                    try {
                        init()
                        launch()
                        if (processes.processCount > 0) {
                            delay(500)
                        }
                        c.tryResume(Libcore.speedTestDownload(box, link, timeout))
                    } catch (e: Exception) {
                        c.tryResumeWithException(e)
                    }
                }
            }
        }
    }

    suspend fun doUploadTest(link: String, sizeMB: Int, timeout: Int): Double {
        return suspendCoroutine { c ->
            processes = GuardedProcessPool {
                c.tryResumeWithException(it)
            }
            runOnDefaultDispatcher {
                use {
                    try {
                        init()
                        launch()
                        if (processes.processCount > 0) {
                            delay(500)
                        }
                        c.tryResume(Libcore.speedTestUpload(box, link, sizeMB, timeout))
                    } catch (e: Exception) {
                        c.tryResumeWithException(e)
                    }
                }
            }
        }
    }

    override suspend fun loadConfig() {
        box = Libcore.newSingBoxInstance(config.config, LocalResolverImpl)
    }
}
'''

# ---------------------------------------------------------------- layout_speedtest.xml
LAYOUT_SPEEDTEST_XML = '''<?xml version="1.0" encoding="utf-8"?>
<!-- chanboxSpeedTest -->
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    android:orientation="vertical"
    android:padding="16dp">

    <TextView
        android:id="@+id/speedtest_status"
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:text="@string/speedtest_idle"
        android:textSize="14sp"
        android:layout_marginBottom="16dp" />

    <LinearLayout
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:orientation="horizontal"
        android:layout_marginBottom="8dp">

        <TextView
            android:layout_width="0dp"
            android:layout_height="wrap_content"
            android:layout_weight="1"
            android:text="@string/speedtest_download" />

        <TextView
            android:id="@+id/speedtest_download"
            android:layout_width="0dp"
            android:layout_height="wrap_content"
            android:layout_weight="1"
            android:text="--"
            android:textStyle="bold" />
    </LinearLayout>

    <LinearLayout
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:orientation="horizontal"
        android:layout_marginBottom="16dp">

        <TextView
            android:layout_width="0dp"
            android:layout_height="wrap_content"
            android:layout_weight="1"
            android:text="@string/speedtest_upload" />

        <TextView
            android:id="@+id/speedtest_upload"
            android:layout_width="0dp"
            android:layout_height="wrap_content"
            android:layout_weight="1"
            android:text="--"
            android:textStyle="bold" />
    </LinearLayout>

    <ProgressBar
        android:id="@+id/speedtest_progress"
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        style="?android:attr/progressBarStyleHorizontal"
        android:indeterminate="true"
        android:visibility="gone"
        android:layout_marginBottom="16dp" />

    <LinearLayout
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:orientation="horizontal">

        <Button
            android:id="@+id/speedtest_start"
            android:layout_width="0dp"
            android:layout_height="wrap_content"
            android:layout_weight="1"
            android:text="@string/speedtest_start" />

        <Button
            android:id="@+id/speedtest_cancel"
            android:layout_width="0dp"
            android:layout_height="wrap_content"
            android:layout_weight="1"
            android:text="@string/speedtest_cancel"
            android:enabled="false" />
    </LinearLayout>

    <TextView
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:text="@string/speedtest_hint"
        android:textSize="12sp"
        android:layout_marginTop="16dp" />

</LinearLayout>
'''

# ---------------------------------------------------------------- string resources
STRINGS_EN = {
    "tools_speedtest": "Speed Test",
    "speedtest_idle": "Test the selected node's download/upload speed.",
    "speedtest_start": "Start Test",
    "speedtest_cancel": "Cancel",
    "speedtest_download": "Download",
    "speedtest_upload": "Upload",
    "speedtest_testing": "Testing...",
    "speedtest_running": "Running speed test...",
    "speedtest_downloading": "Testing download speed...",
    "speedtest_uploading": "Testing upload speed...",
    "speedtest_done": "Test complete.",
    "speedtest_cancelled": "Test cancelled.",
    "speedtest_failed": "Failed",
    "speedtest_no_profile": "No profile selected.",
    "speedtest_mbps": "%.1f Mbps",
    "speedtest_error": "Error: %1$s",
    "speedtest_hint": "Speed is measured through the currently selected node via Speedtest.net.",
    "speedtest_selecting": "Selecting test server...",
    "speedtest_server": "Server: %1$s",
}

STRINGS_ZH = {
    "tools_speedtest": "测速",
    "speedtest_idle": "测试当前选中节点的下行/上行速度。",
    "speedtest_start": "开始测速",
    "speedtest_cancel": "取消",
    "speedtest_download": "下行",
    "speedtest_upload": "上行",
    "speedtest_testing": "测试中...",
    "speedtest_running": "正在测速...",
    "speedtest_downloading": "正在测试下行速度...",
    "speedtest_uploading": "正在测试上行速度...",
    "speedtest_done": "测试完成。",
    "speedtest_cancelled": "已取消。",
    "speedtest_failed": "失败",
    "speedtest_no_profile": "未选择节点。",
    "speedtest_mbps": "%.1f Mbps",
    "speedtest_error": "错误：%1$s",
    "speedtest_hint": "通过当前选中节点，经 Speedtest.net 测速。",
    "speedtest_selecting": "正在选择测速服务器...",
    "speedtest_server": "服务器：%1$s",
}


def patch_go_speedtest(root):
    path = os.path.join(root, "libcore", "speedtest.go")
    if os.path.exists(path):
        with open(path) as f:
            if MARKER in f.read():
                print("libcore/speedtest.go already patched, skip")
                return
    with open(path, "w") as f:
        f.write("// " + MARKER + "\n" + SPEEDTEST_GO)
    print("libcore/speedtest.go written")


def patch_go_box(root):
    path = os.path.join(root, "libcore", "box.go")
    with open(path) as f:
        src = f.read()
    if MARKER in src:
        print("libcore/box.go already patched, skip")
        return
    assert BOX_GO_IMPORTS_OLD in src, "box.go import block not found"
    src = src.replace(BOX_GO_IMPORTS_OLD, BOX_GO_IMPORTS_NEW, 1)
    # insert new funcs right after UrlTest function (anchor on its closing + next decl)
    anchor = "var protectCloser io.Closer"
    assert anchor in src, "box.go anchor not found"
    src = src.replace(anchor, "// " + MARKER + BOX_GO_FUNCS + "\n" + anchor, 1)
    with open(path, "w") as f:
        f.write(src)
    print("libcore/box.go patched")


def patch_kotlin_fragment(root):
    path = os.path.join(root, "app/src/main/java/io/nekohasekai/sagernet/ui/SpeedTestFragment.kt")
    if os.path.exists(path):
        with open(path) as f:
            if MARKER in f.read():
                print("SpeedTestFragment.kt already exists, skip")
                return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(SPEEDTEST_FRAGMENT_KT)
    print("SpeedTestFragment.kt written")


def patch_kotlin_instance(root):
    path = os.path.join(root, "app/src/main/java/io/nekohasekai/sagernet/bg/proto/SpeedTestInstance.kt")
    if os.path.exists(path):
        with open(path) as f:
            if MARKER in f.read():
                print("SpeedTestInstance.kt already exists, skip")
                return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(SPEEDTEST_INSTANCE_KT)
    print("SpeedTestInstance.kt written")


def patch_tools_fragment(root):
    path = os.path.join(root, "app/src/main/java/io/nekohasekai/sagernet/ui/ToolsFragment.kt")
    with open(path) as f:
        src = f.read()
    if MARKER in src:
        print("ToolsFragment.kt already patched, skip")
        return
    old = "        tools.add(NetworkFragment())\n        tools.add(BackupFragment())"
    assert old in src, "ToolsFragment tools list not found"
    new = ("        tools.add(NetworkFragment())\n"
           "        // " + MARKER + "\n"
           "        tools.add(SpeedTestFragment())\n"
           "        tools.add(BackupFragment())")
    src = src.replace(old, new, 1)
    with open(path, "w") as f:
        f.write(src)
    print("ToolsFragment.kt patched")


def patch_layout(root):
    path = os.path.join(root, "app/src/main/res/layout/layout_speedtest.xml")
    if os.path.exists(path):
        with open(path) as f:
            if MARKER in f.read():
                print("layout_speedtest.xml already exists, skip")
                return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(LAYOUT_SPEEDTEST_XML)
    print("layout_speedtest.xml written")


def patch_strings(root, lang_dir, strings):
    path = os.path.join(root, "app/src/main/res", lang_dir, "strings.xml")
    with open(path) as f:
        src = f.read()
    if MARKER in src:
        print(f"{lang_dir}/strings.xml already patched, skip")
        return
    additions = []
    for k, v in strings.items():
        # formatted strings need formatting="false" only when containing %; keep simple
        # aapt2 rejects a raw apostrophe ("Invalid unicode escape sequence"), escape it
        v = v.replace("'", "\\'")
        additions.append(f'    <string name="{k}">{v}</string>')
    block = "    <!-- " + MARKER + " -->\n" + "\n".join(additions) + "\n"
    anchor = "</resources>"
    assert anchor in src, f"{lang_dir}/strings.xml anchor not found"
    src = src.replace(anchor, block + anchor, 1)
    with open(path, "w") as f:
        f.write(src)
    print(f"{lang_dir}/strings.xml patched")


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    # NekoBox checkout root is where libcore/ and app/ live; integrate.sh runs
    # with cwd at nekobox dir, bridge at ../chanbox-assets/bridge
    patch_go_speedtest(root)
    patch_go_box(root)
    patch_kotlin_fragment(root)
    patch_kotlin_instance(root)
    patch_tools_fragment(root)
    patch_layout(root)
    patch_strings(root, "values", STRINGS_EN)
    patch_strings(root, "values-zh-rCN", STRINGS_ZH)
    print("speedtest patch OK")


if __name__ == "__main__":
    main()

