#!/usr/bin/env python3
"""Patch NekoBox server list: two-column grid display.

User request: the main server/profile list should display in two columns
(like v2rayNG's "dual column" option) instead of a single-column list.

Two files are touched (both under the NekoBox checkout, run from its root):

1. app/src/main/java/io/nekohasekai/sagernet/ktx/FixedGridLayoutManager.kt (NEW)
   A GridLayoutManager counterpart of the existing FixedLinearLayoutManager
   (Layouts.kt): same IndexOutOfBoundsException guard in onLayoutChildren
   and same FAB hide/show-on-scroll behavior, but with spanCount=2.

2. app/src/main/java/io/nekohasekai/sagernet/ui/ConfigurationFragment.kt
   - import io.nekohasekai.sagernet.ktx.FixedLinearLayoutManager
     -> import io.nekohasekai.sagernet.ktx.FixedGridLayoutManager
   - layoutManager = FixedLinearLayoutManager(configurationListView)
     -> layoutManager = FixedGridLayoutManager(configurationListView)

Notes:
- `lateinit var layoutManager: LinearLayoutManager` is left as-is:
  GridLayoutManager extends LinearLayoutManager, so all existing usages
  (findFirstVisibleItemPosition, findLastVisibleItemPosition,
  findViewByPosition) keep compiling and working.
- The item layout (layout_profile.xml) uses match_parent width; in a
  2-span grid each card automatically takes half the width.
- ItemTouchHelper drag (UP/DOWN) and swipe keep working in a grid.
- ProfileSelectActivity reuses ConfigurationFragment(select=true), so it
  gets the two-column layout automatically.

Idempotent: re-running is a no-op (marker checks in both files).
"""
import os

KT_NEW = "app/src/main/java/io/nekohasekai/sagernet/ktx/FixedGridLayoutManager.kt"
KT_TARGET = "app/src/main/java/io/nekohasekai/sagernet/ui/ConfigurationFragment.kt"
MARKER = "twoColumnGrid"

NEW_FILE_CONTENT = '''package io.nekohasekai.sagernet.ktx

import android.graphics.Rect
import androidx.recyclerview.widget.GridLayoutManager
import androidx.recyclerview.widget.RecyclerView
import io.nekohasekai.sagernet.database.DataStore
import io.nekohasekai.sagernet.ui.MainActivity

// %s: two-column grid counterpart of FixedLinearLayoutManager (Layouts.kt).
// Same IndexOutOfBoundsException guard and FAB hide/show-on-scroll behavior.
class FixedGridLayoutManager(
    val recyclerView: RecyclerView,
    spanCount: Int = 2
) : GridLayoutManager(recyclerView.context, spanCount, RecyclerView.VERTICAL, false) {

    override fun onLayoutChildren(recycler: RecyclerView.Recycler?, state: RecyclerView.State?) {
        try {
            super.onLayoutChildren(recycler, state)
        } catch (ignored: IndexOutOfBoundsException) {
        }
    }

    private var listenerDisabled = false

    override fun scrollVerticallyBy(
        dx: Int, recycler: RecyclerView.Recycler,
        state: RecyclerView.State
    ): Int {
        // Matsuri style
        if (!DataStore.showBottomBar) return super.scrollVerticallyBy(dx, recycler, state)

        // SagerNet Style
        val scrollRange = super.scrollVerticallyBy(dx, recycler, state)
        if (listenerDisabled) return scrollRange
        val activity = recyclerView.context as? MainActivity
        if (activity == null) {
            listenerDisabled = true
            return scrollRange
        }

        val overscroll = dx - scrollRange
        if (overscroll > 0) {
            val view =
                (recyclerView.findViewHolderForAdapterPosition(findLastVisibleItemPosition())
                    ?: return scrollRange).itemView
            val itemLocation = Rect().also { view.getGlobalVisibleRect(it) }
            val fabLocation = Rect().also { activity.binding.fab.getGlobalVisibleRect(it) }
            if (!itemLocation.contains(fabLocation.left, fabLocation.top) && !itemLocation.contains(
                    fabLocation.right,
                    fabLocation.bottom
                )
            ) {
                return scrollRange
            }
            activity.binding.fab.apply {
                if (isShown) hide()
            }
        } else {
            activity.binding.fab.apply {
                if (!isShown) show()
            }
        }
        return scrollRange
    }

}
''' % MARKER


def patch_new_file(path):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            if MARKER in f.read():
                print("FixedGridLayoutManager.kt already exists, skip")
                return
    with open(path, "w", encoding="utf-8") as f:
        f.write(NEW_FILE_CONTENT)
    print("FixedGridLayoutManager.kt created OK")


def patch_fragment(path):
    with open(path, encoding="utf-8") as f:
        src = f.read()
    if MARKER in src:
        print("ConfigurationFragment.kt already patched, skip")
        return

    old_import = "import io.nekohasekai.sagernet.ktx.FixedLinearLayoutManager\n"
    new_import = "import io.nekohasekai.sagernet.ktx.FixedGridLayoutManager\n"
    assert src.count(old_import) == 1, "FixedLinearLayoutManager import not found exactly once"
    src = src.replace(old_import, new_import)

    old_init = "            layoutManager = FixedLinearLayoutManager(configurationListView)\n"
    new_init = (
        f"            layoutManager = FixedGridLayoutManager(configurationListView) "
        f"// {MARKER}\n"
    )
    assert src.count(old_init) == 1, "layoutManager init not found exactly once"
    src = src.replace(old_init, new_init)

    with open(path, "w", encoding="utf-8") as f:
        f.write(src)
    print("ConfigurationFragment.kt patched OK")


if __name__ == "__main__":
    patch_new_file(KT_NEW)
    patch_fragment(KT_TARGET)
