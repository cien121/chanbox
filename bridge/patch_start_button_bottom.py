#!/usr/bin/env python3
"""Move start button to bottom + bottom nav bar with key entries.

User requests (2026-10-06):
- "启动键放在最下面": move the VPN start button (starburst badge) from the
  dashboard center to the very bottom of the screen.
- "菜单键也独立出来，放在最下面（和启动键一起在底部）": menu button also
  independent at the bottom together with the start button.
- "把几个关键入口——配置、路由、设置、分组——都摊开显示，不要藏在菜单里":
  lay out key entries (Configuration, Routes, Groups, Settings) openly in the
  bottom bar instead of hiding them in menus.
- "节点信息（节点卡片列表）放在上面，样式紧凑缩小些": move the node list
  above the dashboard (dashboard relocated below fragment_holder) and make
  node cards compact.
- "节点名显示一行，不要换行分成两排（长名字用省略号）": node names are
  single-line with end ellipsis.

Layout (bottom bar, horizontal):
  [menu] [配置] [路由] [ badge 116dp ] [分组] [设置]
Nav buttons use a compact small style (20dp icon, 9sp label).

- Menu button opens the navigation drawer.
- 配置/路由/分组/设置 call MainActivity.displayFragmentWithId() with the same
  nav ids as the drawer menu.
- The starburst badge keeps its timer / on-off / connecting visuals; its views
  are now bound activity-scoped in StatsBar (they live outside StatsBar).

Idempotent via marker. Requires patch_unified_page.py applied first.
"""

import re
import sys

MARKER = "chanboxStartButtonBottom"
UNIFIED_MARKER = "chanboxUnifiedPage"

LAYOUT_MAIN = "app/src/main/res/layout/layout_main.xml"
MAIN_ACTIVITY = "app/src/main/java/io/nekohasekai/sagernet/ui/MainActivity.kt"
STATSBAR_KT = "app/src/main/java/io/nekohasekai/sagernet/widget/StatsBar.kt"
STRINGS_EN = "app/src/main/res/values/strings.xml"
STRINGS_ZH = "app/src/main/res/values-zh-rCN/strings.xml"


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _write(path, src):
    with open(path, "w", encoding="utf-8") as f:
        f.write(src)


def _nav_item(item_id, icon, label_ref):
    return (
        '            <LinearLayout\n'
        f'                android:id="@+id/{item_id}"\n'
        '                android:layout_width="0dp"\n'
        '                android:layout_height="wrap_content"\n'
        '                android:layout_weight="1"\n'
        '                android:clickable="true"\n'
        '                android:focusable="true"\n'
        '                android:background="@drawable/bg_bottom_nav_item"\n'
        '                android:gravity="center_horizontal"\n'
        '                android:orientation="vertical"\n'
        '                android:paddingTop="4dp"\n'
        '                android:paddingBottom="4dp">\n\n'
        '                <FrameLayout\n'
        f'                    android:id="@+id/{item_id}_pill"\n'
        '                    android:layout_width="44dp"\n'
        '                    android:layout_height="28dp"\n'
        '                    android:background="@drawable/bg_nav_pill">\n\n'
        '                    <ImageView\n'
        f'                        android:id="@+id/{item_id}_icon"\n'
        '                        android:layout_width="20dp"\n'
        '                        android:layout_height="20dp"\n'
        '                        android:layout_gravity="center"\n'
        f'                        android:src="{icon}"\n'
        '                        android:tint="#9E9E9E" />\n'
        '                </FrameLayout>\n\n'
        '                <TextView\n'
        f'                    android:id="@+id/{item_id}_label"\n'
        '                    android:layout_width="wrap_content"\n'
        '                    android:layout_height="wrap_content"\n'
        '                    android:layout_marginTop="2dp"\n'
        f'                    android:text="{label_ref}"\n'
        '                    android:textColor="#9E9E9E"\n'
        '                    android:textSize="9sp" />\n'
        '            </LinearLayout>\n'
    )


