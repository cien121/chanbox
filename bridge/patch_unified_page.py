#!/usr/bin/env python3
"""Unified single page + commercial start button + dual-stack IP display.

- Merges the ZedSecure dashboard (StatsBar) and node list into ONE page:
  dashboard becomes a fixed top header, node list scrolls below it.
- Removes the old NekoBox paper-plane FAB entirely; the dashboard's
  starburst badge (ZedSecure style) is the commercial start button.
- IP egress card shows BOTH IPv4 and IPv6.
- Refreshes the panel gradient to the vibrant ZedSecure reference colors.

Idempotent via marker. Requires patch_config_cards.py (v3) applied first.
"""

import re
import sys

MARKER = "chanboxUnifiedPage"
MARKER_V3 = "chanboxConfigCardsV2"
GEO_MARKER = "chanboxIPGeo"

LAYOUT_MAIN = "app/src/main/res/layout/layout_main.xml"
MAIN_ACTIVITY = "app/src/main/java/io/nekohasekai/sagernet/ui/MainActivity.kt"
STATSBAR_KT = "app/src/main/java/io/nekohasekai/sagernet/widget/StatsBar.kt"
SPEEDTEST_GO = "libcore/speedtest.go"
BOX_GO = "libcore/box.go"
INSTANCE_KT = "app/src/main/java/io/nekohasekai/sagernet/bg/proto/SpeedTestInstance.kt"
DRAWABLE_DIR = "app/src/main/res/drawable"


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _write(path, src):
    with open(path, "w", encoding="utf-8") as f:
        f.write(src)


# ---------------------------------------------------------------- layout_main.xml
def patch_layout_unified(root):
    path = root + "/" + LAYOUT_MAIN
    src = _read(path)
    if MARKER in src:
        print("layout_main.xml already unified, skip")
        return
    assert MARKER_V3 in src, "v3 dashboard patch must be applied first"

    # 1. Extract the StatsBar block (dashboard)
    sb_start = src.index("<io.nekohasekai.sagernet.widget.StatsBar")
    sb_end_tag = "</io.nekohasekai.sagernet.widget.StatsBar>"
    sb_end = src.index(sb_end_tag, sb_start) + len(sb_end_tag)
    statsbar_block = src[sb_start:sb_end]

    # 2. Extract the fragment_holder block
    fh_start = src.index('<androidx.coordinatorlayout.widget.CoordinatorLayout\n            android:id="@+id/fragment_holder"')
    fh_end = src.index("/>", fh_start) + len("/>")
    fh_block = src[fh_start:fh_end]

    # 3. Clean the StatsBar block: remove bottom-overlay attributes
    statsbar_block = statsbar_block.replace(
        '\n            android:layout_gravity="bottom"', "")
    statsbar_block = statsbar_block.replace(
        '\n            app:hideOnScroll="true"', "")
    statsbar_block = statsbar_block.replace(
        '\n            app:layout_scrollFlags="enterAlways|scroll"', "")
    statsbar_block = statsbar_block.replace(
        '\n            android:nextFocusUp="@+id/fab"', "")

    # 4. Build the unified page: dashboard on top, node list below
    unified = (
        '        <!-- ' + MARKER + ': unified single page, dashboard header + node list -->\n'
        '        <LinearLayout\n'
        '            android:layout_width="match_parent"\n'
        '            android:layout_height="match_parent"\n'
        '            android:orientation="vertical">\n\n'
        + _indent_block(statsbar_block, 12) + '\n\n'
        + _indent_block(
            fh_block.replace(
                'android:layout_height="match_parent"',
                'android:layout_height="0dp"\n            android:layout_weight="1"'),
            12)
        + '\n        </LinearLayout>'
    )

    # 5. Replace everything between <CoordinatorLayout coordinator> open tag
    #    and its closing tag's preceding content.
    #    Strategy: find coordinator open, then replace from fragment_holder
    #    start through StatsBar end with the unified block, and drop the
    #    fabProgress + fab blocks.
    coord_open = '<androidx.coordinatorlayout.widget.CoordinatorLayout\n        android:id="@+id/coordinator"'
    ci = src.index(coord_open)
    # find end of coordinator open tag
    ci_end = src.index(">", ci) + 1

    # fabProgress block
    fp_start = src.index('<com.google.android.material.progressindicator.CircularProgressIndicator')
    fp_end = src.index("/>", fp_start) + len("/>")
    # fab block (ServiceButton) - may span multiple lines, ends with />
    fab_start = src.index('<io.nekohasekai.sagernet.widget.ServiceButton')
    fab_end = src.index("/>", fab_start) + len("/>")

    # Reconstruct: coordinator open + unified + coordinator close
    # Find the closing tag of the outer coordinator (last one before nav views)
    # The outer coordinator closes right before the first NavigationView
    nav_start = src.index('<com.google.android.material.navigation.NavigationView')
    # find the last </androidx.coordinatorlayout.widget.CoordinatorLayout> before nav
    close_tag = "</androidx.coordinatorlayout.widget.CoordinatorLayout>"
    co_close = src.rindex(close_tag, ci_end, nav_start) + len(close_tag)

    new_src = (src[:ci_end] + "\n" + unified
               + "\n    </androidx.coordinatorlayout.widget.CoordinatorLayout>"
               + src[co_close:])
    _write(path, new_src)
    print("layout_main.xml unified OK (dashboard top, list below, FAB removed)")


