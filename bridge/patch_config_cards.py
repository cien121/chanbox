#!/usr/bin/env python3
"""Card-style status panel on main screen (two loose cards) + modern FAB.

User requests (2026-10-06):
1. Bottom config/status panel -> card style.
2. Card 1: connection speed, load balance status, IP egress (geolocation).
3. Card 2: node configuration + speed test card.
4. Card design lively, not rigid; loose spacing between cards.
5. Mixed accent colors on black, keep readable.
6. VPN start icon (paper-plane FAB) redesigned, modern style.

Changes (run from NekoBox checkout root):
1. app/src/main/res/layout/layout_main.xml
   - StatsBar inner content -> slim status line + 2 MaterialCardViews
     (dark #161616 cards, blue / green accent strokes, loose margins).
   - ServiceButton: squircle shape + blue tint (modern).
2. app/src/main/res/values/themes.xml - ShapeAppearance.RelayBox.FabSquircle.
3. app/src/main/java/io/nekohasekai/sagernet/widget/StatsBar.kt
   - Wire new views: realtime speed, LB toggle (tap), IP geo (tap refresh,
     via proxy through SpeedTestInstance), node card, in-card speed test.
4. libcore/speedtest.go - append ipGeoLookup (ip-api.com through proxy).
5. libcore/box.go - export IPGeoLookup (requires patch_speedtest first).
6. bg/proto/SpeedTestInstance.kt - add doIPGeoLookup (requires patch_speedtest).
7. values/strings.xml + values-zh-rCN/strings.xml - new strings.

Requires: patch_speedtest.py and patch_loadbalance.py already applied.
Idempotent via marker comments.
"""

import re
import sys

MARKER = "chanboxConfigCards"
GEO_MARKER = "chanboxIPGeo"

LAYOUT_MAIN = "app/src/main/res/layout/layout_main.xml"
THEMES_XML = "app/src/main/res/values/themes.xml"
STATSBAR_KT = "app/src/main/java/io/nekohasekai/sagernet/widget/StatsBar.kt"
SPEEDTEST_GO = "libcore/speedtest.go"
BOX_GO = "libcore/box.go"
INSTANCE_KT = "app/src/main/java/io/nekohasekai/sagernet/bg/proto/SpeedTestInstance.kt"
STRINGS_EN = "app/src/main/res/values/strings.xml"
STRINGS_ZH = "app/src/main/res/values-zh-rCN/strings.xml"


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _write(path, src):
    with open(path, "w", encoding="utf-8") as f:
        f.write(src)


# ---------------------------------------------------------------- layout_main.xml
def _card_row(icon_entity, label_ref, value_id, row_id=None, tools_text=""):
    clickable = ""
    if row_id:
        clickable = (
            '\n                            android:id="@+id/%s"'
            '\n                            android:clickable="true"'
            '\n                            android:focusable="true"'
            '\n                            android:foreground="?android:attr/selectableItemBackground"'
        ) % row_id
    return """                        <LinearLayout{clickable}
                            android:layout_width="match_parent"
                            android:layout_height="wrap_content"
                            android:gravity="center_vertical"
                            android:orientation="horizontal"
                            android:paddingTop="7dp"
                            android:paddingBottom="7dp">

                            <TextView
                                android:layout_width="wrap_content"
                                android:layout_height="wrap_content"
                                android:text="{icon}"
                                android:textSize="20sp" />

                            <TextView
                                android:layout_width="wrap_content"
                                android:layout_height="wrap_content"
                                android:layout_marginStart="10dp"
                                android:text="{label}"
                                android:textColor="#9E9E9E"
                                android:textSize="12sp" />

                            <TextView
                                android:id="@+id/{value_id}"
                                android:layout_width="0dp"
                                android:layout_height="wrap_content"
                                android:layout_weight="1"
                                android:gravity="end"
                                android:textColor="#FFFFFF"
                                android:textSize="13sp"
                                android:textStyle="bold"
                                tools:text="{tools_text}" />
                        </LinearLayout>""".format(
        clickable=clickable, icon=icon_entity, label=label_ref,
        value_id=value_id, tools_text=tools_text,
    )