BOTTOM_BAR = (
    '        <!-- ' + MARKER + ': bottom bar - menu + key entries + start badge -->\n'
    '        <LinearLayout\n'
    '            android:id="@+id/bottom_bar"\n'
    '            android:layout_width="match_parent"\n'
    '            android:layout_height="wrap_content"\n'
    '            android:background="#0B0B0F"\n'
    '            android:gravity="center_vertical"\n'
    '            android:orientation="horizontal"\n'
    '            android:paddingStart="4dp"\n'
    '            android:paddingTop="8dp"\n'
    '            android:paddingEnd="4dp"\n'
    '            android:paddingBottom="10dp">\n\n'
    + _nav_item("bottom_nav_menu", "@drawable/ic_navigation_menu", "@string/bottom_menu_label")
    + '\n'
    + _nav_item("bottom_nav_config", "@drawable/ic_action_description", "@string/menu_configuration")
    + '\n'
    + _nav_item("bottom_nav_route", "@drawable/ic_maps_directions", "@string/menu_route")
    + '\n'
    '            <LinearLayout\n'
    '                android:layout_width="wrap_content"\n'
    '                android:layout_height="wrap_content"\n'
    '                android:gravity="center_horizontal"\n'
    '                android:orientation="vertical"\n'
    '                android:paddingStart="6dp"\n'
    '                android:paddingEnd="6dp">\n\n'
    '                <FrameLayout\n'
    '                    android:layout_width="wrap_content"\n'
    '                    android:layout_height="wrap_content">\n\n'
    '                    <View\n'
    '                        android:id="@+id/card_badge_bg"\n'
    '                        android:layout_width="116dp"\n'
    '                        android:layout_height="116dp"\n'
    '                        android:background="@drawable/bg_badge_off" />\n\n'
    '                    <LinearLayout\n'
    '                        android:id="@+id/card_badge"\n'
    '                        android:layout_width="116dp"\n'
    '                        android:layout_height="116dp"\n'
    '                        android:clickable="true"\n'
    '                        android:focusable="true"\n'
    '                        android:gravity="center"\n'
    '                        android:orientation="vertical">\n\n'
    '                        <TextView\n'
    '                            android:id="@+id/card_timer"\n'
    '                            android:layout_width="wrap_content"\n'
    '                            android:layout_height="wrap_content"\n'
    '                            android:text="00:00"\n'
    '                            android:textColor="#FFFFFF"\n'
    '                            android:textSize="26sp"\n'
    '                            android:textStyle="bold" />\n'
    '                    </LinearLayout>\n'
    '                </FrameLayout>\n\n'
    '                <TextView\n'
    '                    android:id="@+id/card_badge_state"\n'
    '                    android:layout_width="wrap_content"\n'
    '                    android:layout_height="wrap_content"\n'
    '                    android:layout_marginTop="4dp"\n'
    '                    android:text="@string/card_badge_disconnected"\n'
    '                    android:textColor="#9E9E9E"\n'
    '                    android:textSize="12sp"\n'
    '                    android:textStyle="bold" />\n'
    '            </LinearLayout>\n\n'
    + _nav_item("bottom_nav_group", "@drawable/ic_baseline_view_list_24", "@string/menu_group")
    + '\n'
    + _nav_item("bottom_nav_settings", "@drawable/ic_action_settings", "@string/settings")
    + '        </LinearLayout>\n'
)


