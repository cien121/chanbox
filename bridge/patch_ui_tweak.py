#!/usr/bin/env python3
"""UI tweaks after #110 user feedback (2026-10-06).

User requests:
1. "菜单取消显示" - Remove the menu button from the bottom bar entirely.
2. "透明磨砂还是还回黑色" - Dashboard cards back from frosted glass
   (#2EFFFFFF) to opaque black (#161616).
3. "启动按键做小点不要跟配置路由分组设置同在一行" - Make the start badge
   smaller and NOT on the same row as config/route/group/settings.
   Badge moves to its own centered row above the nav items.
4. "侧边抽屉导航（下拉条）整个删掉，不要显示" - Remove the entire side
   drawer navigation (NavigationViews, drawer wiring, toolbar hamburger icon).

Layout after (bottom_bar becomes vertical):
  [smaller badge 80dp, centered, own row]
  [配置] [路由] [分组] [设置]  (horizontal row, menu removed)

Idempotent via marker. Requires patch_start_button_bottom.py applied first.
"""

import re
import sys

MARKER = "chanboxUiTweak"
SBB_MARKER = "chanboxStartButtonBottom"

LAYOUT_MAIN = "app/src/main/res/layout/layout_main.xml"
MAIN_ACTIVITY = "app/src/main/java/io/nekohasekai/sagernet/ui/MainActivity.kt"
TOOLBAR_FRAGMENT = "app/src/main/java/io/nekohasekai/sagernet/ui/ToolbarFragment.kt"
LAYOUT_APPBAR = "app/src/main/res/layout/layout_appbar.xml"
MENU_ADD_PROFILE = "app/src/main/res/menu/add_profile_menu.xml"


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _write(path, src):
    with open(path, "w", encoding="utf-8") as f:
        f.write(src)


def _find_matching_close(src, open_tag_start, indent):
    """Find the closing tag matching the LinearLayout at open_tag_start.

    The nav item outer LinearLayout uses 12-space indent for its open and
    close tags; inner elements use deeper indents. We scan for the next
    occurrence of '<indent></LinearLayout>' at line start (preceded by
    newline) to avoid matching deeper-indented closes that contain the
    indent as a substring.
    """
    close_tag = "\n" + indent + "</LinearLayout>"
    idx = src.index(close_tag, open_tag_start + 1)
    return idx + len(close_tag)


def patch_layout_remove_menu(root):
    """Remove the menu nav item from the bottom bar."""
    path = root + "/" + LAYOUT_MAIN
    src = _read(path)
    if MARKER + ":nomenu" in src:
        print("layout_main.xml menu already removed, skip")
        return

    # Find the menu nav item block: outer LinearLayout with 12-space indent
    menu_id = 'android:id="@+id/bottom_nav_menu"'
    assert src.count(menu_id) == 1, "bottom_nav_menu not found or not unique"
    # Find the start of the LinearLayout open tag (12-space indent)
    open_start = src.rindex('            <LinearLayout\n', 0, src.index(menu_id))
    close_end = _find_matching_close(src, open_start, "            ")
    # Also swallow one trailing newline if present
    if src[close_end:close_end + 1] == "\n":
        close_end += 1
    src = src[:open_start] + src[close_end:]
    print("  bottom_nav_menu removed from layout")

    # Tag with marker
    old = "<!-- " + SBB_MARKER + ": bottom bar - menu + key entries + start badge -->"
    assert src.count(old) == 1, "bottom bar comment not found"
    src = src.replace(
        old,
        old + "\n        <!-- " + MARKER + ":nomenu menu button removed per user request -->",
        1)
    _write(path, src)
    print("layout_main.xml menu removal OK")


