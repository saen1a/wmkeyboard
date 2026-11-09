package com.wasimaster.wmkeyboard.ime

import android.content.ClipData
import android.content.ClipDescription
import android.content.ClipboardManager
import android.content.Context
import android.net.Uri
import android.os.Build
import android.os.PersistableBundle

/**
 * The one gate for keyboard-originated clipboard writes.
 *
 * Every copy the keyboard makes - panel, tool, restore, clear - goes through
 * here so an architecture test can fail a new direct `setPrimaryClip`. The
 * sensitivity decision stays with the caller; this only carries it onto the
 * clip.
 */
object ClipboardWriteGate {

    /**
     * The description extra that carries a self-write token. Private to the
     * keyboard: a clip from any other app never has it, and it is removed from
     * the clipboard history path as soon as the listener reads it.
     */
    private const val SELF_WRITE_TOKEN_KEY = "com.wasimaster.wmkeyboard.SELF_WRITE_TOKEN"

    /** Copies [text] onto the system clipboard, marked sensitive when [sensitive]. */
    internal fun writeText(
        context: Context,
        text: CharSequence,
        label: CharSequence? = "",
        sensitive: Boolean = false,
        selfWrite: Boolean = false,
    ): Boolean = runCatching {
        writeClip(context, ClipData.newPlainText(label, text), sensitive, selfWrite)
    }.getOrDefault(false)

    /** A user's normal text copy; a private hold stays private (#392, #612). */
    fun copyText(
        context: Context,
        text: CharSequence,
        label: String = "",
        sensitive: Boolean = false,
    ) {
        KeyboardClipboard.copy(context, text, label, sensitive)
    }

    /** Copies [uri] onto the system clipboard, marked sensitive when [sensitive]. */
    fun copyUri(
        context: Context,
        uri: Uri,
        mimeType: String,
        label: String,
        sensitive: Boolean = false,
    ) {
        val clip = runCatching {
            if (mimeType.isBlank()) {
                ClipData.newUri(context.contentResolver, label, uri)
            } else {
                ClipData(ClipDescription(label, arrayOf(mimeType)), ClipData.Item(uri))
            }
        }.getOrNull() ?: return
        writeClip(context, clip, sensitive)
    }

    /** Writes [clip] as it is, marked sensitive when [sensitive]. */
    internal fun writeClip(
        context: Context,
        clip: ClipData,
        sensitive: Boolean = false,
        selfWrite: Boolean = false,
    ): Boolean = runCatching {
        if (sensitive) KeyboardClipboard.markSensitive(clip)
        if (selfWrite) recordSelfWrite(clip)
        (context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager).setPrimaryClip(clip)
    }.isSuccess

    /** Whether [clip] is one this gate wrote and has not yet been consumed. */
    fun consumeSelfWrite(clip: ClipData): Boolean {
        val token = runCatching {
            clip.description?.extras?.getString(SELF_WRITE_TOKEN_KEY)
        }.getOrNull()
        return SelfWriteLedger.consume(token)
    }

    /** Puts a fresh token on [clip] so the listener skips this write once. */
    private fun recordSelfWrite(clip: ClipData) {
        runCatching {
            val description = clip.description ?: return
            val extras = description.extras ?: PersistableBundle().also { description.extras = it }
            val token = java.util.UUID.randomUUID().toString()
            SelfWriteLedger.record(token)
            extras.putString(SELF_WRITE_TOKEN_KEY, token)
        }
    }

    /** Empties the system clipboard, with the pre-Android-9 stand-in. */
    fun clear(context: Context) {
        runCatching {
            val manager = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                manager.clearPrimaryClip()
            } else {
                manager.setPrimaryClip(ClipData.newPlainText("", ""))
            }
        }
    }
}