def patch_layout_main(root):
    path = root + "/" + LAYOUT_MAIN
    src = _read(path)
    if MARKER in src:
        print("layout_main.xml already patched, skip")
        return
    sb = "<io.nekohasekai.sagernet.widget.StatsBar"
    i = src.index(sb)
    j = src.index("<LinearLayout", i)
    k = src.index("</io.nekohasekai.sagernet.widget.StatsBar>", j)
    m = src.rindex("</LinearLayout>", j, k)

    inner = """<!-- %s: two loose cards, mixed accents on black -->
            <LinearLayout
                android:layout_width="match_parent"
                android:layout_height="wrap_content"
                android:background="?android:attr/selectableItemBackground"
                android:orientation="vertical"
                android:padding="12dp">

                <TextView
                    android:id="@+id/status"
                    android:layout_width="wrap_content"
                    android:layout_height="wrap_content"
                    android:layout_marginStart="4dp"
                    android:ellipsize="end"
                    android:maxLines="1"
                    android:textColor="?whiteOrTextPrimary"
                    android:textSize="13sp"
                    tools:text="@string/connection_test_available" />

                <!-- Card 1: connection status -->
                <com.google.android.material.card.MaterialCardView
                    android:layout_width="match_parent"
                    android:layout_height="wrap_content"
                    android:layout_marginTop="10dp"
                    app:cardBackgroundColor="#161616"
                    app:cardCornerRadius="18dp"
                    app:cardElevation="0dp"
                    app:strokeColor="@color/material_blue_500"
                    app:strokeWidth="1dp">

                    <LinearLayout
                        android:layout_width="match_parent"
                        android:layout_height="wrap_content"
                        android:orientation="vertical"
                        android:paddingLeft="14dp"
                        android:paddingTop="8dp"
                        android:paddingRight="14dp"
                        android:paddingBottom="8dp">

%s
%s
%s
                    </LinearLayout>
                </com.google.android.material.card.MaterialCardView>

                <!-- Card 2: node config + speed test -->
                <com.google.android.material.card.MaterialCardView
                    android:layout_width="match_parent"
                    android:layout_height="wrap_content"
                    android:layout_marginTop="12dp"
                    android:layout_marginBottom="4dp"
                    app:cardBackgroundColor="#161616"
                    app:cardCornerRadius="18dp"
                    app:cardElevation="0dp"
                    app:strokeColor="@color/material_green_500"
                    app:strokeWidth="1dp">

                    <LinearLayout
                        android:layout_width="match_parent"
                        android:layout_height="wrap_content"
                        android:orientation="vertical"
                        android:padding="14dp">

                        <LinearLayout
                            android:layout_width="match_parent"
                            android:layout_height="wrap_content"
                            android:gravity="center_vertical"
                            android:orientation="horizontal">

                            <TextView
                                android:layout_width="wrap_content"
                                android:layout_height="wrap_content"
                                android:text="&#x1F680;"
                                android:textSize="22sp" />

                            <LinearLayout
                                android:layout_width="0dp"
                                android:layout_height="wrap_content"
                                android:layout_marginStart="10dp"
                                android:layout_weight="1"
                                android:orientation="vertical">

                                <TextView
                                    android:id="@+id/card_node_name"
                                    android:layout_width="wrap_content"
                                    android:layout_height="wrap_content"
                                    android:ellipsize="end"
                                    android:maxLines="1"
                                    android:text="@string/card_node_label"
                                    android:textColor="#FFFFFF"
                                    android:textSize="14sp"
                                    android:textStyle="bold" />

                                <TextView
                                    android:id="@+id/card_node_detail"
                                    android:layout_width="wrap_content"
                                    android:layout_height="wrap_content"
                                    android:layout_marginTop="2dp"
                                    android:ellipsize="end"
                                    android:maxLines="1"
                                    android:textColor="#9E9E9E"
                                    android:textSize="12sp"
                                    tools:text="VLESS" />
                            </LinearLayout>
                        </LinearLayout>

                        <LinearLayout
                            android:layout_width="match_parent"
                            android:layout_height="wrap_content"
                            android:layout_marginTop="10dp"
                            android:gravity="center_vertical"
                            android:orientation="horizontal">

                            <com.google.android.material.button.MaterialButton
                                android:id="@+id/card_speedtest_btn"
                                android:layout_width="wrap_content"
                                android:layout_height="wrap_content"
                                android:insetLeft="0dp"
                                android:insetTop="0dp"
                                android:insetRight="0dp"
                                android:insetBottom="0dp"
                                android:minWidth="0dp"
                                android:minHeight="0dp"
                                android:paddingLeft="18dp"
                                android:paddingTop="9dp"
                                android:paddingRight="18dp"
                                android:paddingBottom="9dp"
                                android:text="@string/card_speedtest_start"
                                android:textSize="12sp"
                                app:backgroundTint="@color/material_green_500"
                                app:cornerRadius="14dp" />

                            <TextView
                                android:id="@+id/card_speedtest_value"
                                android:layout_width="0dp"
                                android:layout_height="wrap_content"
                                android:layout_marginStart="12dp"
                                android:layout_weight="1"
                                android:textColor="#FFFFFF"
                                android:textSize="13sp"
                                android:textStyle="bold" />
                        </LinearLayout>
                    </LinearLayout>
                </com.google.android.material.card.MaterialCardView>
            </LinearLayout>""" % (
        MARKER,
        _card_row("&#x1F4CA;", "@string/card_speed_label", "card_speed_value",
                  tools_text="\u25B2 0 B/s  \u25BC 0 B/s"),
        _card_row("&#x1F500;", "@string/card_lb_label", "card_lb_value",
                  row_id="card_lb_row", tools_text="\u5DF2\u5173\u95ED"),
        _card_row("&#x1F30D;", "@string/card_ip_label", "card_ip_value",
                  row_id="card_ip_row", tools_text="\u672A\u77E5"),
    )
    src = src[:j] + inner + src[m + len("</LinearLayout>"):]
    _write(path, src)
    print("layout_main.xml patched OK")


