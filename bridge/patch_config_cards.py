#!/usr/bin/env python3
"""ZedSecure-style dashboard panel on main screen (v2).

User requests (2026-10-06), reference: ZedSecure VPN Client:
1. Bottom config/status panel -> card style dashboard:
   - Row: IP egress location + latency (tap re-tests).
   - Center: big gradient badge = connect toggle, shows connection duration
     timer + connected state (this replaces the old paper-plane FAB).
   - Two side-by-side cards: DOWNLOAD (realtime + total) / UPLOAD (realtime + total).
   - "Auto select" card: load balance switch status + current auto-selected
     node + latency (tap toggles).
   - Node config card + in-card Ookla speed test.
2. Lively, not rigid; loose spacing; mixed accents on black, readable.
3. Old FAB hidden (badge is the new start control), modern look.

Changes (run from NekoBox checkout root):
1. app/src/main/res/layout/layout_main.xml
   - StatsBar inner content -> dashboard (see above).
   - ServiceButton -> android:visibility="gone".
2. app/src/main/res/drawable/bg_badge_on.xml / bg_badge_off.xml (new).
3. app/src/main/java/io/nekohasekai/sagernet/widget/StatsBar.kt
   - Wire dashboard: timer, badge toggle, IP geo, LB/auto card, node card,
     in-card speed test, traffic totals.
4. app/src/main/java/io/nekohasekai/sagernet/ui/MainActivity.kt
   - Add toggleService(); FAB uses it; cbSpeedUpdate -> updateTraffic.
5. libcore/speedtest.go - append ipGeoLookup (ip-api.com through proxy).
6. libcore/box.go - export IPGeoLookup (requires patch_speedtest first).
7. bg/proto/SpeedTestInstance.kt - add doIPGeoLookup (requires patch_speedtest).
8. values/strings.xml + values-zh-rCN/strings.xml - new strings.

Requires: patch_speedtest.py and patch_loadbalance.py already applied.
Idempotent via marker comments. Replaces v1 card design (fresh checkout).
"""

import sys

MARKER = "chanboxConfigCardsV2"
GEO_MARKER = "chanboxIPGeo"

LAYOUT_MAIN = "app/src/main/res/layout/layout_main.xml"
MAIN_ACTIVITY = "app/src/main/java/io/nekohasekai/sagernet/ui/MainActivity.kt"
STATSBAR_KT = "app/src/main/java/io/nekohasekai/sagernet/widget/StatsBar.kt"
SPEEDTEST_GO = "libcore/speedtest.go"
BOX_GO = "libcore/box.go"
INSTANCE_KT = "app/src/main/java/io/nekohasekai/sagernet/bg/proto/SpeedTestInstance.kt"
STRINGS_EN = "app/src/main/res/values/strings.xml"
STRINGS_ZH = "app/src/main/res/values-zh-rCN/strings.xml"
DRAWABLE_DIR = "app/src/main/res/drawable"


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _write(path, src):
    with open(path, "w", encoding="utf-8") as f:
        f.write(src)