def patch_layout(root):
    path = root + "/" + LAYOUT_MAIN
    src = _read(path)
    if MARKER in src:
        print("layout_main.xml bottom bar already present, skip")
        return
    assert UNIFIED_MARKER in src, "patch_unified_page.py must run first"

    # 1. Remove the badge block from the dashboard.
    badge_start = src.index("<!-- center badge = connect toggle -->")
    state_id = src.index('android:id="@+id/card_badge_state"', badge_start)
    badge_end = src.index("/>", state_id) + len("/>")
    # also swallow the trailing newline after the TextView
    if src[badge_end:badge_end + 1] == "\n":
        badge_end += 1
    # swallow leading whitespace/newlines of the comment line
    line_start = src.rindex("\n", 0, badge_start) + 1
    src = src[:line_start] + src[badge_end:]
    print("  dashboard badge block removed")

    # 2. Insert the bottom bar after fragment_holder, before the LinearLayout close.
    anchor = 'android:layout_weight="1" />\n        </LinearLayout>'
    assert src.count(anchor) == 1, "fragment_holder anchor not unique/found"
    src = src.replace(anchor, 'android:layout_weight="1" />\n' + BOTTOM_BAR + '        </LinearLayout>', 1)
    _write(path, src)
    print("layout_main.xml bottom bar added OK")

    # 3. Relocate dashboard below node list ("节点列表放在上面").
    # Extract the dashboard LinearLayout out of StatsBar; StatsBar becomes a
    # 0dp anchor (kept for binding.stats references). Dashboard is inserted
    # between fragment_holder and the bottom bar.
    src = _read(path)
    dash_marker = "<!-- chanboxConfigCardsV2: ZedSecure-style dashboard -->"
    assert src.count(dash_marker) == 1, "dashboard marker not found"
    dash_start = src.rindex("\n", 0, src.index(dash_marker)) + 1
    stats_close = "</io.nekohasekai.sagernet.widget.StatsBar>"
    assert src.count(stats_close) == 1, "StatsBar close not found"
    dash_end = src.rindex("</LinearLayout>", 0, src.index(stats_close)) + len("</LinearLayout>")
    dashboard = src[dash_start:dash_end]
    src = src[:dash_start] + src[dash_end:]
    # StatsBar -> empty 0dp anchor
    i = src.index("<io.nekohasekai.sagernet.widget.StatsBar")
    j = src.index(">", i) + 1
    k = src.index(stats_close, j) + len(stats_close)
    new_stats = (
        "<!-- " + MARKER + ":dashboardtop dashboard relocated below node list; StatsBar kept as 0dp anchor -->\n"
        "            <io.nekohasekai.sagernet.widget.StatsBar\n"
        '                        android:id="@+id/stats"\n'
        '                        android:layout_width="match_parent"\n'
        '                        android:layout_height="0dp"\n'
        '                        android:minHeight="0dp" />'
    )
    src = src[:i] + new_stats + src[k:]
    # insert dashboard between fragment_holder and bottom bar
    anchor = 'android:layout_weight="1" />\n        <!-- ' + MARKER + ': bottom bar'
    assert src.count(anchor) == 1, "bottom bar anchor not found"
    dashboard_tagged = (
        "        <!-- " + MARKER + ":dashboardtop dashboard panel below node list -->\n"
        + dashboard.replace(
            "<LinearLayout\n",
            '<LinearLayout\n                            android:id="@+id/dashboard_panel"\n',
            1)
        + "\n"
    )
    src = src.replace(
        anchor,
        'android:layout_weight="1" />\n' + dashboard_tagged + '        <!-- ' + MARKER + ': bottom bar',
        1)
    _write(path, src)
    print("layout_main.xml dashboard relocated below node list OK")

    # refined bottom nav drawables (overwrite is idempotent)
    res = root + "/app/src/main/res"
    _write(res + "/drawable/bg_bottom_nav_item.xml",
           '<?xml version="1.0" encoding="utf-8"?>\n'
           '<!-- ' + MARKER + ': rounded ripple for bottom nav items -->\n'
           '<ripple xmlns:android="http://schemas.android.com/apk/res/android"\n'
           '    android:color="#28FFFFFF">\n'
           '    <item android:id="@android:id/mask">\n'
           '        <shape android:shape="rectangle">\n'
           '            <corners android:radius="16dp" />\n'
           '            <solid android:color="#FFFFFF" />\n'
           '        </shape>\n'
           '    </item>\n'
           '    <item>\n'
           '        <shape android:shape="rectangle">\n'
           '            <corners android:radius="16dp" />\n'
           '            <solid android:color="@android:color/transparent" />\n'
           '        </shape>\n'
           '    </item>\n'
           '</ripple>\n')
    _write(res + "/drawable/bg_nav_pill.xml",
           '<?xml version="1.0" encoding="utf-8"?>\n'
           '<!-- ' + MARKER + ': icon pill behind selected bottom nav entry -->\n'
           '<shape xmlns:android="http://schemas.android.com/apk/res/android"\n'
           '    android:shape="rectangle">\n'
           '    <corners android:radius="18dp" />\n'
           '    <solid android:color="@android:color/transparent" />\n'
           '</shape>\n')
    print("bottom nav drawables written OK")