def patch_layout_cards_black(root):
    """Revert dashboard cards from frosted glass (#2EFFFFFF) back to black (#161616)."""
    path = root + "/" + LAYOUT_MAIN
    src = _read(path)
    if MARKER + ":blackcards" in src:
        print("layout_main.xml cards already black, skip")
        return

    old = 'app:cardBackgroundColor="#2EFFFFFF"'
    count = src.count(old)
    assert count == 4, f"frosted glass card count changed (found {count}, want 4)"
    src = src.replace(old, 'app:cardBackgroundColor="#161616"')

    old = "<!-- " + SBB_MARKER + ":glasscards frosted glass cards, gradient shows through -->"
    assert src.count(old) == 1, "glasscards comment not found"
    src = src.replace(
        old,
        "<!-- " + MARKER + ":blackcards cards reverted to opaque black per user request -->",
        1)
    _write(path, src)
    print("layout_main.xml cards reverted to black OK")


def patch_layout_badge_separate_row(root):
    """Move badge to its own row above nav items, make it smaller (80dp).

    Current: bottom_bar is horizontal with
      [config] [route] [badge 116dp vertical] [group] [settings]
    New: bottom_bar becomes vertical with
      [badge row: centered 80dp badge + state label]
      [nav row: config | route | group | settings]
    """
    path = root + "/" + LAYOUT_MAIN
    src = _read(path)
    if MARKER + ":badgerow" in src:
        print("layout_main.xml badge already on separate row, skip")
        return

    # --- Step 1: extract the badge container block ---
    # The badge container is the LinearLayout with paddingStart="6dp" that
    # holds card_badge_bg / card_badge / card_timer / card_badge_state.
    badge_id = 'android:id="@+id/card_badge_bg"'
    assert src.count(badge_id) == 1, "card_badge_bg not found or not unique"
    # The container LinearLayout opens with 12-space indent before the badge
    container_open = src.rindex("            <LinearLayout\n", 0, src.index(badge_id))
    container_close = _find_matching_close(src, container_open, "            ")
    badge_block = src[container_open:container_close]
    # Remove it from its current position (keep one trailing newline handling)
    end = container_close
    if src[end:end + 1] == "\n":
        end += 1
    # Also swallow the blank line before it if present
    start = container_open
    if src[start - 1:start] == "\n":
        start -= 1
    src = src[:start] + src[end:]
    print("  badge block extracted")

    # --- Step 2: shrink the badge (116dp -> 80dp, timer text 26sp -> 20sp) ---
    assert badge_block.count('"116dp"') == 4, "badge 116dp count changed"
    badge_block = badge_block.replace('"116dp"', '"80dp"')
    assert 'android:textSize="26sp"' in badge_block, "badge timer text size not found"
    badge_block = badge_block.replace('android:textSize="26sp"', 'android:textSize="20sp"', 1)
    print("  badge shrunk to 80dp")

    # --- Step 3: restructure bottom_bar to vertical with badge row + nav row ---
    # Find bottom_bar open tag
    bar_open = src.index('android:id="@+id/bottom_bar"')
    bar_tag_start = src.rindex("<LinearLayout\n", 0, bar_open)
    bar_tag_end = src.index(">", bar_tag_start) + 1
    bar_open_tag = src[bar_tag_start:bar_tag_end]
    assert 'android:orientation="horizontal"' in bar_open_tag, "bottom_bar not horizontal"
    new_bar_open_tag = bar_open_tag.replace(
        'android:orientation="horizontal"',
        'android:orientation="vertical"')
    src = src[:bar_tag_start] + new_bar_open_tag + src[bar_tag_end:]
    print("  bottom_bar switched to vertical")

    # Find the first nav item (config) to insert the badge row before it
    config_id = 'android:id="@+id/bottom_nav_config"'
    assert src.count(config_id) == 1, "bottom_nav_config not found"
    config_open = src.rindex("            <LinearLayout\n", 0, src.index(config_id))

    # Build the badge row: centered horizontal container with the badge
    # Re-indent badge block from 12-space base to 16-space base (one level deeper)
    badge_lines = badge_block.strip("\n").split("\n")
    reindented = []
    for line in badge_lines:
        if line.startswith("            "):
            reindented.append("    " + line)
        elif line == "":
            reindented.append(line)
        else:
            reindented.append("    " + line)
    badge_inner = "\n".join(reindented)

    badge_row = (
        '            <!-- ' + MARKER + ':badgerow start button on its own row, smaller -->\n'
        '            <LinearLayout\n'
        '                android:layout_width="match_parent"\n'
        '                android:layout_height="wrap_content"\n'
        '                android:gravity="center_horizontal"\n'
        '                android:orientation="horizontal"\n'
        '                android:paddingBottom="6dp">\n'
        '\n'
        + badge_inner + '\n'
        '            </LinearLayout>\n'
        '\n'
        '            <!-- ' + MARKER + ':badgerow nav items row -->\n'
        '            <LinearLayout\n'
        '                android:layout_width="match_parent"\n'
        '                android:layout_height="wrap_content"\n'
        '                android:gravity="center_vertical"\n'
        '                android:orientation="horizontal">\n'
        '\n'
    )
    src = src[:config_open] + badge_row + src[config_open:]

    # Close the nav row LinearLayout before bottom_bar closes.
    # Find bottom_bar's closing tag: it's the "        </LinearLayout>" that
    # closes bottom_bar. We need the last nav item (settings) close, then
    # insert the nav-row close before bottom_bar close.
    # The settings nav item is the last _nav_item; find its close, then find
    # the bottom_bar close after it.
    settings_id = 'android:id="@+id/bottom_nav_settings"'
    assert src.count(settings_id) == 1, "bottom_nav_settings not found"
    settings_open = src.rindex("            <LinearLayout\n", 0, src.index(settings_id))
    # NOTE: after inserting badge_row, nav items are still at 12-space indent
    # inside the new nav-row container (16-space). The settings close is at
    # 12 spaces.
    settings_close = _find_matching_close(src, settings_open, "            ")
    # Find bottom_bar close: the next "        </LinearLayout>" (8 spaces)
    # after settings_close
    bar_close = src.index("        </LinearLayout>", settings_close)
    # Insert nav-row close (12 spaces) before bottom_bar close
    nav_row_close = '            </LinearLayout>\n'
    # Handle trailing newline after settings close
    insert_at = settings_close
    if src[insert_at:insert_at + 1] == "\n":
        insert_at += 1
    # Skip any blank lines between settings close and bar close to keep tidy
    src = (src[:insert_at] + "\n" + nav_row_close
           + src[insert_at:bar_close] + src[bar_close:])
    # The above may leave extra blank lines; that's cosmetically fine for XML.

    _write(path, src)
    print("layout_main.xml badge moved to separate row OK")