# ---------------------------------------------------------------- layout_main.xml
DASHBOARD_INNER = """<!-- {M}: ZedSecure-style dashboard -->
            <LinearLayout
                android:layout_width="match_parent"
                android:layout_height="wrap_content"
                android:background="@drawable/bg_panel_gradient"
                android:orientation="vertical"
                android:padding="16dp">

                <!-- location + latency row -->
                <LinearLayout
                    android:id="@+id/card_loc_row"
                    android:layout_width="match_parent"
                    android:layout_height="wrap_content"
                    android:clickable="true"
                    android:focusable="true"
                    android:foreground="?android:attr/selectableItemBackground"
                    android:gravity="center_vertical"
                    android:orientation="horizontal"
                    android:paddingTop="4dp"
                    android:paddingBottom="4dp">

                    <TextView
                        android:layout_width="wrap_content"
                        android:layout_height="wrap_content"
                        android:text="&#x1F30D;"
                        android:textSize="22sp" />

                    <LinearLayout
                        android:layout_width="0dp"
                        android:layout_height="wrap_content"
                        android:layout_marginStart="10dp"
                        android:layout_weight="1"
                        android:orientation="vertical">

                        <TextView
                            android:id="@+id/card_loc_value"
                            android:layout_width="wrap_content"
                            android:layout_height="wrap_content"
                            android:ellipsize="end"
                            android:maxLines="1"
                            android:textColor="#FFFFFF"
                            android:textSize="14sp"
                            android:textStyle="bold"
                            tools:text="\u7F8E\u56FD" />

                        <TextView
                            android:layout_width="wrap_content"
                            android:layout_height="wrap_content"
                            android:text="@string/card_loc_title"
                            android:textColor="#9E9E9E"
                            android:textSize="11sp" />
                    </LinearLayout>

                    <TextView
                        android:id="@+id/card_ping_value"
                        android:layout_width="wrap_content"
                        android:layout_height="wrap_content"
                        android:layout_marginEnd="4dp"
                        android:background="@drawable/bg_pill_latency"
                        android:paddingStart="10dp"
                        android:paddingEnd="10dp"
                        android:paddingTop="3dp"
                        android:paddingBottom="3dp"
                        android:textColor="#FFFFFF"
                        android:textSize="13sp"
                        android:textStyle="bold"
                        tools:text="208ms" />

                    <TextView
                        android:layout_width="wrap_content"
                        android:layout_height="wrap_content"
                        android:text="\u203A"
                        android:textColor="#9E9E9E"
                        android:textSize="20sp" />
                </LinearLayout>

                <!-- center badge = connect toggle -->
                <FrameLayout
                    android:layout_width="wrap_content"
                    android:layout_height="wrap_content"
                    android:layout_gravity="center_horizontal"
                    android:layout_marginTop="14dp">

                    <View
                        android:id="@+id/card_badge_bg"
                        android:layout_width="150dp"
                        android:layout_height="150dp"
                        android:background="@drawable/bg_badge_off" />

                    <LinearLayout
                        android:id="@+id/card_badge"
                        android:layout_width="150dp"
                        android:layout_height="150dp"
                        android:clickable="true"
                        android:focusable="true"
                        android:gravity="center"
                        android:orientation="vertical">

                        <TextView
                            android:id="@+id/card_timer"
                            android:layout_width="wrap_content"
                            android:layout_height="wrap_content"
                            android:text="00:00"
                            android:textColor="#FFFFFF"
                            android:textSize="32sp"
                            android:textStyle="bold" />
                    </LinearLayout>
                </FrameLayout>

                <TextView
                    android:id="@+id/card_badge_state"
                    android:layout_width="wrap_content"
                    android:layout_height="wrap_content"
                    android:layout_gravity="center_horizontal"
                    android:layout_marginTop="8dp"
                    android:text="@string/card_badge_disconnected"
                    android:textColor="#9E9E9E"
                    android:textSize="14sp"
                    android:textStyle="bold" />

                <!-- download / upload cards -->
                <LinearLayout
                    android:layout_width="match_parent"
                    android:layout_height="wrap_content"
                    android:layout_marginTop="16dp"
                    android:orientation="horizontal">

                    <com.google.android.material.card.MaterialCardView
                        android:layout_width="0dp"
                        android:layout_height="wrap_content"
                        android:layout_marginEnd="6dp"
                        android:layout_weight="1"
                        app:cardBackgroundColor="#161616"
                        app:cardCornerRadius="18dp"
                        app:cardElevation="0dp"
                        app:strokeColor="@color/material_blue_500"
                        app:strokeWidth="1dp">

                        <LinearLayout
                            android:layout_width="match_parent"
                            android:layout_height="wrap_content"
                            android:orientation="vertical"
                            android:padding="14dp">

                            <LinearLayout
                                android:layout_width="wrap_content"
                                android:layout_height="wrap_content"
                                android:gravity="center_vertical"
                                android:orientation="horizontal">

                                <TextView
                                    android:layout_width="wrap_content"
                                    android:layout_height="wrap_content"
                                    android:text="&#x2B07;"
                                    android:textColor="@color/material_blue_500"
                                    android:textSize="16sp" />

                                <TextView
                                    android:layout_width="wrap_content"
                                    android:layout_height="wrap_content"
                                    android:layout_marginStart="6dp"
                                    android:text="@string/card_down_label"
                                    android:textColor="#9E9E9E"
                                    android:textSize="11sp" />
                            </LinearLayout>

                            <TextView
                                android:id="@+id/card_down_speed"
                                android:layout_width="wrap_content"
                                android:layout_height="wrap_content"
                                android:layout_marginTop="6dp"
                                android:textColor="#FFFFFF"
                                android:textSize="20sp"
                                android:textStyle="bold"
                                tools:text="57 KB/s" />

                            <TextView
                                android:id="@+id/card_down_total"
                                android:layout_width="wrap_content"
                                android:layout_height="wrap_content"
                                android:layout_marginTop="2dp"
                                android:textColor="#9E9E9E"
                                android:textSize="12sp"
                                tools:text="262.0 KB" />

                            <ProgressBar
                                android:id="@+id/card_down_bar"
                                style="?android:attr/progressBarStyleHorizontal"
                                android:layout_width="match_parent"
                                android:layout_height="4dp"
                                android:layout_marginTop="8dp"
                                android:max="100"
                                android:progress="0"
                                android:progressDrawable="@drawable/bg_speed_bar_blue" />
                        </LinearLayout>
                    </com.google.android.material.card.MaterialCardView>

                    <com.google.android.material.card.MaterialCardView
                        android:layout_width="0dp"
                        android:layout_height="wrap_content"
                        android:layout_marginStart="6dp"
                        android:layout_weight="1"
                        app:cardBackgroundColor="#161616"
                        app:cardCornerRadius="18dp"
                        app:cardElevation="0dp"
                        app:strokeColor="@color/material_purple_500"
                        app:strokeWidth="1dp">

                        <LinearLayout
                            android:layout_width="match_parent"
                            android:layout_height="wrap_content"
                            android:orientation="vertical"
                            android:padding="14dp">

                            <LinearLayout
                                android:layout_width="wrap_content"
                                android:layout_height="wrap_content"
                                android:gravity="center_vertical"
                                android:orientation="horizontal">

                                <TextView
                                    android:layout_width="wrap_content"
                                    android:layout_height="wrap_content"
                                    android:text="&#x2B06;"
                                    android:textColor="@color/material_purple_500"
                                    android:textSize="16sp" />

                                <TextView
                                    android:layout_width="wrap_content"
                                    android:layout_height="wrap_content"
                                    android:layout_marginStart="6dp"
                                    android:text="@string/card_up_label"
                                    android:textColor="#9E9E9E"
                                    android:textSize="11sp" />
                            </LinearLayout>

                            <TextView
                                android:id="@+id/card_up_speed"
                                android:layout_width="wrap_content"
                                android:layout_height="wrap_content"
                                android:layout_marginTop="6dp"
                                android:textColor="#FFFFFF"
                                android:textSize="20sp"
                                android:textStyle="bold"
                                tools:text="2.7 KB/s" />

                            <TextView
                                android:id="@+id/card_up_total"
                                android:layout_width="wrap_content"
                                android:layout_height="wrap_content"
                                android:layout_marginTop="2dp"
                                android:textColor="#9E9E9E"
                                android:textSize="12sp"
                                tools:text="59.9 KB" />

                            <ProgressBar
                                android:id="@+id/card_up_bar"
                                style="?android:attr/progressBarStyleHorizontal"
                                android:layout_width="match_parent"
                                android:layout_height="4dp"
                                android:layout_marginTop="8dp"
                                android:max="100"
                                android:progress="0"
                                android:progressDrawable="@drawable/bg_speed_bar_purple" />
                        </LinearLayout>
                    </com.google.android.material.card.MaterialCardView>
                </LinearLayout>

                <!-- auto select card -->
                <com.google.android.material.card.MaterialCardView
                    android:layout_width="match_parent"
                    android:layout_height="wrap_content"
                    android:layout_marginTop="12dp"
                    app:cardBackgroundColor="#161616"
                    app:cardCornerRadius="18dp"
                    app:cardElevation="0dp"
                    app:strokeColor="@color/material_orange_500"
                    app:strokeWidth="1dp">

                    <LinearLayout
                        android:id="@+id/card_lb_row"
                        android:layout_width="match_parent"
                        android:layout_height="wrap_content"
                        android:clickable="true"
                        android:focusable="true"
                        android:foreground="?android:attr/selectableItemBackground"
                        android:gravity="center_vertical"
                        android:orientation="horizontal"
                        android:padding="14dp">

                        <TextView
                            android:layout_width="wrap_content"
                            android:layout_height="wrap_content"
                            android:text="&#x1F500;"
                            android:textSize="22sp" />

                        <LinearLayout
                            android:layout_width="0dp"
                            android:layout_height="wrap_content"
                            android:layout_marginStart="10dp"
                            android:layout_weight="1"
                            android:orientation="vertical">

                            <TextView
                                android:layout_width="wrap_content"
                                android:layout_height="wrap_content"
                                android:text="@string/card_auto_label"
                                android:textColor="#FFFFFF"
                                android:textSize="14sp"
                                android:textStyle="bold" />

                            <TextView
                                android:id="@+id/card_lb_value"
                                android:layout_width="wrap_content"
                                android:layout_height="wrap_content"
                                android:layout_marginTop="2dp"
                                android:ellipsize="end"
                                android:maxLines="1"
                                android:textColor="#9E9E9E"
                                android:textSize="12sp"
                                tools:text="\u5DF2\u5173\u95ED" />
                        </LinearLayout>

                        <TextView
                            android:layout_width="wrap_content"
                            android:layout_height="wrap_content"
                            android:text="\u203A"
                            android:textColor="#9E9E9E"
                            android:textSize="20sp" />
                    </LinearLayout>
                </com.google.android.material.card.MaterialCardView>

                <!-- node config + speed test card -->
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

                <TextView
                    android:id="@+id/status"
                    android:layout_width="wrap_content"
                    android:layout_height="wrap_content"
                    android:layout_gravity="center_horizontal"
                    android:layout_marginTop="8dp"
                    android:ellipsize="end"
                    android:maxLines="1"
                    android:textColor="#616161"
                    android:textSize="12sp"
                    tools:text="@string/connection_test_available" />
            </LinearLayout>"""


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
    src = src[:j] + DASHBOARD_INNER.format(M=MARKER) + src[m + len("</LinearLayout>"):]
    # hide old FAB: the badge is the new start control
    old_fab = '            android:id="@+id/fab"\n'
    assert src.count(old_fab) == 1, "FAB anchor not found exactly once"
    src = src.replace(old_fab, old_fab + '            android:visibility="gone"\n', 1)
    _write(path, src)
    print("layout_main.xml patched OK")

