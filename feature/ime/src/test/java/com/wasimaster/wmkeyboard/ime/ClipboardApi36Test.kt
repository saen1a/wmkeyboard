package com.wasimaster.wmkeyboard.ime

import android.content.ClipboardManager
import android.content.Context
import android.os.Build
import com.wasimaster.wmkeyboard.core.directboot.DirectBoot
import com.wasimaster.wmkeyboard.ime.ui.InlineChipPalette
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config

/**
 * The clipboard and direct-boot surfaces at the API level the project targets
 * (36). Pinned on the class rather than inherited from robolectric.properties,
 * which stays at 34 for the rest of the suite: a failure to load the 36 jar
 * must fail this run loudly, never silently fall back to 34.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [36])
class ClipboardApi36Test {
    private val context: Context = RuntimeEnvironment.getApplication()
    private val system = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager

    @After
    fun reset() {
        KeyboardClipboard.isPrivate = false
        KeyboardClipboard.onPrivateCopy = null
    }

    @Test
    fun `the suite runs at API 36, not 34`() {
        assertEquals(36, Build.VERSION.SDK_INT)
    }

    @Test
    fun `a keyboard sensitive copy carries the extra on API 36`() {
        KeyboardClipboard.copy(context, "Tr0ub4dor&3xz", sensitive = true)
        val clip = system.primaryClip!!
        assertEquals("Tr0ub4dor&3xz", clip.getItemAt(0).text.toString())
        assertTrue(
            clip.description.extras
                ?.getBoolean(KeyboardClipboard.EXTRA_IS_SENSITIVE) == true,
        )
    }

    @Test
    fun `the palette cache lives in device-protected storage on API 36`() {
        val device = DirectBoot.deviceContext(context)
        assertTrue(device.isDeviceProtectedStorage)
        val palette = InlineChipPalette(
            background = 0xFF112233.toInt(),
            title = 0xFF445566.toInt(),
            subtitle = 0xFF778899.toInt(),
        )
        InlineChipPaletteCache.save(context, palette)
        // The cache must write the device-protected prefs themselves. A
        // round-trip through the cache alone would still pass if the cache
        // moved to credential-protected storage.
        val devicePrefs = device.getSharedPreferences("inline_chip_palette", Context.MODE_PRIVATE)
        assertTrue(devicePrefs.getBoolean("saved", false))
        assertEquals(palette.background, devicePrefs.getInt("background", 0))
        assertEquals(palette.title, devicePrefs.getInt("title", 0))
        assertEquals(palette.subtitle, devicePrefs.getInt("subtitle", 0))
        assertEquals(palette, InlineChipPaletteCache.load(context))
    }
}