def patch_statsbar(root):
    path = root + "/" + STATSBAR_KT
    src = _read(path)
    if MARKER in src:
        print("StatsBar.kt bottom-bar bindings already present, skip")
        return

    # Badge views now live in the bottom bar (activity layout), not inside
    # StatsBar. They can only be bound AFTER setContentView, so binding moves
    # to a dedicated bindBottomBadge() called from MainActivity.onCreate.
    old = """        cardTimer = findViewById(R.id.card_timer)
        cardBadgeState = findViewById(R.id.card_badge_state)
        cardBadgeBg = findViewById(R.id.card_badge_bg)"""
    assert src.count(old) == 1, "badge binding anchor not found"
    src = src.replace(old, "", 1)

    old = """        findViewById<View>(R.id.card_badge)?.setOnClickListener {
            (context as MainActivity).toggleService()
        }
"""
    assert src.count(old) == 1, "badge click anchor not found"
    src = src.replace(old, "", 1)

    # add bindBottomBadge() before setStatus
    old = "    private fun setStatus(text: CharSequence) {"
    assert src.count(old) == 1, "setStatus anchor not found"
    new = (
        "    // " + MARKER + ": badge lives in bottom bar (activity layout).\n"
        "    // Must be called after setContentView.\n"
        "    fun bindBottomBadge() {\n"
        "        val act = context as MainActivity\n"
        "        cardTimer = act.findViewById(R.id.card_timer)\n"
        "        cardBadgeState = act.findViewById(R.id.card_badge_state)\n"
        "        cardBadgeBg = act.findViewById(R.id.card_badge_bg)\n"
        "        act.findViewById<View>(R.id.card_badge)?.setOnClickListener {\n"
        "            act.toggleService()\n"
        "        }\n"
        "    }\n\n"
        + old
    )
    src = src.replace(old, new, 1)
    _write(path, src)
    print("StatsBar.kt bindBottomBadge added OK")


PROFILE_ITEM = "app/src/main/res/layout/layout_profile.xml"


def patch_statsbar_dashboard_binding(root):
    """Dashboard moved out of StatsBar: bind it activity-scoped.

    setOnClickListener runs from MainActivity.onCreate after setContentView,
    so activity.findViewById is safe here (same pattern as bindBottomBadge).
    """
    path = root + "/" + STATSBAR_KT
    src = _read(path)
    if MARKER + ":dashboardtop" in src:
        print("StatsBar.kt dashboard bindings already activity-scoped, skip")
        return

    old = ("    override fun setOnClickListener(l: OnClickListener?) {\n"
           "        statusText = findViewById(R.id.status)")
    assert src.count(old) == 1, "setOnClickListener anchor not found"
    new = ("    override fun setOnClickListener(l: OnClickListener?) {\n"
           "        // " + MARKER + ":dashboardtop dashboard lives in activity layout now.\n"
           "        val act = context as MainActivity\n"
           "        statusText = act.findViewById(R.id.status)")
    src = src.replace(old, new, 1)

    for rid, var in [
        ("card_loc_ipv6", "cardLocIpv6"),
        ("card_loc_value", "cardLocValue"),
        ("card_ping_value", "cardPingValue"),
        ("card_down_speed", "cardDownSpeed"),
        ("card_down_total", "cardDownTotal"),
        ("card_down_bar", "cardDownBar"),
        ("card_up_speed", "cardUpSpeed"),
        ("card_up_total", "cardUpTotal"),
        ("card_up_bar", "cardUpBar"),
        ("card_lb_value", "cardLbValue"),
        ("card_node_name", "cardNodeName"),
        ("card_node_detail", "cardNodeDetail"),
        ("card_speedtest_btn", "cardSpeedtestBtn"),
        ("card_speedtest_value", "cardSpeedtestValue"),
    ]:
        old = f"        {var} = findViewById(R.id.{rid})"
        assert src.count(old) == 1, f"{rid} binding anchor not found"
        src = src.replace(old, f"        {var} = act.findViewById(R.id.{rid})", 1)

    for rid in ("card_loc_row", "card_lb_row"):
        old = f"        findViewById<View>(R.id.{rid})"
        assert src.count(old) == 1, f"{rid} click anchor not found"
        src = src.replace(old, f"        act.findViewById<View>(R.id.{rid})", 1)

    _write(path, src)
    print("StatsBar.kt dashboard bindings activity-scoped OK")