# ---------------------------------------------------------------- badge drawables
BADGE_ON = """<?xml version="1.0" encoding="utf-8"?>
<!-- {M}: 16-point starburst seal, ZedSecure style -->
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="150dp"
    android:height="150dp"
    android:viewportWidth="100"
    android:viewportHeight="100">
    <path
        android:pathData="M50.0,2.0 L58.0,9.8 L68.4,5.7 L72.8,15.9 L83.9,16.1 L84.1,27.2 L94.3,31.6 L90.2,42.0 L98.0,50.0 L90.2,58.0 L94.3,68.4 L84.1,72.8 L83.9,83.9 L72.8,84.1 L68.4,94.3 L58.0,90.2 L50.0,98.0 L42.0,90.2 L31.6,94.3 L27.2,84.1 L16.1,83.9 L15.9,72.8 L5.7,68.4 L9.8,58.0 L2.0,50.0 L9.8,42.0 L5.7,31.6 L15.9,27.2 L16.1,16.1 L27.2,15.9 L31.6,5.7 L42.0,9.8 Z"
        android:fillColor="#6D4ACD" />
</vector>
"""

BADGE_OFF = """<?xml version="1.0" encoding="utf-8"?>
<!-- {M}: starburst seal, disconnected state -->
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="150dp"
    android:height="150dp"
    android:viewportWidth="100"
    android:viewportHeight="100">
    <path
        android:pathData="M50.0,2.0 L58.0,9.8 L68.4,5.7 L72.8,15.9 L83.9,16.1 L84.1,27.2 L94.3,31.6 L90.2,42.0 L98.0,50.0 L90.2,58.0 L94.3,68.4 L84.1,72.8 L83.9,83.9 L72.8,84.1 L68.4,94.3 L58.0,90.2 L50.0,98.0 L42.0,90.2 L31.6,94.3 L27.2,84.1 L16.1,83.9 L15.9,72.8 L5.7,68.4 L9.8,58.0 L2.0,50.0 L9.8,42.0 L5.7,31.6 L15.9,27.2 L16.1,16.1 L27.2,15.9 L31.6,5.7 L42.0,9.8 Z"
        android:fillColor="#2A2A2A" />
</vector>
"""