# ---------------------------------------------------------------- FAB modern style
def patch_fab(root):
    path = root + "/" + LAYOUT_MAIN
    src = _read(path)
    if "ShapeAppearance.RelayBox.FabSquircle" in src:
        print("FAB already restyled, skip")
    else:
        old = 'app:backgroundTint="?fabColorBackground"'
        assert src.count(old) == 1, "FAB backgroundTint anchor not found exactly once"
        new = ('app:backgroundTint="@color/material_blue_500"\n'
               '            app:shapeAppearanceOverlay="@style/ShapeAppearance.RelayBox.FabSquircle"')
        src = src.replace(old, new, 1)
        _write(path, src)
        print("FAB button restyled OK")
    tpath = root + "/" + THEMES_XML
    tsrc = _read(tpath)
    if "ShapeAppearance.RelayBox.FabSquircle" in tsrc:
        print("themes.xml FAB style already present, skip")
        return
    anchor = '    <style name="AppearanceFoundation.Title" parent="TextAppearance.AppCompat.Title">'
    assert tsrc.count(anchor) == 1, "themes.xml style anchor not found exactly once"
    style = ('    <!-- ' + MARKER + ': modern squircle FAB -->\n'
             '    <style name="ShapeAppearance.RelayBox.FabSquircle" parent="">\n'
             '        <item name="cornerFamily">rounded</item>\n'
             '        <item name="cornerSize">28dp</item>\n'
             '    </style>\n\n')
    tsrc = tsrc.replace(anchor, style + anchor, 1)
    _write(tpath, tsrc)
    print("themes.xml FAB style added OK")

# ---------------------------------------------------------------- StatsBar.kt
STATSBAR_IMPORTS_ANCHOR = "import io.nekohasekai.sagernet.ui.MainActivity"
STATSBAR_IMPORTS_NEW = """import io.nekohasekai.sagernet.bg.proto.SpeedTestInstance
import io.nekohasekai.sagernet.database.GroupManager
import io.nekohasekai.sagernet.database.SagerDatabase
import io.nekohasekai.sagernet.ui.MainActivity
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job"""

STATSBAR_FIELDS_OLD = """    private lateinit var statusText: TextView
    private lateinit var txText: TextView
    private lateinit var rxText: TextView
"""
STATSBAR_FIELDS_NEW = """    private lateinit var statusText: TextView
    private lateinit var cardSpeedValue: TextView
    private lateinit var cardLbValue: TextView
    private lateinit var cardIpValue: TextView
    private lateinit var cardNodeName: TextView
    private lateinit var cardNodeDetail: TextView
    private lateinit var cardSpeedtestBtn: View
    private lateinit var cardSpeedtestValue: TextView
    private var ipGeoJob: Job? = null
    private var speedtestJob: Job? = null
"""