def _indent_block(block, spaces):
    pad = " " * spaces
    lines = block.strip("\n").split("\n")
    return "\n".join(pad + l if l.strip() else l for l in lines)


# ---------------------------------------------------------------- MainActivity.kt
def patch_main_activity_unified(root):
    path = root + "/" + MAIN_ACTIVITY
    src = _read(path)
    if MARKER in src:
        print("MainActivity.kt already unified, skip")
        return

    # 1. Remove fab initProgress
    old = "        binding.fab.initProgress(binding.fabProgress)\n"
    assert src.count(old) == 1, "fab initProgress anchor not found"
    src = src.replace(old, "        // " + MARKER + ": FAB removed, starburst badge is the start control\n", 1)

    # 2. Remove FAB click listener (keep toggleService method for badge)
    old = "        binding.fab.setOnClickListener { toggleService() }\n"
    if src.count(old) == 1:
        src = src.replace(old, "", 1)
        print("  FAB click listener removed")
    else:
        # fallback: try the original pre-v3 listener shape
        old2 = """        binding.fab.setOnClickListener {
            if (DataStore.serviceState.canStop) SagerNet.stopService() else connect.launch(
                null
            )
        }
"""
        if src.count(old2) == 1:
            src = src.replace(old2, "", 1)
            print("  FAB click listener (original) removed")

    # 3. displayFragment: drop fab.show()/fab.hide()
    old = "            binding.fab.show()\n"
    assert src.count(old) == 1, "fab.show anchor not found"
    src = src.replace(old, "", 1)
    old = "            binding.fab.hide()\n"
    assert src.count(old) == 1, "fab.hide anchor not found"
    src = src.replace(old, "", 1)

    # 4. changeState: drop fab.changeState
    old = "        binding.fab.changeState(state, DataStore.serviceState, animate)\n"
    assert src.count(old) == 1, "fab.changeState anchor not found"
    src = src.replace(old, "", 1)

    # 5. snackbarInternal: drop fab anchor block
    old = """            if (binding.fab.isShown) {
                anchorView = binding.fab
            }
"""
    assert src.count(old) == 1, "snackbar fab anchor not found"
    src = src.replace(old, "", 1)

    # 6. marker comment at top of onCreate region
    src = src.replace(
        "        // " + MARKER + ": FAB removed, starburst badge is the start control\n",
        "        // " + MARKER + ": FAB removed, starburst badge is the start control\n",
        1)

    _write(path, src)
    print("MainActivity.kt unified OK (FAB refs removed)")


# ---------------------------------------------------------------- Layouts.kt (FAB scroll behavior)
LAYOUTS_KT = "app/src/main/java/io/nekohasekai/sagernet/ktx/Layouts.kt"


def patch_layouts_kt(root):
    path = root + "/" + LAYOUTS_KT
    src = _read(path)
    if MARKER in src:
        print("Layouts.kt already unified, skip")
        return
    # The custom LayoutManager hides/shows the FAB on overscroll. FAB is gone;
    # simplify to just return scrollRange.
    start_anchor = "        val overscroll = dx - scrollRange"
    assert src.count(start_anchor) == 1, "overscroll anchor not found"
    i = src.index(start_anchor)
    # find "        return scrollRange" after the anchor (end of the if/else)
    end_anchor = "        return scrollRange\n    }"
    j = src.index(end_anchor, i) + len("        return scrollRange")
    replacement = (
        "        // " + MARKER + ": FAB removed; no hide/show on scroll needed.\n"
        "        return scrollRange"
    )
    src = src[:i] + replacement + src[j:]
    _write(path, src)
    print("Layouts.kt unified OK (FAB scroll logic removed)")


# ---------------------------------------------------------------- FixedGridLayoutManager.kt (FAB scroll behavior)
GRID_KT = "app/src/main/java/io/nekohasekai/sagernet/ktx/FixedGridLayoutManager.kt"