def patch_main_activity_remove_menu(root):
    """Remove the bottomNavMenu click wiring (menu button gone from layout)."""
    path = root + "/" + MAIN_ACTIVITY
    src = _read(path)
    if MARKER + ":nomenuclick" in src:
        print("MainActivity.kt menu click already removed, skip")
        return

    # Match both multi-line and single-line formats
    pattern = r"        binding\.bottomNavMenu\.setOnClickListener \{[^}]*\}\n"
    m = re.search(pattern, src)
    if m:
        src = (src[:m.start()]
               + "        // " + MARKER + ":nomenuclick menu button removed from bottom bar\n"
               + src[m.end():])
    elif "bottomNavMenu" not in src:
        # Already gone; just tag
        pass
    else:
        assert False, "bottomNavMenu found but wiring pattern unexpected"

    # GravityCompat import is now unused; remove it to avoid warnings
    # (keep it if referenced elsewhere)
    if src.count("GravityCompat") == 1:
        old_imp = "import androidx.core.view.GravityCompat\n"
        assert src.count(old_imp) == 1, "GravityCompat import not found"
        src = src.replace(old_imp, "", 1)
        print("  unused GravityCompat import removed")

    _write(path, src)
    print("MainActivity.kt menu click removed OK")


def patch_layout_remove_drawer(root):
    """Remove both NavigationViews (side drawer) from the layout entirely."""
    path = root + "/" + LAYOUT_MAIN
    src = _read(path)
    if MARKER + ":nodiscard" in src:
        print("layout_main.xml drawer already removed, skip")
        return

    # Remove the first NavigationView (@+id/nav_view)
    nav1_start = src.index('<com.google.android.material.navigation.NavigationView')
    # Verify it's the nav_view one
    assert 'android:id="@+id/nav_view"' in src[nav1_start:nav1_start + 500], "nav_view block not found"
    nav1_end = src.index("/>", nav1_start) + len("/>")
    # Swallow trailing newlines (up to 2)
    while src[nav1_end:nav1_end + 1] == "\n" and src[nav1_end:nav1_end + 2] != "\n\n":
        # Keep one blank line handling simple: remove the block and following blank line
        break
    # Remove block plus one following newline if present
    end = nav1_end
    if src[end:end + 1] == "\n":
        end += 1
    # Also remove preceding blank line to avoid double blank
    start = nav1_start
    if src[start - 1:start] == "\n" and src[start - 2:start - 1] == "\n":
        start -= 1
    src = src[:start] + src[end:]
    print("  nav_view NavigationView removed")

    # Remove the second NavigationView (@+id/nav_view_black)
    nav2_start = src.index('<com.google.android.material.navigation.NavigationView')
    assert 'android:id="@+id/nav_view_black"' in src[nav2_start:nav2_start + 600], "nav_view_black block not found"
    nav2_end = src.index("/>", nav2_start) + len("/>")
    end = nav2_end
    if src[end:end + 1] == "\n":
        end += 1
    start = nav2_start
    if src[start - 1:start] == "\n" and src[start - 2:start - 1] == "\n":
        start -= 1
    src = src[:start] + src[end:]
    print("  nav_view_black NavigationView removed")

    # Marker comment before DrawerLayout close
    old = "</androidx.drawerlayout.widget.DrawerLayout>"
    assert src.count(old) == 1, "DrawerLayout close not found"
    src = src.replace(
        old,
        "    <!-- " + MARKER + ":nodiscard side drawer NavigationViews removed per user request -->\n" + old,
        1)
    _write(path, src)
    print("layout_main.xml drawer removed OK")