def patch_profile_item(root):
    """Compact node cards: single-line ellipsis name, tighter padding."""
    path = root + "/" + PROFILE_ITEM
    src = _read(path)
    if MARKER + ":profilecompact" in src:
        print("layout_profile.xml already compact, skip")
        return

    # marker comment after XML declaration
    old = "?>"
    assert src.count(old) == 1, "xml declaration anchor not found"
    src = src.replace(old, "?>\n<!-- " + MARKER + ":profilecompact compact node cards, single-line ellipsis name -->", 1)

    # tighter card margin
    old = '    android:layout_margin="4dp"\n'
    assert src.count(old) == 1, "card margin anchor not found"
    src = src.replace(old, '    android:layout_margin="3dp"\n', 1)

    # name: single line with ellipsis, fill available width
    old = ('                        android:id="@+id/profile_name"\n'
           '                        android:layout_width="wrap_content"\n'
           '                        android:layout_height="wrap_content"\n'
           '                        android:textAppearance="?android:attr/textAppearanceSmall"')
    assert src.count(old) == 1, "profile_name anchor not found"
    new = ('                        android:id="@+id/profile_name"\n'
           '                        android:layout_width="0dp"\n'
           '                        android:layout_height="wrap_content"\n'
           '                        android:layout_weight="1"\n'
           '                        android:ellipsize="end"\n'
           '                        android:maxLines="1"\n'
           '                        android:scrollHorizontally="true"\n'
           '                        android:textAppearance="?android:attr/textAppearanceSmall"')
    src = src.replace(old, new, 1)

    # tighter name-row padding
    old = ('                    android:paddingLeft="12dp"\n'
           '                    android:paddingTop="8dp"\n'
           '                    android:paddingBottom="8dp">')
    assert src.count(old) == 1, "name row padding anchor not found"
    new = ('                    android:paddingLeft="10dp"\n'
           '                    android:paddingTop="6dp"\n'
           '                    android:paddingBottom="6dp">')
    src = src.replace(old, new, 1)

    # smaller icon touch padding (edit / share / remove)
    assert src.count('android:padding="12dp"') == 3, "icon padding count changed"
    src = src.replace('android:padding="12dp"', 'android:padding="8dp"')

    # tighter bottom rows
    old = '                android:paddingBottom="12dp">'
    assert src.count(old) == 1, "bottom row padding anchor not found"
    src = src.replace(old, '                android:paddingBottom="8dp">', 1)

    _write(path, src)
    print("layout_profile.xml compact node cards OK")