def patch_fixed_grid_layout_manager(root):
    path = root + "/" + GRID_KT
    src = _read(path)
    if MARKER in src:
        print("FixedGridLayoutManager.kt already unified, skip")
        return
    # Same treatment as Layouts.kt: the custom grid LayoutManager (added by
    # patch_two_column.py) hides/shows the FAB on overscroll, but the FAB is
    # gone in the unified page. Simplify scrollVerticallyBy to just delegate.
    sig = "    override fun scrollVerticallyBy("
    assert src.count(sig) == 1, "scrollVerticallyBy anchor not found"
    i = src.index(sig)
    # end of the function: first 4-space-indent closing brace after the signature
    end_anchor = "\n    }\n"
    j = src.index(end_anchor, i) + 1  # j points at the "}" of the function
    replacement = (
        "    override fun scrollVerticallyBy(\n"
        "        dx: Int, recycler: RecyclerView.Recycler,\n"
        "        state: RecyclerView.State\n"
        "    ): Int {\n"
        "        // " + MARKER + ": FAB removed; no hide/show on scroll needed.\n"
        "        return super.scrollVerticallyBy(dx, recycler, state)\n"
    )
    src = src[:i] + replacement + src[j:]
    # refresh the stale header comment (FAB behavior is gone)
    old_comment = ("// Same IndexOutOfBoundsException guard and FAB "
                   "hide/show-on-scroll behavior.")
    if old_comment in src:
        src = src.replace(
            old_comment,
            "// Same IndexOutOfBoundsException guard. FAB scroll behavior "
            "removed by " + MARKER + ".", 1)
    _write(path, src)
    print("FixedGridLayoutManager.kt unified OK (FAB scroll logic removed)")


# ---------------------------------------------------------------- Go: dual-stack IP
DUALSTACK_GO = """
// """ + "chanboxUnifiedPage" + """: query both IPv4 and IPv6 egress addresses.
func ipDualStackLookup(client *http.Client, timeout int32) (string, error) {
\tif client == nil {
\t\treturn "|", fmt.Errorf("no client")
\t}
\tdefer client.CloseIdleConnections()

\tfetch := func(url string) string {
\t\tctx, cancel := context.WithTimeout(context.Background(), time.Duration(timeout)*time.Millisecond)
\t\tdefer cancel()
\t\treq, err := http.NewRequestWithContext(ctx, "GET", url, nil)
\t\tif err != nil {
\t\t\treturn ""
\t\t}
\t\treq.Header.Set("User-Agent", "Mozilla/5.0")
\t\tresp, err := client.Do(req)
\t\tif err != nil {
\t\t\treturn ""
\t\t}
\t\tdefer resp.Body.Close()
\t\tif resp.StatusCode != 200 {
\t\t\treturn ""
\t\t}
\t\tvar r struct {
\t\t\tIP string `json:"ip"`
\t\t}
\t\tif err := json.NewDecoder(resp.Body).Decode(&r); err != nil {
\t\t\treturn ""
\t\t}
\t\treturn strings.TrimSpace(r.IP)
\t}

\tipv4 := fetch("https://api.ipify.org?format=json")
\tipv6 := fetch("https://api6.ipify.org?format=json")
\t// api6 may fall back to v4; drop it if identical
\tif ipv6 == ipv4 {
\t\tipv6 = ""
\t}
\treturn ipv4 + "|" + ipv6, nil
}
"""

BOX_GO_DUALSTACK = """
// EgressDualStackLookup returns "ipv4|ipv6" of the proxy egress (empty side if unavailable).
func EgressDualStackLookup(i *BoxInstance, timeout int32) (info string, err error) {
\tdefer device.DeferPanicToError("box.EgressDualStackLookup", func(err_ error) { err = err_ })
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
\treturn ipDualStackLookup(client, timeout)
}
"""


def patch_go_dualstack(root):
    path = root + "/" + SPEEDTEST_GO
    src = _read(path)
    if MARKER + ":dualstack" in src:
        print("speedtest.go dualstack already present, skip")
    else:
        assert GEO_MARKER in src, "ipgeo patch must run first"
        src = src.rstrip("\n") + "\n" + DUALSTACK_GO
        _write(path, src)
        print("speedtest.go dualstack appended OK")

    path = root + "/" + BOX_GO
    src = _read(path)
    if MARKER + ":dualstack" in src:
        print("box.go dualstack already exported, skip")
        return
    anchor = "var protectCloser io.Closer"
    assert src.count(anchor) == 1, "box.go anchor not found"
    src = src.replace(
        anchor,
        "// " + MARKER + ":dualstack\n" + BOX_GO_DUALSTACK + "\n" + anchor, 1)
    _write(path, src)
    print("box.go EgressDualStackLookup exported OK")