STATSBAR_BIND_OLD = """    override fun setOnClickListener(l: OnClickListener?) {
        statusText = findViewById(R.id.status)
        txText = findViewById(R.id.tx)
        rxText = findViewById(R.id.rx)
        super.setOnClickListener(l)
    }
"""
STATSBAR_BIND_NEW = """    override fun setOnClickListener(l: OnClickListener?) {
        statusText = findViewById(R.id.status)
        cardSpeedValue = findViewById(R.id.card_speed_value)
        cardLbValue = findViewById(R.id.card_lb_value)
        cardIpValue = findViewById(R.id.card_ip_value)
        cardNodeName = findViewById(R.id.card_node_name)
        cardNodeDetail = findViewById(R.id.card_node_detail)
        cardSpeedtestBtn = findViewById(R.id.card_speedtest_btn)
        cardSpeedtestValue = findViewById(R.id.card_speedtest_value)
        findViewById<View>(R.id.card_lb_row)?.setOnClickListener { toggleLoadBalance() }
        findViewById<View>(R.id.card_ip_row)?.setOnClickListener { refreshIPGeo() }
        cardSpeedtestBtn.setOnClickListener { runCardSpeedtest() }
        updateLbCard()
        super.setOnClickListener(l)
    }
"""

STATSBAR_SPEED_OLD = """    @SuppressLint("SetTextI18n")
    fun updateSpeed(txRate: Long, rxRate: Long) {
        txText.text = "▲  ${
            context.getString(
                R.string.speed, Formatter.formatFileSize(context, txRate)
            )
        }"
        rxText.text = "▼  ${
            context.getString(
                R.string.speed, Formatter.formatFileSize(context, rxRate)
            )
        }"
    }
"""
STATSBAR_SPEED_NEW = """    @SuppressLint("SetTextI18n")
    fun updateSpeed(txRate: Long, rxRate: Long) {
        if (!::cardSpeedValue.isInitialized) return
        cardSpeedValue.text = "▲ ${
            context.getString(
                R.string.speed, Formatter.formatFileSize(context, txRate)
            )
        }  ▼ ${
            context.getString(
                R.string.speed, Formatter.formatFileSize(context, rxRate)
            )
        }"
    }
"""

STATSBAR_STATE_OLD = """        if ((state == BaseService.State.Connected).also { hideOnScroll = it }) {
            postWhenStarted {
                if (allowShow) performShow()
                setStatus(app.getText(R.string.vpn_connected))
            }
        } else {
            postWhenStarted {
                performHide()
            }
            updateSpeed(0, 0)
"""
STATSBAR_STATE_NEW = """        if ((state == BaseService.State.Connected).also { hideOnScroll = it }) {
            postWhenStarted {
                if (allowShow) performShow()
                setStatus(app.getText(R.string.vpn_connected))
                updateNodeCard()
                updateLbCard()
                refreshIPGeo()
            }
        } else {
            postWhenStarted {
                performHide()
            }
            ipGeoJob?.cancel()
            speedtestJob?.cancel()
            updateSpeed(0, 0)
            if (::cardIpValue.isInitialized) {
                cardIpValue.text = "\\uD83C\\uDF0D " + app.getString(R.string.card_ip_unknown)
            }
            if (::cardSpeedtestValue.isInitialized) {
                cardSpeedtestValue.text = ""
                cardSpeedtestBtn.isEnabled = true
            }
"""

