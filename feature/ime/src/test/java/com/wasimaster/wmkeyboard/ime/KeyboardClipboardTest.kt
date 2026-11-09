package com.wasimaster.wmkeyboard.ime

import android.content.ClipboardManager
import android.content.Context
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment

/**
 * The keyboard's own copies while incognito keeps the clipboard private
 * (#392): they stay in memory, never reach the system clipboard, and are
 * forgotten when the mode ends.
 */
@RunWith(RobolectricTestRunner::class)
class KeyboardClipboardTest {
    private val context: Context = RuntimeEnvironment.getApplication()
    private val system = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager

    @After
    fun reset() {
        KeyboardClipboard.isPrivate = false
        KeyboardClipboard.onPrivateCopy = null
    }

    private fun systemText(): String? =
        system.primaryClip?.takeIf { it.itemCount > 0 }?.getItemAt(0)?.text?.toString()

    private fun systemSensitive(): Boolean =
        system.primaryClip?.description?.extras
            ?.getBoolean(KeyboardClipboard.EXTRA_IS_SENSITIVE) == true

    @Test
    fun `a sensitive system copy carries the platform flag`() {
        KeyboardClipboard.copy(context, "Tr0ub4dor&3xz", sensitive = true)
        assertEquals("Tr0ub4dor&3xz", systemText())
        assertTrue(systemSensitive())
    }

    @Test
    fun `a clear system copy does not carry the sensitive flag`() {
        KeyboardClipboard.copy(context, "hello")
        assertFalse(systemSensitive())
    }

    @Test
    fun `a private sensitive copy tells the history it is sensitive`() {
        var seen: Pair<String, Boolean>? = null
        KeyboardClipboard.onPrivateCopy = { text, sensitive -> seen = text to sensitive }
        KeyboardClipboard.isPrivate = true
        KeyboardClipboard.copy(context, "secret", sensitive = true)
        assertEquals("secret" to true, seen)
    }

    @Test
    fun `a private copy stays off the system clipboard`() {
        KeyboardClipboard.copy(context, "before")
        KeyboardClipboard.isPrivate = true
        KeyboardClipboard.copy(context, "secret")
        assertEquals("secret", KeyboardClipboard.held)
        assertEquals("before", systemText())
    }

    @Test
    fun `leaving private mode forgets the copy`() {
        KeyboardClipboard.isPrivate = true
        KeyboardClipboard.copy(context, "secret")
        KeyboardClipboard.isPrivate = false
        assertNull(KeyboardClipboard.held)
    }

    @Test
    fun `an ordinary copy goes to the system clipboard and is not held`() {
        KeyboardClipboard.copy(context, "hello")
        assertEquals("hello", systemText())
        assertNull(KeyboardClipboard.held)
    }

    @Test
    fun `an ordinary write has no self write token`() {
        KeyboardClipboard.copy(context, "hello")
        assertFalse(ClipboardWriteGate.consumeSelfWrite(system.primaryClip!!))
    }
}