def patch_main_activity(root):
    path = root + "/" + MAIN_ACTIVITY
    src = _read(path)
    if MARKER in src:
        print("MainActivity.kt bottom nav already wired, skip")
        return

    # import GravityCompat for drawer open
    old = "import androidx.core.content.ContextCompat\n"
    assert src.count(old) == 1, "ContextCompat import anchor not found"
    src = src.replace(old, old + "import androidx.core.view.GravityCompat\n", 1)

    # wire bottom bar buttons next to the stats click wiring
    old = "        binding.stats.setOnClickListener { if (DataStore.serviceState.connected) binding.stats.testConnection() }\n"
    assert src.count(old) == 1, "stats click anchor not found"
    new = old + (
        "        // " + MARKER + ": bottom bar - menu + key entries laid out openly.\n"
        "        binding.bottomNavMenu.setOnClickListener {\n"
        "            binding.drawerLayout.openDrawer(GravityCompat.START)\n"
        "        }\n"
        "        binding.bottomNavConfig.setOnClickListener { displayFragmentWithId(R.id.nav_configuration) }\n"
        "        binding.bottomNavRoute.setOnClickListener { displayFragmentWithId(R.id.nav_route) }\n"
        "        binding.bottomNavGroup.setOnClickListener { displayFragmentWithId(R.id.nav_group) }\n"
        "        binding.bottomNavSettings.setOnClickListener { displayFragmentWithId(R.id.nav_settings) }\n"
    )
    src = src.replace(old, new, 1)

    # bind the bottom badge AFTER setContentView (activity findViewById needs it)
    old = "        setContentView(binding.root)\n"
    assert src.count(old) == 1, "setContentView anchor not found"
    new = old + "        binding.stats.bindBottomBadge() // " + MARKER + "\n"
    src = src.replace(old, new, 1)

    # dashboard only visible on the home (node list) page, as before relocation
    old = "        supportFragmentManager.beginTransaction()\n"
    assert src.count(old) == 1, "displayFragment anchor not found"
    new = (
        "        // " + MARKER + ":dashboardtop dashboard only on home (node list) page.\n"
        "        findViewById<android.view.View>(R.id.dashboard_panel)?.visibility =\n"
        "            if (fragment is ConfigurationFragment) android.view.View.VISIBLE else android.view.View.GONE\n"
        + old
    )
    src = src.replace(old, new, 1)
    _write(path, src)
    print("MainActivity.kt bottom nav wired OK")


DRAWER_MENU = "app/src/main/res/menu/main_drawer_menu.xml"


def patch_drawer_menu(root):
    """Remove Logs/Tools entries from the drawer entirely (user request)."""
    path = root + "/" + DRAWER_MENU
    src = _read(path)
    if MARKER in src:
        print("main_drawer_menu.xml log/tools already removed, skip")
        return

    old_logcat = """        <item
            android:id="@+id/nav_logcat"
            android:icon="@drawable/ic_baseline_bug_report_24"
            android:title="@string/menu_log" />
"""
    assert src.count(old_logcat) == 1, "nav_logcat anchor not found"
    src = src.replace(old_logcat, "", 1)

    old_tools = """        <item
            android:id="@+id/nav_tools"
            android:icon="@drawable/baseline_construction_24"
            android:title="@string/menu_tools" />
"""
    assert src.count(old_tools) == 1, "nav_tools anchor not found"
    src = src.replace(old_tools, "", 1)

    # marker comment so reruns skip
    src = src.replace(
        "<!-- navMenuPruned:",
        "<!-- " + MARKER + ": nav_logcat/nav_tools removed per user request -->\n<!-- navMenuPruned:",
        1)
    _write(path, src)
    print("main_drawer_menu.xml log/tools removed OK")


def patch_main_activity_nav(root):
    """Drop the now-orphaned nav_logcat/nav_tools branches (their R.ids are gone)."""
    path = root + "/" + MAIN_ACTIVITY
    src = _read(path)
    if MARKER + ":navprune" in src:
        print("MainActivity.kt nav branches already pruned, skip")
        return

    old = """            R.id.nav_logcat -> displayFragment(LogcatFragment())
"""
    assert src.count(old) == 1, "nav_logcat branch not found"
    src = src.replace(old, "", 1)

    old = """            R.id.nav_tools -> displayFragment(ToolsFragment())
"""
    assert src.count(old) == 1, "nav_tools branch not found"
    src = src.replace(old, "", 1)

    # marker
    old = "            R.id.nav_route -> displayFragment(RouteFragment())\n"
    assert src.count(old) == 1, "nav_route anchor not found"
    src = src.replace(
        old,
        old + "            // " + MARKER + ":navprune nav_logcat/nav_tools removed from drawer\n",
        1)
    _write(path, src)
    print("MainActivity.kt nav branches pruned OK")