STATSBAR_NEW_METHODS = """
    // %s: refresh load-balance card from the global switch.
    private fun updateLbCard() {
        if (!::cardLbValue.isInitialized) return
        cardLbValue.text = if (DataStore.loadBalance) app.getString(R.string.card_lb_on)
        else app.getString(R.string.card_lb_off)
    }

    // %s: tap LB card toggles the global switch (same key as group settings /
    // quick menu). Enabling auto-enables selector mode on the current group.
    private fun toggleLoadBalance() {
        val activity = context as MainActivity
        runOnDefaultDispatcher {
            val enable = !DataStore.loadBalance
            DataStore.loadBalance = enable
            if (enable) {
                val group = DataStore.currentGroup()
                if (!group.isSelector) {
                    group.isSelector = true
                    GroupManager.updateGroup(group)
                }
            }
            onMainDispatcher {
                updateLbCard()
                activity.snackbar(
                    if (enable) R.string.load_balance_enabled
                    else R.string.load_balance_disabled
                ).show()
            }
        }
    }

    // %s: show current node name / protocol / address on card 2.
    private fun updateNodeCard() {
        if (!::cardNodeName.isInitialized) return
        runOnDefaultDispatcher {
            try {
                val entity = SagerDatabase.proxyDao.getById(DataStore.selectedProxy)
                    ?: return@runOnDefaultDispatcher
                val bean = entity.requireBean()
                val name = entity.displayName().ifBlank { entity.displayType() }
                val detail = entity.displayType() + " · " + bean.serverAddress + ":" + bean.serverPort
                onMainDispatcher {
                    cardNodeName.text = name
                    cardNodeDetail.text = detail
                }
            } catch (e: Exception) {
                Logs.w(e.toString())
            }
        }
    }

    // %s: egress IP geolocation through the current profile's proxy.
    private fun refreshIPGeo() {
        if (!::cardIpValue.isInitialized) return
        ipGeoJob?.cancel()
        if (!DataStore.serviceState.connected) {
            cardIpValue.text = "\\uD83C\\uDF0D " + app.getString(R.string.card_ip_unknown)
            return
        }
        cardIpValue.text = "\\uD83C\\uDF0D " + app.getString(R.string.card_ip_fetching)
        ipGeoJob = runOnDefaultDispatcher {
            try {
                val entity = SagerDatabase.proxyDao.getById(DataStore.selectedProxy)
                    ?: throw IllegalStateException("no profile")
                val raw = SpeedTestInstance(entity).doIPGeoLookup(10000)
                val parts = raw.split("|")
                val label = if (parts.size >= 3 && parts[0].isNotBlank()) {
                    parts[0] + " · " + parts[2]
                } else raw
                onMainDispatcher { cardIpValue.text = "\\uD83C\\uDF0D " + label }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                Logs.w(e.toString())
                onMainDispatcher {
                    cardIpValue.text = "\\uD83C\\uDF0D " + app.getString(R.string.card_ip_unknown)
                }
            }
        }
    }

    // %s: Ookla speed test inside card 2 (reuses SpeedTestInstance).
    private fun runCardSpeedtest() {
        if (!::cardSpeedtestValue.isInitialized) return
        if (speedtestJob?.isActive == true) return
        cardSpeedtestBtn.isEnabled = false
        cardSpeedtestValue.text = app.getString(R.string.card_speedtest_testing)
        speedtestJob = runOnDefaultDispatcher {
            try {
                val entity = SagerDatabase.proxyDao.getById(DataStore.selectedProxy)
                    ?: throw IllegalStateException(app.getString(R.string.speedtest_no_profile))
                val instance = SpeedTestInstance(entity)
                onMainDispatcher {
                    cardSpeedtestValue.text = app.getString(R.string.speedtest_selecting)
                }
                val parts = instance.doSelectServer(30000).split("\\n")
                if (parts.size < 3) throw IllegalStateException("bad server info")
                onMainDispatcher {
                    cardSpeedtestValue.text = app.getString(R.string.speedtest_downloading)
                }
                val down = instance.doDownloadTest(parts[0], 30000)
                onMainDispatcher {
                    cardSpeedtestValue.text = "\\u2193 ${"%%.1f".format(down)} Mbps"
                }
                val up = instance.doUploadTest(parts[1], 10, 30000)
                onMainDispatcher {
                    cardSpeedtestValue.text =
                        "\\u2193 ${"%%.1f".format(down)} Mbps  \\u2191 ${"%%.1f".format(up)} Mbps"
                }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                Logs.w(e.toString())
                onMainDispatcher {
                    cardSpeedtestValue.text = app.getString(R.string.speedtest_failed)
                }
            } finally {
                onMainDispatcher { cardSpeedtestBtn.isEnabled = true }
            }
        }
    }

    fun testConnection() {
"""