PANEL_GRADIENT = """<?xml version="1.0" encoding="utf-8"?>
<!-- {M}: dark purple-blue gradient panel background, ZedSecure style -->
<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle">
    <gradient
        android:angle="135"
        android:startColor="#241B4D"
        android:centerColor="#141F45"
        android:endColor="#0B0B0B" />
    <corners android:topLeftRadius="24dp" android:topRightRadius="24dp" />
</shape>
"""

SPEED_BAR_BLUE = """<?xml version="1.0" encoding="utf-8"?>
<!-- {M}: live speed bar -->
<layer-list xmlns:android="http://schemas.android.com/apk/res/android">
    <item android:id="@android:id/background">
        <shape>
            <corners android:radius="2dp" />
            <solid android:color="#2A2A2A" />
        </shape>
    </item>
    <item android:id="@android:id/progress">
        <clip>
            <shape>
                <corners android:radius="2dp" />
                <solid android:color="@color/material_blue_500" />
            </shape>
        </clip>
    </item>
</layer-list>
"""

SPEED_BAR_PURPLE = """<?xml version="1.0" encoding="utf-8"?>
<!-- {M}: live speed bar -->
<layer-list xmlns:android="http://schemas.android.com/apk/res/android">
    <item android:id="@android:id/background">
        <shape>
            <corners android:radius="2dp" />
            <solid android:color="#2A2A2A" />
        </shape>
    </item>
    <item android:id="@android:id/progress">
        <clip>
            <shape>
                <corners android:radius="2dp" />
                <solid android:color="@color/material_purple_500" />
            </shape>
        </clip>
    </item>
</layer-list>
"""

PILL_LATENCY = """<?xml version="1.0" encoding="utf-8"?>
<!-- {M}: latency quality pill, neutral -->
<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle">
    <corners android:radius="12dp" />
    <solid android:color="#424242" />
</shape>
"""

PILL_LATENCY_GOOD = """<?xml version="1.0" encoding="utf-8"?>
<!-- {M}: latency quality pill, good (<120ms) -->
<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle">
    <corners android:radius="12dp" />
    <solid android:color="#2E7D32" />
</shape>
"""

PILL_LATENCY_MID = """<?xml version="1.0" encoding="utf-8"?>
<!-- {M}: latency quality pill, fair (<300ms) -->
<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle">
    <corners android:radius="12dp" />
    <solid android:color="#B7791F" />
</shape>
"""

PILL_LATENCY_BAD = """<?xml version="1.0" encoding="utf-8"?>
<!-- {M}: latency quality pill, poor -->
<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle">
    <corners android:radius="12dp" />
    <solid android:color="#C62828" />
</shape>
"""


def patch_drawables(root):
    import os
    d = root + "/" + DRAWABLE_DIR
    for name, content in (("bg_badge_on.xml", BADGE_ON),
                          ("bg_badge_off.xml", BADGE_OFF),
                          ("bg_panel_gradient.xml", PANEL_GRADIENT),
                          ("bg_speed_bar_blue.xml", SPEED_BAR_BLUE),
                          ("bg_speed_bar_purple.xml", SPEED_BAR_PURPLE),
                          ("bg_pill_latency.xml", PILL_LATENCY),
                          ("bg_pill_latency_good.xml", PILL_LATENCY_GOOD),
                          ("bg_pill_latency_mid.xml", PILL_LATENCY_MID),
                          ("bg_pill_latency_bad.xml", PILL_LATENCY_BAD)):
        path = d + "/" + name
        if os.path.exists(path) and MARKER in _read(path):
            print("%s already exists, skip" % name)
            continue
        _write(path, content.format(M=MARKER))
        print("%s written" % name)