def patch_main_activity_highlight(root):
    """Refined bottom nav: highlight the active entry (accent icon/label + pill)."""
    path = root + "/" + MAIN_ACTIVITY
    src = _read(path)
    if MARKER + ":navhi" in src:
        print("MainActivity.kt bottom nav highlight already present, skip")
        return

    old = "    fun displayFragmentWithId(@IdRes id: Int): Boolean {"
    assert src.count(old) == 1, "displayFragmentWithId anchor not found"
    new = (
        "    // " + MARKER + ":navhi refined bottom nav - active entry highlight.\n"
        "    private fun updateBottomNav(@IdRes id: Int) {\n"
        "        val accent = ContextCompat.getColor(this, R.color.material_purple_500)\n"
        "        val idle = 0xFF9E9E9E.toInt()\n"
        "        val pillOn = 0x336D4ACD\n"
        "        val pillOff = 0x00000000\n"
        "        styleNavItem(binding.bottomNavConfigPill, binding.bottomNavConfigIcon, binding.bottomNavConfigLabel, id == R.id.nav_configuration, accent, idle, pillOn, pillOff)\n"
        "        styleNavItem(binding.bottomNavRoutePill, binding.bottomNavRouteIcon, binding.bottomNavRouteLabel, id == R.id.nav_route, accent, idle, pillOn, pillOff)\n"
        "        styleNavItem(binding.bottomNavGroupPill, binding.bottomNavGroupIcon, binding.bottomNavGroupLabel, id == R.id.nav_group, accent, idle, pillOn, pillOff)\n"
        "        styleNavItem(binding.bottomNavSettingsPill, binding.bottomNavSettingsIcon, binding.bottomNavSettingsLabel, id == R.id.nav_settings, accent, idle, pillOn, pillOff)\n"
        "    }\n"
        "\n"
        "    private fun styleNavItem(pill: android.view.View, icon: android.widget.ImageView, label: android.widget.TextView, active: Boolean, accent: Int, idle: Int, pillOn: Int, pillOff: Int) {\n"
        "        icon.setColorFilter(if (active) accent else idle)\n"
        "        label.setTextColor(if (active) accent else idle)\n"
        "        (pill.background.mutate() as android.graphics.drawable.GradientDrawable).setColor(if (active) pillOn else pillOff)\n"
        "    }\n"
        "\n"
        "    fun displayFragmentWithId(@IdRes id: Int): Boolean {"
    )
    src = src.replace(old, new, 1)

    old = "        navigation.menu.findItem(id).isChecked = true\n"
    assert src.count(old) == 1, "nav checked anchor not found"
    src = src.replace(old, old + "        updateBottomNav(id) // " + MARKER + ":navhi\n", 1)
    _write(path, src)
    print("MainActivity.kt bottom nav highlight OK")


def patch_strings(root):
    for rel, lang, pairs in (
        (STRINGS_EN, "en", (("bottom_menu_label", "Menu"),)),
        (STRINGS_ZH, "zh", (("bottom_menu_label", "菜单"),)),
    ):
        path = root + "/" + rel
        src = _read(path)
        anchor = 'name="card_badge_disconnected"'
        assert src.count(anchor) == 1, f"string anchor not found in {rel}"
        idx = src.index(anchor)
        line_start = src.rindex("\n", 0, idx) + 1
        indent = src[line_start:idx].split("<string")[0]
        added = []
        for name, text in pairs:
            if f'name="{name}"' in src:
                print(f"{rel} {name} already present, skip")
                continue
            src = (src[:line_start]
                   + f'{indent}<string name="{name}">{text}</string>\n'
                   + src[line_start:])
            # recompute insertion point for the next string
            idx = src.index(anchor)
            line_start = src.rindex("\n", 0, idx) + 1
            indent = src[line_start:idx].split("<string")[0]
            added.append(name)
        _write(path, src)
        if added:
            print(f"{rel} added: {', '.join(added)}")


def main():
    root = "."
    patch_layout(root)
    patch_statsbar(root)
    patch_statsbar_dashboard_binding(root)
    patch_profile_item(root)
    patch_main_activity(root)
    patch_strings(root)
    patch_drawer_menu(root)
    patch_main_activity_nav(root)
    patch_main_activity_highlight(root)
    print("ALL START-BUTTON-BOTTOM PATCHES OK")


if __name__ == "__main__":
    main()