def patch_statsbar_kt(root):
    path = root + "/" + STATSBAR_KT
    src = _read(path)
    if MARKER in src:
        print("StatsBar.kt already patched, skip")
        return
    for old, name in [
        (STATSBAR_FIELDS_OLD, "fields"),
        (STATSBAR_BIND_OLD, "bind"),
        (STATSBAR_SPEED_OLD, "updateSpeed"),
        (STATSBAR_STATE_OLD, "changeState"),
    ]:
        assert src.count(old) == 1, "StatsBar.kt anchor '%s' not found exactly once" % name
    assert "load_balance_enabled" in _read(root + "/" + STRINGS_EN), \
        "patch_loadbalance_quick.py must run first (load_balance_enabled string)"
    src = src.replace(STATSBAR_IMPORTS_ANCHOR, STATSBAR_IMPORTS_NEW, 1)
    src = src.replace(STATSBAR_FIELDS_OLD, STATSBAR_FIELDS_NEW, 1)
    src = src.replace(STATSBAR_BIND_OLD, STATSBAR_BIND_NEW, 1)
    src = src.replace(STATSBAR_SPEED_OLD, STATSBAR_SPEED_NEW, 1)
    src = src.replace(STATSBAR_STATE_OLD, STATSBAR_STATE_NEW, 1)
    anchor = "    fun testConnection() {\n"
    assert src.count(anchor) == 1, "testConnection anchor not found exactly once"
    src = src.replace(anchor, STATSBAR_NEW_METHODS % (MARKER, MARKER, MARKER, MARKER, MARKER) + anchor, 1)
    _write(path, src)
    print("StatsBar.kt patched OK")


# ---------------------------------------------------------------- Go: ipGeoLookup
IPGEO_GO = """const ipGeoAPI = "http://ip-api.com/json/?fields=status,country,city,query"

// ipGeoLookup queries ip-api.com through client and returns "country|city|ip".
func ipGeoLookup(client *http.Client, timeout int32) (string, error) {
	if client == nil {
		return "", fmt.Errorf("no client")
	}
	defer client.CloseIdleConnections()

	ctx, cancel := context.WithTimeout(context.Background(), time.Duration(timeout)*time.Millisecond)
	defer cancel()

	req, err := http.NewRequestWithContext(ctx, "GET", ipGeoAPI, nil)
	if err != nil {
		return "", err
	}
	req.Header.Set("User-Agent", "Mozilla/5.0")

	resp, err := client.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		return "", fmt.Errorf("ip geo HTTP %d", resp.StatusCode)
	}

	var r struct {
		Status  string `json:"status"`
		Country string `json:"country"`
		City    string `json:"city"`
		Query   string `json:"query"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&r); err != nil {
		return "", err
	}
	if r.Status != "success" {
		return "", fmt.Errorf("ip geo lookup failed")
	}
	return r.Country + "|" + r.City + "|" + r.Query, nil
}
"""

BOX_GO_IPGEO = """
// IPGeoLookup returns "country|city|ip" of the proxy egress via ip-api.com.
// If i is nil, uses mainInstance (or direct if no service running).
func IPGeoLookup(i *BoxInstance, timeout int32) (info string, err error) {
	defer device.DeferPanicToError("box.IPGeoLookup", func(err_ error) { err = err_ })
	var client *http.Client
	if i != nil {
		var connectionTracker adapter.ConnectionTracker
		if i.v2api != nil {
			connectionTracker = i.v2api.StatsService()
		}
		client = boxapi.CreateProxyHttpClient(i.Box, connectionTracker)
	} else if mainInstance == nil {
		client = boxapi.CreateProxyHttpClient(nil, nil)
	} else {
		var connectionTracker adapter.ConnectionTracker
		if mainInstance.v2api != nil {
			connectionTracker = mainInstance.v2api.StatsService()
		}
		client = boxapi.CreateProxyHttpClient(mainInstance.Box, connectionTracker)
	}
	return ipGeoLookup(client, timeout)
}
"""


def patch_go_ipgeo(root):
    path = root + "/" + SPEEDTEST_GO
    src = _read(path)
    if GEO_MARKER in src:
        print("speedtest.go ipgeo already present, skip")
        return
    assert "chanboxSpeedTest" in src, "patch_speedtest.py must run first"
    src = src.rstrip("\n") + "\n\n// " + GEO_MARKER + ": egress IP geolocation through the proxy.\n" + IPGEO_GO
    _write(path, src)
    print("speedtest.go ipgeo appended OK")