# ---------------------------------------------------------------- StatsBar.kt
STATSBAR_IMPORTS_ANCHOR = "import io.nekohasekai.sagernet.ui.MainActivity"
STATSBAR_IMPORTS_NEW = """import android.animation.AnimatorSet
import android.animation.ObjectAnimator
import android.os.SystemClock
import io.nekohasekai.sagernet.aidl.SpeedDisplayData
import io.nekohasekai.sagernet.bg.proto.SpeedTestInstance
import io.nekohasekai.sagernet.database.GroupManager
import io.nekohasekai.sagernet.database.SagerDatabase
import io.nekohasekai.sagernet.ui.MainActivity
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.isActive"""

STATSBAR_FIELDS_OLD = """    private lateinit var statusText: TextView
    private lateinit var txText: TextView
    private lateinit var rxText: TextView
"""
STATSBAR_FIELDS_NEW = """    private lateinit var statusText: TextView
    private lateinit var cardLocValue: TextView
    private lateinit var cardPingValue: TextView
    private lateinit var cardTimer: TextView
    private lateinit var cardBadgeState: TextView
    private lateinit var cardBadgeBg: View
    private lateinit var cardDownSpeed: TextView
    private lateinit var cardDownTotal: TextView
    private lateinit var cardDownBar: android.widget.ProgressBar
    private lateinit var cardUpSpeed: TextView
    private lateinit var cardUpTotal: TextView
    private lateinit var cardUpBar: android.widget.ProgressBar
    private lateinit var cardLbValue: TextView
    private lateinit var cardNodeName: TextView
    private lateinit var cardNodeDetail: TextView
    private lateinit var cardSpeedtestBtn: View
    private lateinit var cardSpeedtestValue: TextView
    private var ipGeoJob: Job? = null
    private var speedtestJob: Job? = null
    private var timerJob: Job? = null
    private var breathAnimator: AnimatorSet? = null
    private var connectStartMs: Long = 0L
    private var maxDownSpeed: Long = 1L
    private var maxUpSpeed: Long = 1L
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
        cardLocValue = findViewById(R.id.card_loc_value)
        cardPingValue = findViewById(R.id.card_ping_value)
        cardTimer = findViewById(R.id.card_timer)
        cardBadgeState = findViewById(R.id.card_badge_state)
        cardBadgeBg = findViewById(R.id.card_badge_bg)
        cardDownSpeed = findViewById(R.id.card_down_speed)
        cardDownTotal = findViewById(R.id.card_down_total)
        cardDownBar = findViewById(R.id.card_down_bar)
        cardUpSpeed = findViewById(R.id.card_up_speed)
        cardUpTotal = findViewById(R.id.card_up_total)
        cardUpBar = findViewById(R.id.card_up_bar)
        cardLbValue = findViewById(R.id.card_lb_value)
        cardNodeName = findViewById(R.id.card_node_name)
        cardNodeDetail = findViewById(R.id.card_node_detail)
        cardSpeedtestBtn = findViewById(R.id.card_speedtest_btn)
        cardSpeedtestValue = findViewById(R.id.card_speedtest_value)
        findViewById<View>(R.id.card_loc_row)?.setOnClickListener {
            if (DataStore.serviceState.connected) {
                testConnection()
                refreshIPGeo()
            }
        }
        findViewById<View>(R.id.card_badge)?.setOnClickListener {
            (context as MainActivity).toggleService()
        }
        findViewById<View>(R.id.card_lb_row)?.setOnClickListener { toggleLoadBalance() }
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
        if (!::cardDownSpeed.isInitialized) return
        cardDownSpeed.text = context.getString(R.string.speed, Formatter.formatFileSize(context, rxRate))
        cardUpSpeed.text = context.getString(R.string.speed, Formatter.formatFileSize(context, txRate))
        if (rxRate > maxDownSpeed) maxDownSpeed = rxRate
        if (txRate > maxUpSpeed) maxUpSpeed = txRate
        cardDownBar.progress = ((rxRate * 100 / maxDownSpeed).toInt()).coerceIn(0, 100)
        cardUpBar.progress = ((txRate * 100 / maxUpSpeed).toInt()).coerceIn(0, 100)
    }

    fun updateTraffic(stats: SpeedDisplayData) {
        updateSpeed(stats.txRateProxy, stats.rxRateProxy)
        if (!::cardDownTotal.isInitialized) return
        cardDownTotal.text = Formatter.formatFileSize(context, stats.rxTotal)
        cardUpTotal.text = Formatter.formatFileSize(context, stats.txTotal)
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
                maxDownSpeed = 1L
                maxUpSpeed = 1L
                setBadgeState(true)
                startTimer()
                updateNodeCard()
                updateLbCard()
                refreshIPGeo()
                testConnection()
            }
        } else {
            postWhenStarted {
                performHide()
            }
            ipGeoJob?.cancel()
            speedtestJob?.cancel()
            if (state == BaseService.State.Connecting) {
                setBadgeConnecting()
            } else {
                stopTimer()
                setBadgeState(false)
                updateSpeed(0, 0)
                if (::cardLocValue.isInitialized) {
                    cardLocValue.text = "\\uD83C\\uDF0D " + app.getString(R.string.card_ip_unknown)
                    cardPingValue.text = "--"
                    cardPingValue.setBackgroundResource(R.drawable.bg_pill_latency)
                }
                if (::cardSpeedtestValue.isInitialized) {
                    cardSpeedtestValue.text = ""
                    cardSpeedtestBtn.isEnabled = true
                }
            }
"""