def patch_main_activity_remove_drawer(root):
    """Strip all drawer/navigation references from MainActivity."""
    path = root + "/" + MAIN_ACTIVITY
    src = _read(path)
    if MARKER + ":nodiscard" in src:
        print("MainActivity.kt drawer refs already removed, skip")
        return

    # 1. Remove NavigationView import
    old = "import com.google.android.material.navigation.NavigationView\n"
    if src.count(old) == 1:
        src = src.replace(old, "", 1)
        print("  NavigationView import removed")

    # 2. Remove OnNavigationItemSelectedListener from class declaration
    # Handle both multi-line and single-line formats
    old_multi = ("    OnPreferenceDataStoreChangeListener,\n"
                 "    NavigationView.OnNavigationItemSelectedListener {")
    old_single = "NavigationView.OnNavigationItemSelectedListener"
    if src.count(old_multi) == 1:
        src = src.replace(
            old_multi,
            "    OnPreferenceDataStoreChangeListener {",
            1)
    elif src.count(old_single) == 1:
        # Single-line: remove the interface and preceding comma
        src = re.sub(
            r",\s*NavigationView\.OnNavigationItemSelectedListener",
            "",
            src,
            count=1)
    else:
        assert False, "OnNavigationItemSelectedListener decl not found"
    print("  OnNavigationItemSelectedListener interface removed")

    # 3. Remove lateinit var navigation
    old = "    lateinit var navigation: NavigationView\n"
    assert src.count(old) == 1, "navigation field not found"
    src = src.replace(old, "", 1)
    print("  navigation field removed")

    # 4. Remove navigation setup block in onCreate
    # The block is:
    #         if (themeResId !in intArrayOf(
    #                 R.style.Theme_SagerNet_Black
    #             )
    #         ) {
    #             navigation = binding.navView
    #             binding.drawerLayout.removeView(binding.navViewBlack)
    #         } else {
    #             navigation = binding.navViewBlack
    #             binding.drawerLayout.removeView(binding.navView)
    #         }
    #         navigation.setNavigationItemSelectedListener(this)
    old_start = src.index("        if (themeResId !in intArrayOf(")
    # Find the end: navigation.setNavigationItemSelectedListener(this)\n
    old_end_marker = "        navigation.setNavigationItemSelectedListener(this)\n"
    assert src.count(old_end_marker) == 1, "setNavigationItemSelectedListener not found"
    old_end = src.index(old_end_marker) + len(old_end_marker)
    # Verify the block starts before the marker
    assert old_start < old_end, "navigation setup block order wrong"
    src = (src[:old_start]
           + "        // " + MARKER + ":nodiscard drawer navigation removed\n"
           + src[old_end:])
    print("  navigation setup block removed")

    # 5. Remove onNavigationItemSelected override
    old = """    override fun onNavigationItemSelected(item: MenuItem): Boolean {
        if (item.isChecked) binding.drawerLayout.closeDrawers() else {
            return displayFragmentWithId(item.itemId)
        }
        return true
    }
"""
    # The exact formatting may vary; try flexible match
    if src.count(old) != 1:
        # Try regex
        pattern = r"    override fun onNavigationItemSelected\(item: MenuItem\): Boolean \{\n.*?\n    \}\n"
        m = re.search(pattern, src, re.DOTALL)
        assert m, "onNavigationItemSelected not found"
        src = src[:m.start()] + src[m.end():]
    else:
        src = src.replace(old, "", 1)
    print("  onNavigationItemSelected removed")

    # 6. Remove navigation.menu visibility setup in onCreate
    # Looks like:
    #         if (::navigation.isInitialized) {
    #             navigation.menu.findItem(R.id.nav_traffic)?.isVisible = clashApi
    #             navigation.menu.findItem(R.id.nav_tuiguang)?.isVisible = !isPlay
    #         }
    pattern = r"        if \(::navigation\.isInitialized\) \{\n.*?\n        \}\n"
    m = re.search(pattern, src, re.DOTALL)
    if m:
        src = src[:m.start()] + src[m.end():]
        print("  navigation menu visibility setup removed")

    # 7. In displayFragmentWithId: replace navigation.menu.findItem with just updateBottomNav
    # Current (after start-button-bottom patch):
    #         navigation.menu.findItem(id).isChecked = true
    #         updateBottomNav(id) // chanboxStartButtonBottom:navhi
    old = "        navigation.menu.findItem(id).isChecked = true\n"
    assert src.count(old) == 1, "navigation.menu.findItem not found"
    src = src.replace(
        old,
        "        // " + MARKER + ":nodiscard drawer gone; bottom nav highlight only\n",
        1)
    print("  navigation.menu.findItem replaced")

    # 8. Remove MenuItem import if now unused
    # Check if MenuItem is used elsewhere
    if src.count("MenuItem") == 0:
        pass  # no import to remove
    elif src.count("MenuItem") == 1 and "import android.view.MenuItem" in src:
        # Only the import remains, remove it
        src = src.replace("import android.view.MenuItem\n", "", 1)
        print("  unused MenuItem import removed")

    # 9. Remove drawerLayout closeDrawers calls (drawer no longer exists)
    # In displayFragment: binding.drawerLayout.closeDrawers()
    old = "        binding.drawerLayout.closeDrawers()\n"
    count = src.count(old)
    # There might be multiple; remove all
    src = src.replace(old, "", count)
    if count:
        print(f"  removed {count} drawerLayout.closeDrawers() calls")

    # 10. Neutralize onKeyDown drawer handling
    # The block:
    #             KeyEvent.KEYCODE_DPAD_LEFT -> {
    #                 if (super.onKeyDown(keyCode, event)) return true
    #                 binding.drawerLayout.open()
    #                 navigation.requestFocus()
    #             }
    #
    #             KeyEvent.KEYCODE_DPAD_RIGHT -> {
    #                 if (binding.drawerLayout.isOpen) {
    #                     binding.drawerLayout.close()
    #                     return true
    #                 }
    #             }
    #         ...
    #         if (binding.drawerLayout.isOpen) return false
    old = """            KeyEvent.KEYCODE_DPAD_LEFT -> {
                if (super.onKeyDown(keyCode, event)) return true
                binding.drawerLayout.open()
                navigation.requestFocus()
            }

            KeyEvent.KEYCODE_DPAD_RIGHT -> {
                if (binding.drawerLayout.isOpen) {
                    binding.drawerLayout.close()
                    return true
                }
            }
"""
    if src.count(old) == 1:
        src = src.replace(old, "", 1)
        print("  DPAD drawer handling removed")
    old = "        if (binding.drawerLayout.isOpen) return false\n"
    if src.count(old) == 1:
        src = src.replace(old, "", 1)
        print("  drawerLayout.isOpen check removed")

    # Marker
    old = "    fun displayFragmentWithId(@IdRes id: Int): Boolean {"
    assert src.count(old) == 1, "displayFragmentWithId anchor not found"
    src = src.replace(
        old,
        "    // " + MARKER + ":nodiscard side drawer removed entirely\n" + old,
        1)
    _write(path, src)
    print("MainActivity.kt drawer refs removed OK")