# ---------------------------------------------------------------- SpeedTestInstance.kt
INSTANCE_DUALSTACK_KT = """    // chanboxUnifiedPage:dualstack egress IPv4 + IPv6 through this profile's proxy.
    // Returns "ipv4|ipv6" (empty side if unavailable).
    suspend fun doIPDualStackLookup(timeout: Int): String {
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
                        c.tryResume(Libcore.egressDualStackLookup(box, timeout))
                    } catch (e: Exception) {
                        c.tryResumeWithException(e)
                    }
                }
            }
        }
    }

"""


def patch_instance_dualstack(root):
    path = root + "/" + INSTANCE_KT
    src = _read(path)
    if MARKER + ":dualstack" in src:
        print("SpeedTestInstance.kt dualstack already present, skip")
        return
    assert "chanboxSpeedTest" in src, "patch_speedtest.py must run first"
    anchor = "    // " + GEO_MARKER + ": egress IP + geolocation through this profile's proxy."
    assert src.count(anchor) == 1, "geo anchor not found"
    src = src.replace(anchor, INSTANCE_DUALSTACK_KT + anchor, 1)
    _write(path, src)
    print("SpeedTestInstance.kt doIPDualStackLookup added OK")


# ---------------------------------------------------------------- StatsBar.kt: show IPv6
def patch_statsbar_dualstack(root):
    path = root + "/" + STATSBAR_KT
    src = _read(path)
    if MARKER + ":dualstack" in src:
        print("StatsBar.kt dualstack display already present, skip")
        return
    assert MARKER_V3 in src, "v3 patch must be applied first"

    # 1. Add an IPv6 TextView under the location value in the dashboard XML.
    #    The dashboard inner XML lives inside patch_config_cards.py's DASHBOARD_INNER,
    #    but at CI time it's already materialized in layout_main.xml. Patch it there.
    lpath = root + "/" + LAYOUT_MAIN
    lsrc = _read(lpath)
    v6_view = (
        '                        <TextView\n'
        '                            android:id="@+id/card_loc_ipv6"\n'
        '                            android:layout_width="wrap_content"\n'
        '                            android:layout_height="wrap_content"\n'
        '                            android:ellipsize="middle"\n'
        '                            android:maxLines="1"\n'
        '                            android:textColor="#B0BEC5"\n'
        '                            android:textSize="11sp"\n'
        '                            android:visibility="gone"\n'
        '                            tools:text="IPv6 \\u00B7 2001:db8::1" />\n'
    )
    anchor = '                            android:text="@string/card_loc_title"\n'
    assert lsrc.count(anchor) == 1, "loc title anchor not found in layout_main.xml"
    # insert the ipv6 view right before the title TextView's parent close:
    # the title TextView is the last child of the vertical LinearLayout;
    # insert before it.
    title_tv_start = lsrc.index(anchor)
    # find start of that TextView element
    tv_start = lsrc.rindex("<TextView", 0, title_tv_start)
    lsrc = lsrc[:tv_start] + v6_view + lsrc[tv_start:]
    _write(lpath, lsrc)
    print("layout_main.xml IPv6 TextView added OK")

    # 2. StatsBar.kt: bind the view + fetch dual-stack on geo refresh.
    # Find the view-binding block from v3.
    bind_anchor = "        cardLocValue = findViewById(R.id.card_loc_value)"
    assert src.count(bind_anchor) == 1, "view binding anchor not found"
    src = src.replace(
        bind_anchor,
        "        cardLocIpv6 = findViewById(R.id.card_loc_ipv6)\n" + bind_anchor, 1)

    # field declaration: find cardLocValue field
    fdecl = "    private lateinit var cardLocValue: TextView"
    assert src.count(fdecl) == 1, "field decl anchor not found"
    src = src.replace(
        fdecl,
        "    private lateinit var cardLocIpv6: TextView\n" + fdecl, 1)

    # 3. Ensure ProxyEntity import exists.
    imp_anchor = "import io.nekohasekai.sagernet.database.DataStore"
    assert src.count(imp_anchor) >= 1, "DataStore import anchor not found"
    if "import io.nekohasekai.sagernet.database.ProxyEntity" not in src:
        src = src.replace(
            imp_anchor,
            imp_anchor + "\nimport io.nekohasekai.sagernet.database.ProxyEntity", 1)

    # 4. Add refreshDualStackIp helper before refreshIPGeo, and call it
    #    inside refreshIPGeo after the geo lookup succeeds.
    geo_anchor = "    // " + MARKER_V3 + ": egress IP geolocation through the current profile's proxy.\n    private fun refreshIPGeo() {"
    assert src.count(geo_anchor) == 1, "refreshIPGeo anchor not found"
    helper = (
        "    // " + MARKER + ":dualstack fetch IPv4+IPv6 egress and show both.\n"
        "    private fun refreshDualStackIp(entity: ProxyEntity) {\n"
        "        runOnDefaultDispatcher {\n"
        "            try {\n"
        "                val raw = SpeedTestInstance(entity).doIPDualStackLookup(8000)\n"
        "                val parts = raw.split(\"|\")\n"
        "                val v6 = parts.getOrElse(1) { \"\" }\n"
        "                onMainDispatcher {\n"
        "                    if (!::cardLocIpv6.isInitialized) return@onMainDispatcher\n"
        "                    if (v6.isNotEmpty()) {\n"
        "                        cardLocIpv6.text = \"IPv6 \\u00B7 \" + v6\n"
        "                        cardLocIpv6.visibility = View.VISIBLE\n"
        "                    } else {\n"
        "                        cardLocIpv6.visibility = View.GONE\n"
        "                    }\n"
        "                }\n"
        "            } catch (_: Exception) { }\n"
        "        }\n"
        "    }\n\n"
        + geo_anchor
    )
    src = src.replace(geo_anchor, helper, 1)

    # 4. Call refreshDualStackIp inside refreshIPGeo after entity is fetched.
    call_site = "                val raw = SpeedTestInstance(entity).doIPGeoLookup(10000)"
    assert src.count(call_site) == 1, "geo lookup call site not found"
    src = src.replace(
        call_site,
        call_site + "\n                refreshDualStackIp(entity)", 1)
    _write(path, src)
    print("StatsBar.kt dualstack display wired OK")