STATSBAR_PING_OLD = """                val elapsed = activity.urlTest()
                onMainDispatcher {
                    isEnabled = true
                    setStatus(
"""
STATSBAR_PING_NEW = """                val elapsed = activity.urlTest()
                onMainDispatcher {
                    isEnabled = true
                    if (::cardPingValue.isInitialized) {
                        cardPingValue.text = "" + elapsed + "ms"
                        updateLatencyPill(elapsed.toInt())
                    }
                    setStatus(
"""


def _methods_block():
    # built with plain concatenation to avoid %-format vs Kotlin "%02d" clashes
    M = MARKER
    return """
    // """ + M + """: badge on/off visuals + breathing animation when connected.
    private fun setBadgeState(connected: Boolean) {
        if (!::cardBadgeBg.isInitialized) return
        cardBadgeBg.setBackgroundResource(
            if (connected) R.drawable.bg_badge_on else R.drawable.bg_badge_off
        )
        cardBadgeState.text = app.getString(
            if (connected) R.string.card_badge_connected else R.string.card_badge_disconnected
        )
        if (connected) startBreathing() else stopBreathing()
    }

    // """ + M + """: gentle breathing scale on the badge, feels alive.
    private fun startBreathing(fast: Boolean = false) {
        stopBreathing()
        if (!::cardBadgeBg.isInitialized) return
        val dur = if (fast) 900L else 2200L
        val sx = ObjectAnimator.ofFloat(cardBadgeBg, "scaleX", 1f, 1.06f, 1f)
        val sy = ObjectAnimator.ofFloat(cardBadgeBg, "scaleY", 1f, 1.06f, 1f)
        sx.duration = dur
        sy.duration = dur
        sx.repeatCount = ObjectAnimator.INFINITE
        sy.repeatCount = ObjectAnimator.INFINITE
        breathAnimator = AnimatorSet().apply {
            playTogether(sx, sy)
            start()
        }
    }

    private fun stopBreathing() {
        breathAnimator?.cancel()
        breathAnimator = null
        if (::cardBadgeBg.isInitialized) {
            cardBadgeBg.scaleX = 1f
            cardBadgeBg.scaleY = 1f
        }
    }

    // """ + M + """: connecting state - badge pulses fast with "connecting" text.
    private fun setBadgeConnecting() {
        if (!::cardBadgeBg.isInitialized) return
        cardBadgeBg.setBackgroundResource(R.drawable.bg_badge_on)
        cardBadgeState.text = app.getString(R.string.card_badge_connecting)
        if (::cardTimer.isInitialized) cardTimer.text = "00:00"
        startBreathing(fast = true)
    }

    // """ + M + """: latency pill color tells line quality at a glance.
    private fun updateLatencyPill(ms: Int) {
        if (!::cardPingValue.isInitialized) return
        cardPingValue.setBackgroundResource(
            when {
                ms < 0 -> R.drawable.bg_pill_latency
                ms < 120 -> R.drawable.bg_pill_latency_good
                ms < 300 -> R.drawable.bg_pill_latency_mid
                else -> R.drawable.bg_pill_latency_bad
            }
        )
    }

    // """ + M + """: flag + Chinese country name, friendlier for Chinese users.
    private fun countryLabel(countryEn: String, ip: String): String {
        val name = when (countryEn.lowercase()) {
            "united states" -> "\\uD83C\\uDDFA\\uD83C\\uDDF8 \\u7F8E\\u56FD"
            "japan" -> "\\uD83C\\uDDEF\\uD83C\\uDDF5 \\u65E5\\u672C"
            "singapore" -> "\\uD83C\\uDDF8\\uD83C\\uDDEC \\u65B0\\u52A0\\u5761"
            "germany" -> "\\uD83C\\uDDE9\\uD83C\\uDDEA \\u5FB7\\u56FD"
            "united kingdom" -> "\\uD83C\\uDDEC\\uD83C\\uDDE7 \\u82F1\\u56FD"
            "france" -> "\\uD83C\\uDDEB\\uD83C\\uDDF7 \\u6CD5\\u56FD"
            "netherlands" -> "\\uD83C\\uDDF3\\uD83C\\uDDF1 \\u8377\\u5170"
            "canada" -> "\\uD83C\\uDDE8\\uD83C\\uDDE6 \\u52A0\\u62FF\\u5927"
            "australia" -> "\\uD83C\\uDDE6\\uD83C\\uDDFA \\u6FB3\\u5927\\u5229\\u4E9A"
            "south korea", "korea" -> "\\uD83C\\uDDF0\\uD83C\\uDDF7 \\u97E9\\u56FD"
            "hong kong" -> "\\uD83C\\uDDED\\uD83C\\uDDF0 \\u9999\\u6E2F"
            "taiwan" -> "\\uD83C\\uDDF9\\uD83C\\uDDFC \\u53F0\\u6E7E"
            "russia" -> "\\uD83C\\uDDF7\\uD83C\\uDDFA \\u4FC4\\u7F57\\u65AF"
            "india" -> "\\uD83C\\uDDEE\\uD83C\\uDDF3 \\u5370\\u5EA6"
            else -> "\\uD83C\\uDF0D " + countryEn
        }
        return name + " \\u00B7 " + ip
    }

    // """ + M + """: connection duration timer inside the badge.
    private fun startTimer() {
        stopTimer()
        connectStartMs = SystemClock.elapsedRealtime()
        val activity = context as MainActivity
        timerJob = activity.lifecycleScope.launch(Dispatchers.Main) {
            while (isActive) {
                val s = (SystemClock.elapsedRealtime() - connectStartMs) / 1000
                if (::cardTimer.isInitialized) {
                    @SuppressLint("SetTextI18n")
                    cardTimer.text = if (s >= 3600) "%d:%02d:%02d".format(s / 3600, (s % 3600) / 60, s % 60)
                    else "%02d:%02d".format(s / 60, s % 60)
                }
                delay(1000)
            }
        }
    }

    private fun stopTimer() {
        timerJob?.cancel()
        timerJob = null
        if (::cardTimer.isInitialized) cardTimer.text = "00:00"
    }

    // """ + M + """: auto-select card: LB switch + current best node + latency.
    private fun updateLbCard() {
        if (!::cardLbValue.isInitialized) return
        runOnDefaultDispatcher {
            val on = DataStore.loadBalance
            var detail = app.getString(if (on) R.string.card_auto_on else R.string.card_auto_off)
            try {
                if (on) {
                    val best = SagerDatabase.proxyDao.getByGroup(DataStore.currentGroupId())
                        .filter { it.ping > 0 }.minByOrNull { it.ping }
                    if (best != null) {
                        @SuppressLint("SetTextI18n")
                        detail += " \\u00B7 " + best.displayName() + " " + best.ping + "ms"
                    }
                } else {
                    val entity = SagerDatabase.proxyDao.getById(DataStore.selectedProxy)
                    if (entity != null) detail += " \\u00B7 " + entity.displayName()
                }
            } catch (e: Exception) {
                Logs.w(e.toString())
            }
            val text = detail
            onMainDispatcher { cardLbValue.text = text }
        }
    }

    // """ + M + """: tap auto card toggles LB (same key as group settings).
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

    // """ + M + """: current node name / protocol / address on card 2.
    private fun updateNodeCard() {
        if (!::cardNodeName.isInitialized) return
        runOnDefaultDispatcher {
            try {
                val entity = SagerDatabase.proxyDao.getById(DataStore.selectedProxy)
                    ?: return@runOnDefaultDispatcher
                val bean = entity.requireBean()
                val name = entity.displayName().ifBlank { entity.displayType() }
                var detail = entity.displayType() + " \\u00B7 " + bean.serverAddress + ":" + bean.serverPort
                val pingMs = entity.ping
                if (pingMs > 0) detail += " \\u00B7 " + pingMs + "ms"
                onMainDispatcher {
                    cardNodeName.text = name
                    cardNodeDetail.text = detail
                }
            } catch (e: Exception) {
                Logs.w(e.toString())
            }
        }
    }

    // """ + M + """: egress IP geolocation through the current profile's proxy.
    private fun refreshIPGeo() {
        if (!::cardLocValue.isInitialized) return
        ipGeoJob?.cancel()
        if (!DataStore.serviceState.connected) {
            cardLocValue.text = "\\uD83C\\uDF0D " + app.getString(R.string.card_ip_unknown)
            return
        }
        cardLocValue.text = "\\uD83C\\uDF0D " + app.getString(R.string.card_ip_fetching)
        ipGeoJob = runOnDefaultDispatcher {
            try {
                val entity = SagerDatabase.proxyDao.getById(DataStore.selectedProxy)
                    ?: throw IllegalStateException("no profile")
                val raw = SpeedTestInstance(entity).doIPGeoLookup(10000)
                val parts = raw.split("|")
                val label = if (parts.size >= 3 && parts[0].isNotBlank() && parts[2].isNotBlank()) {
                    countryLabel(parts[0], parts[2])
                } else raw
                onMainDispatcher { cardLocValue.text = label }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                Logs.w(e.toString())
                onMainDispatcher {
                    cardLocValue.text = "\\uD83C\\uDF0D " + app.getString(R.string.card_ip_unknown)
                }
            }
        }
    }

    // """ + M + """: Ookla speed test inside card 2 (reuses SpeedTestInstance).
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
                    @SuppressLint("SetTextI18n")
                    cardSpeedtestValue.text = "\\u2193 " + "%.1f".format(down) + " Mbps"
                }
                val up = instance.doUploadTest(parts[1], 10, 30000)
                onMainDispatcher {
                    @SuppressLint("SetTextI18n")
                    cardSpeedtestValue.text =
                        "\\u2193 " + "%.1f".format(down) + " Mbps  \\u2191 " + "%.1f".format(up) + " Mbps"
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
        (STATSBAR_PING_OLD, "ping"),
    ]:
        assert src.count(old) == 1, "StatsBar.kt anchor '%s' not found exactly once" % name
    assert "load_balance_enabled" in _read(root + "/" + STRINGS_EN), \
        "patch_loadbalance_quick.py must run first (load_balance_enabled string)"
    src = src.replace(STATSBAR_IMPORTS_ANCHOR, STATSBAR_IMPORTS_NEW, 1)
    src = src.replace(STATSBAR_FIELDS_OLD, STATSBAR_FIELDS_NEW, 1)
    src = src.replace(STATSBAR_BIND_OLD, STATSBAR_BIND_NEW, 1)
    src = src.replace(STATSBAR_SPEED_OLD, STATSBAR_SPEED_NEW, 1)
    src = src.replace(STATSBAR_STATE_OLD, STATSBAR_STATE_NEW, 1)
    src = src.replace(STATSBAR_PING_OLD, STATSBAR_PING_NEW, 1)
    anchor = "    fun testConnection() {\n"
    assert src.count(anchor) == 1, "testConnection anchor not found exactly once"
    src = src.replace(anchor, _methods_block() + anchor, 1)
    _write(path, src)
    print("StatsBar.kt patched OK")


# ---------------------------------------------------------------- MainActivity.kt
TOGGLE_SERVICE_METHOD = """    // {M}: one-tap connect/disconnect, shared by FAB and panel badge.
    fun toggleService() {
        if (DataStore.serviceState.canStop) SagerNet.stopService() else connect.launch(null)
    }

