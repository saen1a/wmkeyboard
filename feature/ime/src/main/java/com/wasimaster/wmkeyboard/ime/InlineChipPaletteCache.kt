package com.wasimaster.wmkeyboard.ime

import android.content.Context
import com.wasimaster.wmkeyboard.core.directboot.DirectBoot
import com.wasimaster.wmkeyboard.ime.ui.InlineChipPalette

/**
 * The last chip palette the board resolved, kept so the first inline
 * suggestions request after a cold start is themed (#250).
 *
 * Device-protected storage because `onCreate` runs before the first unlock and
 * the credential-encrypted store is unavailable there. Both the service and
 * the SDK-36 test read and write it through this one accessor, so the test
 * exercises the production path rather than a parallel preferences file.
 */
internal object InlineChipPaletteCache {

    private const val PREFS = "inline_chip_palette"

    /** The saved palette, or null before the board has drawn once. */
    fun load(context: Context): InlineChipPalette? {
        val prefs = prefs(context)
        if (!prefs.getBoolean("saved", false)) return null
        return InlineChipPalette(
            background = prefs.getInt("background", 0),
            title = prefs.getInt("title", 0),
            subtitle = prefs.getInt("subtitle", 0),
        )
    }

    fun save(context: Context, palette: InlineChipPalette) {
        prefs(context).edit()
            .putBoolean("saved", true)
            .putInt("background", palette.background)
            .putInt("title", palette.title)
            .putInt("subtitle", palette.subtitle)
            .apply()
    }

    private fun prefs(context: Context) =
        DirectBoot.deviceContext(context).getSharedPreferences(PREFS, Context.MODE_PRIVATE)
}