def patch_toolbar_fragment(root):
    """Remove hamburger navigation icon from toolbar (drawer is gone)."""
    path = root + "/" + TOOLBAR_FRAGMENT
    src = _read(path)
    if MARKER in src:
        print("ToolbarFragment.kt already patched, skip")
        return

    # Remove setNavigationIcon and setNavigationOnClickListener (flexible format)
    # Pattern 1: multi-line with drawer open
    pattern1 = (
        r"        toolbar\.setNavigationIcon\(R\.drawable\.ic_navigation_menu\)\n"
        r"        toolbar\.setNavigationOnClickListener \{\n"
        r".*?"
        r"\n        \}\n"
    )
    m = re.search(pattern1, src, re.DOTALL)
    if m:
        src = src[:m.start()] + src[m.end():]
    else:
        # Pattern 2: single-line or simplified
        pattern2 = r"        toolbar\.setNavigationIcon\(.*?\)\n"
        m2 = re.search(pattern2, src)
        if m2:
            src = src[:m2.start()] + src[m2.end():]
        pattern3 = r"        toolbar\.setNavigationOnClickListener \{.*?\n        \}\n"
        m3 = re.search(pattern3, src, re.DOTALL)
        if m3:
            src = src[:m3.start()] + src[m3.end():]
    # Add marker comment after toolbar assignment
    old_assign = "        toolbar = view.findViewById(R.id.toolbar)\n"
    assert src.count(old_assign) == 1, "toolbar assignment not found"
    src = src.replace(
        old_assign,
        old_assign + "        // " + MARKER + ": side drawer removed, no hamburger icon\n",
        1)

    # Remove GravityCompat import if unused
    if src.count("GravityCompat") == 1:
        old_imp = "import androidx.core.view.GravityCompat\n"
        assert src.count(old_imp) == 1, "GravityCompat import not found"
        src = src.replace(old_imp, "", 1)
        print("  unused GravityCompat import removed")

    # Remove MainActivity import if unused (was only for drawerLayout access)
    if "MainActivity" not in src.replace("import io.nekohasekai.sagernet.ui.MainActivity", ""):
        # Check if MainActivity is referenced elsewhere
        pass
    # Actually check: is MainActivity still referenced?
    refs = src.count("MainActivity")
    # One ref is the import itself; if only 1, remove import
    if refs == 1 and "import io.nekohasekai.sagernet.ui.MainActivity" in src:
        # Same package, import is unnecessary anyway, but remove for cleanliness
        src = src.replace("import io.nekohasekai.sagernet.ui.MainActivity\n", "", 1)
        print("  unused MainActivity import removed")

    _write(path, src)
    print("ToolbarFragment.kt hamburger icon removed OK")