"""

FAB_LISTENER_OLD = """        binding.fab.setOnClickListener {
            if (DataStore.serviceState.canStop) SagerNet.stopService() else connect.launch(
                null
            )
        }"""

CBSPEED_OLD = """    override fun cbSpeedUpdate(stats: SpeedDisplayData) {
        binding.stats.updateSpeed(stats.txRateProxy, stats.rxRateProxy)
    }"""
CBSPEED_NEW = """    override fun cbSpeedUpdate(stats: SpeedDisplayData) {
        binding.stats.updateTraffic(stats)
    }"""


def patch_main_activity(root):
    path = root + "/" + MAIN_ACTIVITY
    src = _read(path)
    if MARKER in src:
        print("MainActivity.kt already patched, skip")
        return
    anchor = "    override fun cbSpeedUpdate(stats: SpeedDisplayData) {"
    assert src.count(anchor) == 1, "cbSpeedUpdate anchor not found exactly once"
    src = src.replace(anchor, TOGGLE_SERVICE_METHOD.replace("{M}", MARKER) + anchor, 1)
    assert src.count(FAB_LISTENER_OLD) == 1, "FAB listener anchor not found exactly once"
    src = src.replace(FAB_LISTENER_OLD, "        binding.fab.setOnClickListener { toggleService() }", 1)
    assert src.count(CBSPEED_OLD) == 1, "cbSpeedUpdate body anchor not found exactly once"
    src = src.replace(CBSPEED_OLD, CBSPEED_NEW, 1)
    _write(path, src)
    print("MainActivity.kt patched OK")

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
INSTANCE_GEO_KT = """    // {G}: egress IP + geolocation through this profile's proxy.
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
    src = src.replace(anchor, INSTANCE_GEO_KT.replace("{G}", GEO_MARKER) + anchor, 1)
    _write(path, src)
    print("SpeedTestInstance.kt doIPGeoLookup added OK")