# ---------------------------------------------------------------- StatsBar.kt: no hide/show (top header)
def patch_statsbar_nohide(root):
    path = root + "/" + STATSBAR_KT
    src = _read(path)
    if MARKER + ":nohide" in src:
        print("StatsBar.kt nohide already applied, skip")
        return
    # changeState: don't hide the bar when disconnected; it's a top header now.
    old = """        if ((state == BaseService.State.Connected).also { hideOnScroll = it }) {
            postWhenStarted {
                if (allowShow) performShow()
                setStatus(app.getText(R.string.vpn_connected))"""
    assert src.count(old) == 1, "changeState connected anchor not found"
    new = """        // """ + MARKER + """:nohide top header stays visible; no hide/show.
        if (state == BaseService.State.Connected) {
            postWhenStarted {
                setStatus(app.getText(R.string.vpn_connected))"""
    src = src.replace(old, new, 1)

    old = """        } else {
            postWhenStarted {
                performHide()
            }
            ipGeoJob?.cancel()"""
    assert src.count(old) == 1, "changeState disconnected anchor not found"
    new = """        } else {
            ipGeoJob?.cancel()"""
    src = src.replace(old, new, 1)
    _write(path, src)
    print("StatsBar.kt nohide applied OK")


# ---------------------------------------------------------------- vibrant ZedSecure gradient
GRADIENT_VIBRANT = """<?xml version="1.0" encoding="utf-8"?>
<!-- {M}: vibrant ZedSecure purple-blue gradient panel background -->
<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle">
    <gradient
        android:angle="135"
        android:startColor="#4B2E9E"
        android:centerColor="#24478F"
        android:endColor="#0B0B0F" />
    <corners android:topLeftRadius="24dp" android:topRightRadius="24dp" />
</shape>
"""


def patch_gradient(root):
    import os
    path = root + "/" + DRAWABLE_DIR + "/bg_panel_gradient.xml"
    src = _read(path)
    if MARKER in src:
        print("bg_panel_gradient.xml already vibrant, skip")
        return
    assert MARKER_V3 in src, "v3 gradient must exist first"
    _write(path, GRADIENT_VIBRANT.format(M=MARKER))
    print("bg_panel_gradient.xml refreshed to vibrant ZedSecure colors OK")


# ---------------------------------------------------------------- main
def main():
    root = "."
    patch_layout_unified(root)
    patch_main_activity_unified(root)
    patch_layouts_kt(root)
    patch_fixed_grid_layout_manager(root)
    patch_go_dualstack(root)
    patch_instance_dualstack(root)
    patch_statsbar_dualstack(root)
    patch_statsbar_nohide(root)
    patch_gradient(root)
    print("ALL UNIFIED-PAGE PATCHES OK")


if __name__ == "__main__":
    main()