def patch_menu_remove_search(root):
    """Remove the search (magnifier) icon from the main toolbar menu."""
    path = root + "/" + MENU_ADD_PROFILE
    src = _read(path)
    if MARKER + ":nosearch" in src:
        print("add_profile_menu.xml search already removed, skip")
        return

    # Remove the action_search item block (flexible trailing whitespace)
    pattern = (
        r'    <item\n'
        r'        android:id="@\+id/action_search"\n'
        r'        android:title="@android:string/search_go"\n'
        r'        app:actionViewClass="androidx\.appcompat\.widget\.SearchView"\n'
        r'        app:showAsAction="always" />\n\n?'
    )
    m = re.search(pattern, src)
    assert m, "action_search menu item not found"
    src = src[:m.start()] + src[m.end():]

    # Marker comment
    old = "<menu xmlns:android="
    assert src.count(old) == 1, "menu root not found"
    src = src.replace(
        old,
        "<!-- " + MARKER + ":nosearch search icon removed per user request -->\n" + old,
        1)
    _write(path, src)
    print("add_profile_menu.xml search removed OK")


def patch_appbar_gradient(root):
    """Toolbar background -> purple-blue gradient (same as dashboard below)."""
    path = root + "/" + LAYOUT_APPBAR
    src = _read(path)
    if MARKER + ":toolbargradient" in src:
        print("layout_appbar.xml gradient already applied, skip")
        return

    # Create the gradient drawable (same colors as dashboard: #4B2E9E -> #24478F -> #0B0B0F)
    res = root + "/app/src/main/res"
    _write(res + "/drawable/bg_toolbar_gradient.xml",
           '<?xml version="1.0" encoding="utf-8"?>\n'
           '<!-- ' + MARKER + ':toolbargradient purple-blue gradient for toolbar -->\n'
           '<shape xmlns:android="http://schemas.android.com/apk/res/android"\n'
           '    android:shape="rectangle">\n'
           '    <gradient\n'
           '        android:angle="135"\n'
           '        android:startColor="#4B2E9E"\n'
           '        android:centerColor="#24478F"\n'
           '        android:endColor="#0B0B0F" />\n'
           '</shape>\n')
    print("  bg_toolbar_gradient.xml created")

    # Apply to AppBarLayout and Toolbar (replace ?attr/colorPrimary)
    old = 'android:background="?attr/colorPrimary"'
    count = src.count(old)
    assert count == 2, f"toolbar background count changed (found {count}, want 2)"
    src = src.replace(old, 'android:background="@drawable/bg_toolbar_gradient"')

    # Marker
    old = "<com.google.android.material.appbar.AppBarLayout"
    assert src.count(old) == 1, "AppBarLayout not found"
    src = src.replace(
        old,
        "<!-- " + MARKER + ":toolbargradient toolbar uses purple-blue gradient -->\n" + old,
        1)
    _write(path, src)
    print("layout_appbar.xml gradient applied OK")