# ---------------------------------------------------------------- strings
STRINGS_EN_ADD = """    <!-- {M} -->
    <string name="card_loc_title">Exit IP</string>
    <string name="card_down_label">Download</string>
    <string name="card_up_label">Upload</string>
    <string name="card_auto_label">Auto Select</string>
    <string name="card_auto_on">ON</string>
    <string name="card_auto_off">OFF</string>
    <string name="card_badge_connected">Connected</string>
    <string name="card_badge_disconnected">Disconnected</string>
    <string name="card_badge_connecting">Connecting…</string>
    <string name="card_ip_fetching">locating…</string>
    <string name="card_ip_unknown">unknown</string>
    <string name="card_node_label">Node</string>
    <string name="card_speedtest_start">Speed Test</string>
    <string name="card_speedtest_testing">testing…</string>
""".format(M=MARKER)

STRINGS_ZH_ADD = """    <!-- {M} -->
    <string name="card_loc_title">IP出口</string>
    <string name="card_down_label">下载</string>
    <string name="card_up_label">上传</string>
    <string name="card_auto_label">自动选择</string>
    <string name="card_auto_on">已开启</string>
    <string name="card_auto_off">已关闭</string>
    <string name="card_badge_connected">已连接</string>
    <string name="card_badge_disconnected">未连接</string>
    <string name="card_badge_connecting">连接中…</string>
    <string name="card_ip_fetching">获取中…</string>
    <string name="card_ip_unknown">未知</string>
    <string name="card_node_label">节点配置</string>
    <string name="card_speedtest_start">开始测速</string>
    <string name="card_speedtest_testing">测试中…</string>
""".format(M=MARKER)


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
    patch_drawables(root)
    patch_statsbar_kt(root)
    patch_main_activity(root)
    patch_go_ipgeo(root)
    patch_go_box(root)
    patch_instance_kt(root)
    patch_strings(root)
    print("ALL CONFIG-CARDS PATCHES OK")


if __name__ == "__main__":
    main()