def patch_go_box(root):
    path = root + "/" + BOX_GO
    src = _read(path)
    if GEO_MARKER in src:
        print("box.go IPGeoLookup already exported, skip")
        return
    assert "chanboxSpeedTest" in src, "patch_speedtest.py must run first"
    anchor = "var protectCloser io.Closer"
    assert src.count(anchor) == 1, "box.go anchor not found exactly once"
    src = src.replace(anchor, "// " + GEO_MARKER + BOX_GO_IPGEO + "\n" + anchor, 1)
    _write(path, src)
    print("box.go IPGeoLookup exported OK")


# ---------------------------------------------------------------- SpeedTestInstance.kt
INSTANCE_GEO_KT = """    // %s: egress IP + geolocation through this profile's proxy.
    // Returns "country|city|ip".
    suspend fun doIPGeoLookup(timeout: Int): String {
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
                        c.tryResume(Libcore.iPGeoLookup(box, timeout))
                    } catch (e: Exception) {
                        c.tryResumeWithException(e)
                    }
                }
            }
        }
    }

"""


def patch_instance_kt(root):
    path = root + "/" + INSTANCE_KT
    src = _read(path)
    if GEO_MARKER in src:
        print("SpeedTestInstance.kt ipgeo already present, skip")
        return
    assert "chanboxSpeedTest" in src, "patch_speedtest.py must run first"
    anchor = "    override suspend fun loadConfig() {"
    assert src.count(anchor) == 1, "loadConfig anchor not found exactly once"
    src = src.replace(anchor, INSTANCE_GEO_KT % GEO_MARKER + anchor, 1)
    _write(path, src)
    print("SpeedTestInstance.kt doIPGeoLookup added OK")


# ---------------------------------------------------------------- strings
STRINGS_EN_ADD = """    <!-- %s -->
    <string name="card_speed_label">Speed</string>
    <string name="card_lb_label">Load Balance</string>
    <string name="card_lb_on">ON · auto fastest</string>
    <string name="card_lb_off">OFF</string>
    <string name="card_ip_label">Exit IP</string>
    <string name="card_ip_fetching">locating…</string>
    <string name="card_ip_unknown">unknown</string>
    <string name="card_node_label">Node</string>
    <string name="card_speedtest_start">Speed Test</string>
    <string name="card_speedtest_testing">testing…</string>
""" % MARKER

STRINGS_ZH_ADD = """    <!-- %s -->
    <string name="card_speed_label">连接速率</string>
    <string name="card_lb_label">负载均衡</string>
    <string name="card_lb_on">已开启 · 自动选最快</string>
    <string name="card_lb_off">已关闭</string>
    <string name="card_ip_label">IP出口</string>
    <string name="card_ip_fetching">获取中…</string>
    <string name="card_ip_unknown">未知</string>
    <string name="card_node_label">节点配置</string>
    <string name="card_speedtest_start">开始测速</string>
    <string name="card_speedtest_testing">测试中…</string>
""" % MARKER


def _patch_strings(path, anchor_str, addition):
    src = _read(path)
    if MARKER in src:
        print("%s already patched, skip" % path)
        return
    assert src.count(anchor_str) == 1, "strings anchor not found exactly once in %s" % path
    src = src.replace(anchor_str, anchor_str + addition, 1)
    _write(path, src)
    print("%s patched OK" % path)


def patch_strings(root):
    _patch_strings(root + "/" + STRINGS_EN,
                   '    <string name="load_balance">Load Balance</string>\n',
                   STRINGS_EN_ADD)
    _patch_strings(root + "/" + STRINGS_ZH,
                   '    <string name="load_balance">\u8D1F\u8F7D\u5747\u8861</string>\n',
                   STRINGS_ZH_ADD)


# ---------------------------------------------------------------- main
def main():
    root = "."
    patch_layout_main(root)
    patch_fab(root)
    patch_statsbar_kt(root)
    patch_go_ipgeo(root)
    patch_go_box(root)
    patch_instance_kt(root)
    patch_strings(root)
    print("ALL CONFIG-CARDS PATCHES OK")


if __name__ == "__main__":
    main()