def patch_dashboard_narrow_cards(root):
    """Narrow the dashboard cards (download/upload, auto-select, node config).

    Add horizontal padding to the dashboard_panel so cards don't span the
    full width.
    """
    path = root + "/" + LAYOUT_MAIN
    src = _read(path)
    if MARKER + ":narrowcards" in src:
        print("layout_main.xml dashboard cards already narrowed, skip")
        return

    # Find the dashboard_panel LinearLayout open tag
    panel_id = 'android:id="@+id/dashboard_panel"'
    assert src.count(panel_id) == 1, "dashboard_panel not found"
    panel_open = src.rindex("<LinearLayout\n", 0, src.index(panel_id))
    panel_tag_end = src.index(">", panel_open) + 1
    panel_tag = src[panel_open:panel_tag_end]

    # Add horizontal padding if not already present
    if 'android:paddingStart=' not in panel_tag and 'android:paddingLeft=' not in panel_tag:
        # Insert padding attributes before the closing >
        new_tag = panel_tag.replace(
            ">",
            '\n                            android:paddingStart="16dp"\n'
            '                            android:paddingEnd="16dp">',
            1)
        src = src[:panel_open] + new_tag + src[panel_tag_end:]
        print("  dashboard_panel horizontal padding added")
    else:
        print("  dashboard_panel already has horizontal padding")

    # Marker
    old = "<!-- " + MARKER + ":blackcards cards reverted to opaque black per user request -->"
    if src.count(old) == 1:
        src = src.replace(
            old,
            old + "\n        <!-- " + MARKER + ":narrowcards dashboard cards narrowed -->",
            1)
    else:
        # Fallback: add marker near dashboard_panel
        old2 = "<!-- " + SBB_MARKER + ":dashboardtop dashboard panel below node list -->"
        assert src.count(old2) == 1, "dashboard panel marker not found"
        src = src.replace(
            old2,
            old2 + "\n        <!-- " + MARKER + ":narrowcards dashboard cards narrowed -->",
            1)
    _write(path, src)
    print("layout_main.xml dashboard cards narrowed OK")


