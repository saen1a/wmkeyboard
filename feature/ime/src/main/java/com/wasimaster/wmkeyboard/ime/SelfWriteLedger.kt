package com.wasimaster.wmkeyboard.ime

import java.util.concurrent.ConcurrentHashMap

/**
 * Tokens for clips the keyboard writes and must not record twice: a cleaned
 * copy written back to the system clipboard, or an Undo restore. A token is
 * valid for a short window, consumed once, and carries no content.
 *
 * The gate puts the token in `ClipData.description.extras`; this object owns
 * the expiry and the one-shot lookup.
 */
internal object SelfWriteLedger {
    const val DEFAULT_TTL_MILLIS = 5_000L

    private val tokens = ConcurrentHashMap<String, Long>()

    fun record(token: String, now: Long = System.currentTimeMillis()) {
        prune(now)
        tokens[token] = now + DEFAULT_TTL_MILLIS
    }

    fun consume(token: String?, now: Long = System.currentTimeMillis()): Boolean {
        if (token.isNullOrEmpty()) return false
        prune(now)
        val expiresAt = tokens.remove(token) ?: return false
        return expiresAt >= now
    }

    fun clear() = tokens.clear()

    private fun prune(now: Long) {
        tokens.entries.removeAll { it.value < now }
    }
}