CONFIGURATION_FRAGMENT = "app/src/main/java/io/nekohasekai/sagernet/ui/ConfigurationFragment.kt"


def patch_configuration_fragment_remove_search(root):
    """Remove the dangling R.id.action_search wiring in ConfigurationFragment.kt.

    patch_menu_remove_search() deletes the action_search menu item, so the
    Kotlin reference `toolbar.findViewById<SearchView>(R.id.action_search)`
    no longer resolves (build #111 failed: 'Unresolved reference action_search').
    Remove the searchView declaration + its listener block (lines kept idempotent
    via marker). The private cancelSearch() stays; unused private funs only warn.
    """
    path = root + "/" + CONFIGURATION_FRAGMENT
    src = _read(path)
    if MARKER + ":nosearchfrag" in src:
        print("ConfigurationFragment.kt search wiring already removed, skip")
        return

    lines = src.split("\n")
    idx = None
    for i, l in enumerate(lines):
        if "findViewById<SearchView>(R.id.action_search)" in l:
            idx = i
            break
    assert idx is not None, "action_search findViewById not found in ConfigurationFragment.kt"

    j = idx
    while j < len(lines) and "if (searchView != null)" not in lines[j]:
        j += 1
    assert j < len(lines), "searchView if-block not found in ConfigurationFragment.kt"

    # Brace-count to the end of the if-block.
    depth = 0
    k = j
    while k < len(lines):
        depth += lines[k].count("{") - lines[k].count("}")
        if depth == 0:
            break
        k += 1
    assert depth == 0, "unbalanced braces in searchView if-block"

    indent = lines[idx][:len(lines[idx]) - len(lines[idx].lstrip())]
    del lines[idx:k + 1]
    lines.insert(idx, indent + "// " + MARKER +
                 ":nosearchfrag search wiring removed (menu item action_search deleted)")
    _write(path, "\n".join(lines))
    print("ConfigurationFragment.kt search wiring removed OK")


def main():
    root = "."
    patch_layout_remove_menu(root)
    patch_layout_cards_black(root)
    patch_layout_badge_separate_row(root)
    patch_main_activity_remove_menu(root)
    patch_layout_remove_drawer(root)
    patch_main_activity_remove_drawer(root)
    patch_toolbar_fragment(root)
    patch_menu_remove_search(root)
    patch_configuration_fragment_remove_search(root)
    patch_appbar_gradient(root)
    patch_dashboard_narrow_cards(root)
    print("ALL UI-TWEAK PATCHES OK")


if __name__ == "__main__":
    main()
